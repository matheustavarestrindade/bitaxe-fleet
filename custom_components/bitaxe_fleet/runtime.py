"""Typed runtime ownership for one Bitaxe Fleet config entry."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import UpdateFailed

from .aggregates import FleetAggregates, calculate_fleet_aggregates
from .axeos.client import AxeOSClient
from .axeos.errors import AxeOSError, AxeOSMutationUncertainError
from .axeos.models import (
    EnrolledMiner,
    MinerEndpoint,
    MinerId,
    MinerSnapshot,
    RecoveryPolicy,
    RecoveryProfile,
)
from .axeos.parser import parse_private_ipv4
from .coordinator import MinerCoordinator
from .discovery.manager import DiscoveryManager
from .discovery.models import DiscoveryCandidate, DiscoveryScanStatus
from .recovery import RecoveryActionOutcome, RecoveryEngine
from .storage import MinerRegistry


class FleetActionError(Exception):
    """A safe user-facing failure from a validated fleet operation."""


@dataclass(slots=True)
class BitaxeFleetRuntime:
    """Own all live resources for one singleton fleet config entry."""

    hass: HomeAssistant
    entry_id: str
    registry: MinerRegistry
    session: aiohttp.ClientSession
    coordinators: dict[MinerId, MinerCoordinator] = field(default_factory=dict)
    recovery: RecoveryEngine = field(init=False)
    discovery: DiscoveryManager | None = field(default=None, init=False)
    _recovery_unsubscribers: dict[MinerId, Callable[[], None]] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )
    _fleet_unsubscribers: dict[MinerId, Callable[[], None]] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )
    _fleet_aggregates: FleetAggregates = field(
        default_factory=FleetAggregates.empty,
        init=False,
        repr=False,
    )
    _closed: bool = field(default=False, init=False, repr=False)

    @classmethod
    async def async_create(
        cls, hass: HomeAssistant, entry_id: str
    ) -> BitaxeFleetRuntime:
        """Load persisted state and create resources owned by this config entry."""
        registry = MinerRegistry(hass, entry_id)
        await registry.async_load()
        runtime = cls(
            hass=hass,
            entry_id=entry_id,
            registry=registry,
            session=async_get_clientsession(hass),
        )
        runtime.recovery = RecoveryEngine(
            hass,
            registry.get,
            runtime._snapshot_for_recovery,
            runtime._async_restart_for_recovery,
            runtime._async_restore_profile_for_recovery,
            registry.async_record_incident,
            incident_provider=lambda: registry.incidents,
        )
        return runtime

    @property
    def is_closed(self) -> bool:
        """Return whether runtime resources have been released."""
        return self._closed

    @property
    def miner_added_signal(self) -> str:
        """Return the entry-specific dispatcher signal used by entity platforms."""
        return f"bitaxe_fleet_miner_added_{self.entry_id}"

    @property
    def fleet_updated_signal(self) -> str:
        """Return the entry-specific dispatcher signal for cached fleet metrics."""
        return f"bitaxe_fleet_updated_{self.entry_id}"

    @property
    def fleet_aggregates(self) -> FleetAggregates:
        """Return the latest cached totals calculated from fresh snapshots only."""
        return self._fleet_aggregates

    @property
    def candidates(self) -> tuple[DiscoveryCandidate, ...]:
        """Return pending explicit-approval discovery candidates."""
        if self.discovery is None:
            return ()
        return self.discovery.candidates

    @property
    def scan_status(self) -> DiscoveryScanStatus:
        """Return active scan progress or an idle status before setup completes."""
        if self.discovery is None:
            return DiscoveryScanStatus.idle()
        return self.discovery.scan_status

    async def async_start(self, entry: BitaxeFleetConfigEntry) -> None:
        """Start coordinators and mDNS discovery after config-entry setup begins."""
        for miner in self.registry.miners:
            if miner.enabled:
                await self.async_start_miner(entry, miner, notify_platforms=False)

        self._async_refresh_fleet_aggregates()

        self.discovery = DiscoveryManager(
            self.hass,
            self.registry,
            self._make_client,
            self._async_handle_known_snapshot,
            self._async_handle_approved_miner,
        )
        await self.discovery.async_start()

    async def async_start_miner(
        self,
        entry: BitaxeFleetConfigEntry,
        miner: EnrolledMiner,
        *,
        notify_platforms: bool,
    ) -> MinerCoordinator:
        """Create or update one coordinator while retaining its MAC-based identity."""
        miner_id = miner.identity.miner_id
        existing = self.coordinators.get(miner_id)
        if existing is not None:
            await existing.async_replace_enrollment(miner)
            await existing.async_refresh()
            return existing

        coordinator = MinerCoordinator(
            self.hass,
            entry,
            miner,
            self._make_client,
            self.registry,
        )
        self.coordinators[miner_id] = coordinator
        self._recovery_unsubscribers[miner_id] = coordinator.async_add_listener(
            lambda: self.recovery.async_schedule(miner_id)
        )
        self._fleet_unsubscribers[miner_id] = coordinator.async_add_listener(
            self._async_refresh_fleet_aggregates
        )
        await coordinator.async_refresh()
        if notify_platforms:
            async_dispatcher_send(self.hass, self.miner_added_signal, coordinator)
        return coordinator

    async def async_enroll_host(self, host: str) -> MinerSnapshot:
        """Validate and explicitly approve one administrator-supplied private host."""
        endpoint = MinerEndpoint(host=parse_private_ipv4(host))
        snapshot = await self._make_client(endpoint).async_get_system_info()
        miner = await self.registry.async_enroll(snapshot)
        await self.async_start_miner(self._entry(), miner, notify_platforms=True)
        return snapshot

    def async_start_scan(self, network: str) -> DiscoveryScanStatus:
        """Start an administrator-requested bounded private-network scan."""
        if self.discovery is None:
            raise RuntimeError("discovery is not running")
        return self.discovery.async_start_scan(network)

    async def async_approve_candidate(self, miner_id: MinerId) -> EnrolledMiner:
        """Revalidate and explicitly approve a discovered miner MAC."""
        if self.discovery is None:
            raise RuntimeError("discovery is not running")
        return await self.discovery.async_approve_candidate(miner_id)

    async def async_reject_candidate(self, miner_id: MinerId) -> None:
        """Persist an explicit discovery rejection for one candidate identity."""
        if self.discovery is None:
            raise RuntimeError("discovery is not running")
        await self.discovery.async_reject_candidate(miner_id)

    async def async_remove_miner(self, miner_id: MinerId) -> bool:
        """Remove a miner from persistent state and stop its live coordinator."""
        self.recovery.async_forget_miner(miner_id)
        unsubscribe = self._recovery_unsubscribers.pop(miner_id, None)
        if unsubscribe is not None:
            unsubscribe()
        fleet_unsubscribe = self._fleet_unsubscribers.pop(miner_id, None)
        if fleet_unsubscribe is not None:
            fleet_unsubscribe()
        coordinator = self.coordinators.pop(miner_id, None)
        if coordinator is not None:
            await coordinator.async_shutdown()
        removed = await self.registry.async_remove(miner_id)
        self._async_refresh_fleet_aggregates()
        return removed

    async def async_run_action(self, miner_id: MinerId, action: str) -> None:
        """Run one explicit restart, pause, resume, or identify request safely."""
        coordinator = self._require_coordinator(miner_id)
        try:
            await coordinator.async_call_client_action(action)
        except AxeOSMutationUncertainError as err:
            await self.registry.async_record_incident(
                miner_id, "manual_action", "uncertain", action
            )
            raise FleetActionError("miner action outcome is uncertain") from err
        except (AxeOSError, UpdateFailed) as err:
            await self.registry.async_record_incident(
                miner_id, "manual_action", "failed", action
            )
            raise FleetActionError("miner action failed") from err
        await self.registry.async_record_incident(
            miner_id, "manual_action", "requested", action
        )

    async def async_capture_profile(self, miner_id: MinerId) -> RecoveryProfile:
        """Capture values only after a fresh capability-checked read."""
        coordinator = self._require_coordinator(miner_id)
        async with coordinator.action_lock:
            snapshot = await self._async_fresh_snapshot(coordinator)
            profile = snapshot.configuration.to_recovery_profile()
            if profile is None:
                raise FleetActionError("miner does not expose every recovery setting")
            try:
                capabilities = await coordinator.async_get_capabilities(
                    force_refresh=True
                )
            except AxeOSError as err:
                raise FleetActionError("miner capabilities could not be read") from err
            if not capabilities.supports_profile(profile):
                raise FleetActionError("miner does not support its current profile")
            await self.registry.async_set_recovery_profile(miner_id, profile)
        await self.registry.async_record_incident(
            miner_id, "profile_capture", "captured", "six approved settings"
        )
        return profile

    async def async_apply_profile(self, miner_id: MinerId) -> None:
        """Patch only a saved closed profile and verify its read-back value by value."""
        coordinator = self._require_coordinator(miner_id)
        miner = self.registry.get(miner_id)
        if miner is None or miner.recovery_profile is None:
            raise FleetActionError("miner has no saved recovery profile")
        profile = miner.recovery_profile

        async with coordinator.action_lock:
            await self._async_fresh_snapshot(coordinator)
            try:
                capabilities = await coordinator.async_get_capabilities(
                    force_refresh=True
                )
            except AxeOSError as err:
                raise FleetActionError("miner capabilities could not be read") from err
            if not capabilities.supports_profile(profile):
                raise FleetActionError("saved profile is not supported by this miner")
            try:
                await coordinator.async_patch_profile(profile)
            except AxeOSMutationUncertainError as err:
                current = await self._async_fresh_snapshot(coordinator)
                if current.configuration.to_recovery_profile() != profile:
                    await self.registry.async_record_incident(
                        miner_id,
                        "profile_apply",
                        "uncertain",
                        "read-back did not match",
                    )
                    raise FleetActionError("profile outcome is uncertain") from err
            except AxeOSError as err:
                await self.registry.async_record_incident(
                    miner_id, "profile_apply", "failed", "patch request failed"
                )
                raise FleetActionError("profile could not be applied") from err
            else:
                current = await self._async_fresh_snapshot(coordinator)
                if current.configuration.to_recovery_profile() != profile:
                    await self.registry.async_record_incident(
                        miner_id, "profile_apply", "drift", "read-back did not match"
                    )
                    raise FleetActionError("profile read-back did not match")
        await self.registry.async_record_incident(
            miner_id, "profile_apply", "verified", "six approved settings"
        )

    async def async_set_recovery_policy(
        self, miner_id: MinerId, policy: RecoveryPolicy
    ) -> EnrolledMiner:
        """Persist one validated policy before any automatic recovery is considered."""
        try:
            miner = await self.registry.async_set_recovery_policy(miner_id, policy)
        except (KeyError, ValueError) as err:
            raise FleetActionError(
                "miner recovery policy could not be updated"
            ) from err
        self.recovery.async_forget_miner(miner_id)
        return miner

    async def async_get_logs(self, miner_id: MinerId) -> str:
        """Fetch bounded logs from an enabled approved miner."""
        coordinator = self._require_coordinator(miner_id)
        try:
            return await coordinator.async_get_logs()
        except AxeOSError as err:
            raise FleetActionError("miner logs could not be read") from err

    async def async_set_enabled(
        self, miner_id: MinerId, enabled: bool
    ) -> EnrolledMiner:
        """Enable or disable a miner and its live coordinator deterministically."""
        miner = await self.registry.async_set_enabled(miner_id, enabled)
        coordinator = self.coordinators.get(miner_id)
        if not enabled:
            self.recovery.async_forget_miner(miner_id)
            unsubscribe = self._recovery_unsubscribers.pop(miner_id, None)
            if unsubscribe is not None:
                unsubscribe()
            fleet_unsubscribe = self._fleet_unsubscribers.pop(miner_id, None)
            if fleet_unsubscribe is not None:
                fleet_unsubscribe()
        if not enabled and coordinator is not None:
            await coordinator.async_shutdown()
            self.coordinators.pop(miner_id, None)
        if enabled and coordinator is None:
            await self.async_start_miner(self._entry(), miner, notify_platforms=True)
        self._async_refresh_fleet_aggregates()
        return miner

    def get_coordinator(self, miner_id: MinerId) -> MinerCoordinator | None:
        """Return a live coordinator only for an enabled enrolled miner."""
        return self.coordinators.get(miner_id)

    def _require_coordinator(self, miner_id: MinerId) -> MinerCoordinator:
        """Return an enabled live coordinator or a safe application failure."""
        coordinator = self.coordinators.get(miner_id)
        if coordinator is None:
            raise FleetActionError("miner is unavailable or disabled")
        return coordinator

    async def _async_fresh_snapshot(
        self, coordinator: MinerCoordinator
    ) -> MinerSnapshot:
        """Force a same-MAC refresh and reject stale data before a mutation."""
        await coordinator.async_refresh()
        snapshot = coordinator.snapshot
        if snapshot is None or not coordinator.last_update_success:
            raise FleetActionError("miner could not be read")
        return snapshot

    async def async_close(self) -> None:
        """Release discovery tasks and coordinator resources exactly once."""
        if self._closed:
            return
        self._closed = True
        if self.discovery is not None:
            await self.discovery.async_stop()
            self.discovery = None
        await self.recovery.async_close()
        for unsubscribe in self._recovery_unsubscribers.values():
            unsubscribe()
        self._recovery_unsubscribers.clear()
        for unsubscribe in self._fleet_unsubscribers.values():
            unsubscribe()
        self._fleet_unsubscribers.clear()
        for coordinator in self.coordinators.values():
            await coordinator.async_shutdown()
        self.coordinators.clear()

    def _make_client(self, endpoint: MinerEndpoint) -> AxeOSClient:
        """Construct a short-lived typed client for one validated endpoint."""
        return AxeOSClient(self.session, endpoint)

    def _snapshot_for_recovery(self, miner_id: MinerId) -> MinerSnapshot | None:
        """Return only a same-MAC coordinator snapshot to the recovery engine."""
        coordinator = self.coordinators.get(miner_id)
        if coordinator is None or not coordinator.last_update_success:
            return None
        return coordinator.snapshot

    @callback
    def _async_refresh_fleet_aggregates(self) -> None:
        """Cache linear fleet totals and notify entities after coordinator updates."""
        enabled_miners = tuple(miner for miner in self.registry.miners if miner.enabled)
        snapshots: list[MinerSnapshot] = []
        for miner in enabled_miners:
            coordinator = self.coordinators.get(miner.identity.miner_id)
            if coordinator is None or not coordinator.last_update_success:
                continue
            snapshot = coordinator.snapshot
            if snapshot is not None:
                snapshots.append(snapshot)
        self._fleet_aggregates = calculate_fleet_aggregates(
            len(enabled_miners), tuple(snapshots)
        )
        async_dispatcher_send(self.hass, self.fleet_updated_signal)

    async def _async_restart_for_recovery(
        self, miner_id: MinerId
    ) -> RecoveryActionOutcome:
        """Run one identity-verified restart without retrying uncertain delivery."""
        coordinator = self.coordinators.get(miner_id)
        if coordinator is None:
            return RecoveryActionOutcome.FAILED
        try:
            await coordinator.async_call_client_action("restart")
        except AxeOSMutationUncertainError:
            return RecoveryActionOutcome.UNCERTAIN
        except AxeOSError, UpdateFailed:
            return RecoveryActionOutcome.FAILED
        return RecoveryActionOutcome.REQUESTED

    async def _async_restore_profile_for_recovery(self, miner_id: MinerId) -> bool:
        """Apply an explicitly saved profile through the normal read-back boundary."""
        try:
            await self.async_apply_profile(miner_id)
        except FleetActionError:
            return False
        return True

    async def _async_handle_known_snapshot(
        self, snapshot: MinerSnapshot, miner: EnrolledMiner
    ) -> None:
        """Move an existing same-MAC coordinator to its newly validated endpoint."""
        if not miner.enabled:
            return
        entry = self._entry()
        coordinator = self.coordinators.get(miner.identity.miner_id)
        if coordinator is None:
            await self.async_start_miner(entry, miner, notify_platforms=True)
            return
        await coordinator.async_replace_enrollment(miner)
        coordinator.async_apply_discovered_snapshot(snapshot)

    async def _async_handle_approved_miner(self, miner: EnrolledMiner) -> None:
        """Start a coordinator and entities immediately after administrator approval."""
        if miner.enabled:
            await self.async_start_miner(self._entry(), miner, notify_platforms=True)

    def _entry(self) -> BitaxeFleetConfigEntry:
        """Return this runtime's active config entry with typed runtime data."""
        entry = self.hass.config_entries.async_get_entry(self.entry_id)
        if not isinstance(entry, ConfigEntry):
            raise RuntimeError("Bitaxe Fleet config entry is unavailable")
        runtime_data = entry.runtime_data
        if runtime_data is not self:
            raise RuntimeError("Bitaxe Fleet runtime is unavailable")
        return entry


type BitaxeFleetConfigEntry = ConfigEntry[BitaxeFleetRuntime]
