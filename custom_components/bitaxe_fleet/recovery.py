"""Conservative, opt-in automatic recovery for approved miners."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Literal

from homeassistant.core import HomeAssistant

from .axeos.models import EnrolledMiner, MinerId, MinerSnapshot, OverheatPolicy
from .storage import FleetIncident

type MinerProvider = Callable[[MinerId], EnrolledMiner | None]
type SnapshotProvider = Callable[[MinerId], MinerSnapshot | None]
type IncidentRecorder = Callable[[MinerId, str, str, str], Awaitable[object]]
type IncidentProvider = Callable[[], tuple[FleetIncident, ...]]
type ProfileRestore = Callable[[MinerId], Awaitable[bool]]


class RecoveryActionOutcome(StrEnum):
    """The only safe outcomes for one automatic restart request."""

    REQUESTED = "requested"
    UNCERTAIN = "uncertain"
    FAILED = "failed"


type RestartAction = Callable[[MinerId], Awaitable[RecoveryActionOutcome]]
type Clock = Callable[[], datetime]
type SnapshotCondition = Literal[
    "healthy",
    "paused",
    "unknown",
    "overheat",
    "power_fault",
    "hardware_fault",
    "zero_hashrate",
]


@dataclass(slots=True)
class _MinerRecoveryState:
    """Ephemeral state used to make recovery bounded across coordinator updates."""

    started_at: datetime
    attempts: list[datetime] = field(default_factory=list)
    unhealthy_observations: int = 0
    last_action_at: datetime | None = None
    restart_deadline: datetime | None = None
    restart_requested_at: datetime | None = None
    overheat_active: bool = False
    pending_profile_restore_at: datetime | None = None
    attempt_limit_reported: bool = False


class RecoveryEngine:
    """Evaluate live snapshots and perform only bounded opt-in recovery actions."""

    def __init__(
        self,
        hass: HomeAssistant,
        miner_provider: MinerProvider,
        snapshot_provider: SnapshotProvider,
        restart: RestartAction,
        restore_profile: ProfileRestore,
        record_incident: IncidentRecorder,
        *,
        clock: Clock | None = None,
        incident_provider: IncidentProvider | None = None,
    ) -> None:
        """Initialize callbacks that keep recovery independent of runtime ownership."""
        self._hass = hass
        self._miner_provider = miner_provider
        self._snapshot_provider = snapshot_provider
        self._restart = restart
        self._restore_profile = restore_profile
        self._record_incident = record_incident
        self._clock = clock or _utcnow
        self._incident_provider = incident_provider or _empty_incidents
        self._states: dict[MinerId, _MinerRecoveryState] = {}
        self._locks: dict[MinerId, asyncio.Lock] = {}
        self._tasks: dict[MinerId, asyncio.Task[None]] = {}
        self._closed = False

    def async_schedule(self, miner_id: MinerId) -> None:
        """Coalesce coordinator listener updates into one evaluation per miner."""
        if self._closed or miner_id in self._tasks:
            return
        task = self._hass.async_create_background_task(
            self.async_evaluate(miner_id),
            f"Bitaxe Fleet recovery {miner_id}",
        )
        self._tasks[miner_id] = task
        task.add_done_callback(
            lambda finished: self._async_task_done(miner_id, finished)
        )

    async def async_evaluate(self, miner_id: MinerId) -> None:
        """Evaluate the current snapshot once without ever retrying a mutation."""
        if self._closed:
            return
        lock = self._locks.setdefault(miner_id, asyncio.Lock())
        async with lock:
            miner = self._miner_provider(miner_id)
            snapshot = self._snapshot_provider(miner_id)
            if miner is None or snapshot is None or not miner.enabled:
                self._async_forget_state(miner_id)
                return

            policy = miner.recovery_policy
            if not (
                policy.automatic_recovery_enabled
                or policy.automatic_profile_restore_enabled
            ):
                self._async_forget_state(miner_id)
                return

            now = self._clock()
            state = self._states.get(miner_id)
            if state is None:
                state = _restored_recovery_state(
                    miner_id,
                    now,
                    policy.rolling_window_seconds,
                    self._incident_provider(),
                )
                self._states[miner_id] = state
            condition = snapshot_condition(snapshot)
            if condition == "overheat":
                await self._async_handle_overheat(miner, state)
                return
            if state.overheat_active:
                await self._async_handle_overheat_clear(miner, state, now)
                return
            if state.pending_profile_restore_at is not None:
                if now >= state.pending_profile_restore_at:
                    state.pending_profile_restore_at = None
                    await self._async_restore_saved_profile(
                        miner,
                        "after thermal cooldown",
                    )
                return
            if state.restart_deadline is not None:
                await self._async_handle_pending_restart(miner, snapshot, state, now)
                return
            if not policy.automatic_recovery_enabled:
                return
            if _in_startup_grace(snapshot, state, now, policy.startup_grace_seconds):
                state.unhealthy_observations = 0
                return
            if condition in {"healthy", "paused", "unknown"}:
                state.unhealthy_observations = 0
                return

            state.unhealthy_observations += 1
            if state.unhealthy_observations < policy.consecutive_unhealthy_required:
                return
            if _is_in_cooldown(state, now, policy.cooldown_seconds):
                return

            _prune_attempts(state, now, policy.rolling_window_seconds)
            if len(state.attempts) >= policy.max_attempts:
                if not state.attempt_limit_reported:
                    state.attempt_limit_reported = True
                    await self._record_incident(
                        miner_id,
                        "automatic_restart",
                        "suppressed",
                        "rolling attempt limit reached",
                    )
                return

            state.unhealthy_observations = 0
            state.last_action_at = now
            state.attempts.append(now)
            state.attempt_limit_reported = False
            try:
                outcome = await self._restart(miner_id)
            except Exception:
                outcome = RecoveryActionOutcome.FAILED
            if outcome is RecoveryActionOutcome.FAILED:
                await self._record_incident(
                    miner_id,
                    "automatic_restart",
                    "failed",
                    f"unhealthy condition: {condition}",
                )
                return

            state.restart_requested_at = now
            state.restart_deadline = now + timedelta(
                seconds=policy.post_restart_timeout_seconds
            )
            await self._record_incident(
                miner_id,
                "automatic_restart",
                outcome.value,
                f"unhealthy condition: {condition}",
            )

    def async_forget_miner(self, miner_id: MinerId) -> None:
        """Stop pending work and discard ephemeral state after removal or disable."""
        task = self._tasks.pop(miner_id, None)
        if task is not None:
            task.cancel()
        self._async_forget_state(miner_id)

    async def async_close(self) -> None:
        """Cancel coalesced listener work while the owning config entry unloads."""
        if self._closed:
            return
        self._closed = True
        tasks = tuple(self._tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()
        self._states.clear()
        self._locks.clear()

    async def _async_handle_overheat(
        self, miner: EnrolledMiner, state: _MinerRecoveryState
    ) -> None:
        """Never restart or restore a profile while AxeOS reports thermal protection."""
        state.unhealthy_observations = 0
        state.pending_profile_restore_at = None
        if state.overheat_active:
            return
        state.overheat_active = True
        await self._record_incident(
            miner.identity.miner_id,
            "thermal_safety",
            "detected",
            "AxeOS overheat protection is active",
        )

    async def _async_handle_overheat_clear(
        self, miner: EnrolledMiner, state: _MinerRecoveryState, now: datetime
    ) -> None:
        """Defer an eligible saved-profile restore until cooldown ends."""
        state.overheat_active = False
        state.unhealthy_observations = 0
        await self._record_incident(
            miner.identity.miner_id,
            "thermal_safety",
            "cleared",
            "AxeOS overheat protection is no longer active",
        )
        policy = miner.recovery_policy
        if (
            policy.overheat_policy is OverheatPolicy.RESTORE_AFTER_COOLDOWN
            and policy.automatic_profile_restore_enabled
            and miner.recovery_profile is not None
        ):
            state.pending_profile_restore_at = now + timedelta(
                seconds=policy.cooldown_seconds
            )

    async def _async_handle_pending_restart(
        self,
        miner: EnrolledMiner,
        snapshot: MinerSnapshot,
        state: _MinerRecoveryState,
        now: datetime,
    ) -> None:
        """Wait for a positive post-restart observation before optional restoration."""
        condition = snapshot_condition(snapshot)
        if condition == "healthy":
            state.restart_deadline = None
            state.restart_requested_at = None
            await self._record_incident(
                miner.identity.miner_id,
                "automatic_restart",
                "verified",
                "positive hashrate observed after restart",
            )
            if (
                miner.recovery_policy.automatic_profile_restore_enabled
                and miner.recovery_profile is not None
            ):
                await self._async_restore_saved_profile(miner, "after verified restart")
            return
        deadline = state.restart_deadline
        if deadline is not None and now >= deadline:
            state.restart_deadline = None
            state.restart_requested_at = None
            state.unhealthy_observations = 0
            await self._record_incident(
                miner.identity.miner_id,
                "automatic_restart",
                "timed_out",
                "positive hashrate was not observed after restart",
            )

    async def _async_restore_saved_profile(
        self, miner: EnrolledMiner, reason: str
    ) -> None:
        """Apply a user-captured profile once without retrying ambiguity."""
        try:
            restored = await asyncio.wait_for(
                self._restore_profile(miner.identity.miner_id),
                timeout=miner.recovery_policy.verification_timeout_seconds,
            )
        except TimeoutError:
            restored = False
        await self._record_incident(
            miner.identity.miner_id,
            "automatic_profile_restore",
            "verified" if restored else "failed",
            reason,
        )

    def _async_task_done(self, miner_id: MinerId, task: asyncio.Task[None]) -> None:
        """Forget a completed coalesced task without disturbing a newer replacement."""
        if self._tasks.get(miner_id) is task:
            self._tasks.pop(miner_id, None)

    def _async_forget_state(self, miner_id: MinerId) -> None:
        """Discard state which must never survive an enrollment lifecycle change."""
        self._states.pop(miner_id, None)
        self._locks.pop(miner_id, None)


def snapshot_condition(snapshot: MinerSnapshot) -> SnapshotCondition:
    """Classify clear health signals; unknown telemetry never triggers a restart."""
    health = snapshot.health
    if health.overheat_mode not in {None, 0}:
        return "overheat"
    if health.mining_paused is True:
        return "paused"
    if health.power_fault is not None:
        return "power_fault"
    if health.hardware_fault is not None:
        return "hardware_fault"
    hashrate = snapshot.telemetry.hashrate_gh_s
    if hashrate is None:
        return "unknown"
    if hashrate <= 0:
        return "zero_hashrate"
    return "healthy"


def _in_startup_grace(
    snapshot: MinerSnapshot,
    state: _MinerRecoveryState,
    now: datetime,
    startup_grace_seconds: int,
) -> bool:
    """Use AxeOS uptime when available, otherwise grace from this runtime's start."""
    uptime = snapshot.telemetry.uptime_seconds
    if uptime is not None:
        return uptime < startup_grace_seconds
    return now - state.started_at < timedelta(seconds=startup_grace_seconds)


def _is_in_cooldown(
    state: _MinerRecoveryState, now: datetime, cooldown_seconds: int
) -> bool:
    """Avoid repeated automatic actions after any definite or uncertain attempt."""
    if state.last_action_at is None:
        return False
    return now - state.last_action_at < timedelta(seconds=cooldown_seconds)


def _prune_attempts(
    state: _MinerRecoveryState, now: datetime, rolling_window_seconds: int
) -> None:
    """Retain only attempts that still count toward the user's rolling limit."""
    threshold = now - timedelta(seconds=rolling_window_seconds)
    state.attempts[:] = [attempt for attempt in state.attempts if attempt >= threshold]


def _restored_recovery_state(
    miner_id: MinerId,
    now: datetime,
    rolling_window_seconds: int,
    incidents: tuple[FleetIncident, ...],
) -> _MinerRecoveryState:
    """Restore only prior automatic attempts; interrupted work is never success."""
    threshold = now - timedelta(seconds=rolling_window_seconds)
    attempts = sorted(
        incident.occurred_at
        for incident in incidents
        if (
            incident.miner_id == miner_id
            and incident.cause == "automatic_restart"
            and incident.outcome in {"requested", "uncertain", "failed"}
            and incident.occurred_at >= threshold
        )
    )
    return _MinerRecoveryState(
        started_at=now,
        attempts=attempts,
        last_action_at=attempts[-1] if attempts else None,
    )


def _empty_incidents() -> tuple[FleetIncident, ...]:
    """Return no persisted history when recovery is used in an isolated test."""
    return ()


def _utcnow() -> datetime:
    """Return one timezone-aware clock value for production recovery decisions."""
    return datetime.now(UTC)
