"""Tests for bounded opt-in automatic recovery decisions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from ipaddress import IPv4Address

from homeassistant.core import HomeAssistant

from custom_components.bitaxe_fleet.axeos.models import (
    EnrolledMiner,
    MinerConfiguration,
    MinerEndpoint,
    MinerHealth,
    MinerIdentity,
    MinerSnapshot,
    MinerTelemetry,
    OverheatPolicy,
    RecoveryPolicy,
    RecoveryProfile,
)
from custom_components.bitaxe_fleet.axeos.parser import normalize_miner_id
from custom_components.bitaxe_fleet.recovery import (
    RecoveryActionOutcome,
    RecoveryEngine,
)
from custom_components.bitaxe_fleet.storage import FleetIncident


@dataclass(slots=True)
class _Clock:
    """A deterministic recovery clock controlled by each state-machine test."""

    value: datetime

    def now(self) -> datetime:
        """Return the current test time."""
        return self.value

    def advance(self, seconds: int) -> None:
        """Move the deterministic clock by a positive test duration."""
        self.value += timedelta(seconds=seconds)


def _miner(policy: RecoveryPolicy, *, with_profile: bool = False) -> EnrolledMiner:
    """Create one enabled, approved miner for recovery evaluation."""
    profile = (
        RecoveryProfile(
            frequency_mhz=525.0,
            core_voltage_mv=1200,
            overclock_enabled=True,
            automatic_fan_speed=True,
            target_temperature_c=60,
            minimum_fan_speed_percent=25,
        )
        if with_profile
        else None
    )
    return EnrolledMiner(
        endpoint=MinerEndpoint(IPv4Address("192.168.10.25")),
        identity=MinerIdentity(
            miner_id=normalize_miner_id("02:12:34:56:78:9a"),
            hostname="bitaxe-lab",
            asic_model="BM1368",
            board_version="Bitaxe Supra",
            firmware_version="v2.14.2",
        ),
        recovery_policy=policy,
        recovery_profile=profile,
    )


def _snapshot(
    clock: _Clock,
    *,
    hashrate: float | None,
    uptime: int = 3600,
    health: MinerHealth | None = None,
) -> MinerSnapshot:
    """Create a validated coordinator snapshot with an explicit health state."""
    miner_id = normalize_miner_id("02:12:34:56:78:9a")
    return MinerSnapshot(
        endpoint=MinerEndpoint(IPv4Address("192.168.10.25")),
        identity=MinerIdentity(
            miner_id=miner_id,
            hostname="bitaxe-lab",
            asic_model="BM1368",
            board_version="Bitaxe Supra",
            firmware_version="v2.14.2",
        ),
        telemetry=MinerTelemetry(
            hashrate_gh_s=hashrate,
            power_w=17.4,
            temperature_c=54.0,
            uptime_seconds=uptime,
        ),
        observed_at=clock.now(),
        configuration=MinerConfiguration(),
        health=health or MinerHealth(),
    )


def _engine(
    hass: HomeAssistant,
    miner: EnrolledMiner,
    snapshots: dict[str, MinerSnapshot],
    clock: _Clock,
    restart_outcomes: list[RecoveryActionOutcome],
    incidents: list[tuple[str, str, str]],
    profile_restores: list[str],
    prior_incidents: tuple[FleetIncident, ...] = (),
) -> RecoveryEngine:
    """Build a recovery engine backed by controlled in-memory callbacks."""
    miner_id = str(miner.identity.miner_id)

    async def restart(_: str) -> RecoveryActionOutcome:
        """Return the next controlled restart outcome without network I/O."""
        return restart_outcomes.pop(0)

    async def restore_profile(restored_miner_id: str) -> bool:
        """Record an automatic profile restore without contacting AxeOS."""
        profile_restores.append(restored_miner_id)
        return True

    async def record_incident(_: str, cause: str, outcome: str, detail: str) -> object:
        """Retain only the safe state transition tuple asserted by tests."""
        incidents.append((cause, outcome, detail))
        return None

    return RecoveryEngine(
        hass,
        lambda requested_miner_id: (
            miner if str(requested_miner_id) == miner_id else None
        ),
        lambda requested_miner_id: snapshots.get(str(requested_miner_id)),
        restart,
        restore_profile,
        record_incident,
        clock=clock.now,
        incident_provider=lambda: prior_incidents,
    )


async def test_recovery_requires_consecutive_unhealthy_snapshots_and_verifies(
    hass: HomeAssistant,
) -> None:
    """A restart is opt-in, thresholded, and verified by positive hashrate."""
    clock = _Clock(datetime(2026, 7, 17, tzinfo=UTC))
    policy = RecoveryPolicy(
        automatic_recovery_enabled=True,
        startup_grace_seconds=0,
        consecutive_unhealthy_required=3,
    )
    miner = _miner(policy)
    miner_id = str(miner.identity.miner_id)
    snapshots = {miner_id: _snapshot(clock, hashrate=0.0)}
    outcomes = [RecoveryActionOutcome.REQUESTED]
    incidents: list[tuple[str, str, str]] = []
    profile_restores: list[str] = []
    engine = _engine(
        hass, miner, snapshots, clock, outcomes, incidents, profile_restores
    )

    await engine.async_evaluate(miner.identity.miner_id)
    await engine.async_evaluate(miner.identity.miner_id)
    assert outcomes == [RecoveryActionOutcome.REQUESTED]

    await engine.async_evaluate(miner.identity.miner_id)
    assert outcomes == []
    assert incidents == [
        ("automatic_restart", "requested", "unhealthy condition: zero_hashrate")
    ]

    clock.advance(60)
    snapshots[miner_id] = _snapshot(clock, hashrate=500.0)
    await engine.async_evaluate(miner.identity.miner_id)

    assert incidents[-1] == (
        "automatic_restart",
        "verified",
        "positive hashrate observed after restart",
    )
    assert profile_restores == []


async def test_recovery_never_restarts_a_paused_or_overheated_miner(
    hass: HomeAssistant,
) -> None:
    """Manual pauses and AxeOS thermal protection suppress automatic restarts."""
    clock = _Clock(datetime(2026, 7, 17, tzinfo=UTC))
    policy = RecoveryPolicy(
        automatic_recovery_enabled=True,
        startup_grace_seconds=0,
        consecutive_unhealthy_required=1,
    )
    miner = _miner(policy)
    miner_id = str(miner.identity.miner_id)
    snapshots = {
        miner_id: _snapshot(
            clock,
            hashrate=0.0,
            health=MinerHealth(mining_paused=True),
        )
    }
    outcomes = [RecoveryActionOutcome.REQUESTED]
    incidents: list[tuple[str, str, str]] = []
    profile_restores: list[str] = []
    engine = _engine(
        hass, miner, snapshots, clock, outcomes, incidents, profile_restores
    )

    await engine.async_evaluate(miner.identity.miner_id)
    snapshots[miner_id] = _snapshot(
        clock,
        hashrate=0.0,
        health=MinerHealth(overheat_mode=1),
    )
    await engine.async_evaluate(miner.identity.miner_id)

    assert outcomes == [RecoveryActionOutcome.REQUESTED]
    assert incidents == [
        ("thermal_safety", "detected", "AxeOS overheat protection is active")
    ]


async def test_recovery_restores_a_saved_profile_only_after_thermal_cooldown(
    hass: HomeAssistant,
) -> None:
    """Thermal restoration remains explicit, delayed, and never restarts the miner."""
    clock = _Clock(datetime(2026, 7, 17, tzinfo=UTC))
    policy = RecoveryPolicy(
        automatic_profile_restore_enabled=True,
        cooldown_seconds=30,
        overheat_policy=OverheatPolicy.RESTORE_AFTER_COOLDOWN,
    )
    miner = _miner(policy, with_profile=True)
    miner_id = str(miner.identity.miner_id)
    snapshots = {
        miner_id: _snapshot(
            clock,
            hashrate=0.0,
            health=MinerHealth(overheat_mode=1),
        )
    }
    outcomes = [RecoveryActionOutcome.REQUESTED]
    incidents: list[tuple[str, str, str]] = []
    profile_restores: list[str] = []
    engine = _engine(
        hass, miner, snapshots, clock, outcomes, incidents, profile_restores
    )

    await engine.async_evaluate(miner.identity.miner_id)
    clock.advance(1)
    snapshots[miner_id] = _snapshot(clock, hashrate=500.0)
    await engine.async_evaluate(miner.identity.miner_id)
    clock.advance(29)
    await engine.async_evaluate(miner.identity.miner_id)
    assert profile_restores == []

    clock.advance(1)
    await engine.async_evaluate(miner.identity.miner_id)

    assert profile_restores == [miner_id]
    assert outcomes == [RecoveryActionOutcome.REQUESTED]
    assert incidents[-1] == (
        "automatic_profile_restore",
        "verified",
        "after thermal cooldown",
    )


async def test_recovery_does_not_retry_an_uncertain_restart_or_exceed_its_limit(
    hass: HomeAssistant,
) -> None:
    """An ambiguous POST is counted once and never automatically retried."""
    clock = _Clock(datetime(2026, 7, 17, tzinfo=UTC))
    policy = RecoveryPolicy(
        automatic_recovery_enabled=True,
        startup_grace_seconds=0,
        consecutive_unhealthy_required=1,
        cooldown_seconds=0,
        max_attempts=1,
        post_restart_timeout_seconds=30,
    )
    miner = _miner(policy)
    miner_id = str(miner.identity.miner_id)
    snapshots = {miner_id: _snapshot(clock, hashrate=0.0)}
    outcomes = [RecoveryActionOutcome.UNCERTAIN]
    incidents: list[tuple[str, str, str]] = []
    profile_restores: list[str] = []
    engine = _engine(
        hass, miner, snapshots, clock, outcomes, incidents, profile_restores
    )

    await engine.async_evaluate(miner.identity.miner_id)
    clock.advance(30)
    await engine.async_evaluate(miner.identity.miner_id)
    await engine.async_evaluate(miner.identity.miner_id)

    assert outcomes == []
    assert incidents[0] == (
        "automatic_restart",
        "uncertain",
        "unhealthy condition: zero_hashrate",
    )
    assert incidents[-1] == (
        "automatic_restart",
        "suppressed",
        "rolling attempt limit reached",
    )


async def test_recovery_restores_the_rolling_attempt_budget_after_restart(
    hass: HomeAssistant,
) -> None:
    """Restarting Home Assistant cannot reset a miner's automatic restart budget."""
    clock = _Clock(datetime(2026, 7, 17, tzinfo=UTC))
    policy = RecoveryPolicy(
        automatic_recovery_enabled=True,
        startup_grace_seconds=0,
        consecutive_unhealthy_required=1,
        cooldown_seconds=0,
        max_attempts=1,
    )
    miner = _miner(policy)
    miner_id = str(miner.identity.miner_id)
    snapshots = {miner_id: _snapshot(clock, hashrate=0.0)}
    outcomes = [RecoveryActionOutcome.REQUESTED]
    incidents: list[tuple[str, str, str]] = []
    profile_restores: list[str] = []
    prior_incidents = (
        FleetIncident(
            incident_id="prior-restart",
            miner_id=miner.identity.miner_id,
            occurred_at=clock.now(),
            cause="automatic_restart",
            outcome="requested",
            detail="unhealthy condition: zero_hashrate",
        ),
    )
    engine = _engine(
        hass,
        miner,
        snapshots,
        clock,
        outcomes,
        incidents,
        profile_restores,
        prior_incidents,
    )

    await engine.async_evaluate(miner.identity.miner_id)

    assert outcomes == [RecoveryActionOutcome.REQUESTED]
    assert incidents == [
        ("automatic_restart", "suppressed", "rolling attempt limit reached")
    ]
