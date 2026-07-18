"""Per-miner coordinators that preserve MAC identity across endpoint changes."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, override

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .axeos.client import AxeOSClientProtocol
from .axeos.errors import AxeOSError
from .axeos.models import (
    AsicCapabilities,
    EnrolledMiner,
    MinerEndpoint,
    MinerSnapshot,
    RecoveryProfile,
)
from .const import DOMAIN, MINER_POLL_INTERVAL
from .storage import MinerRegistry

if TYPE_CHECKING:
    from .runtime import BitaxeFleetConfigEntry

_LOGGER = logging.getLogger(__name__)


class MinerCoordinator(DataUpdateCoordinator[MinerSnapshot]):
    """Poll one approved MAC identity through its current mutable endpoint."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: BitaxeFleetConfigEntry,
        miner: EnrolledMiner,
        make_client: Callable[[MinerEndpoint], AxeOSClientProtocol],
        registry: MinerRegistry,
    ) -> None:
        """Initialize one coordinator with an explicit config-entry lifecycle owner."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {miner.identity.display_name}",
            update_interval=MINER_POLL_INTERVAL,
            always_update=False,
        )
        self.entry_id = entry.entry_id
        self.miner = miner
        self._action_lock = asyncio.Lock()
        self._capabilities: AsicCapabilities | None = None
        self._client = make_client(miner.endpoint)
        self._has_snapshot = False
        self._last_success_at: datetime | None = None
        self._make_client = make_client
        self._registry = registry

    @property
    def action_lock(self) -> asyncio.Lock:
        """Return the single lock that serializes all mutating miner operations."""
        return self._action_lock

    @property
    def capabilities(self) -> AsicCapabilities | None:
        """Return the most recent validated ASIC capability response."""
        return self._capabilities

    @property
    def last_success_at(self) -> datetime | None:
        """Return when the coordinator last received a valid same-MAC snapshot."""
        return self._last_success_at

    @property
    def snapshot(self) -> MinerSnapshot | None:
        """Keep the last known-good snapshot while availability reports freshness."""
        if not self._has_snapshot:
            return None
        return self.data

    async def async_replace_enrollment(self, miner: EnrolledMiner) -> None:
        """Atomically replace endpoint metadata after same-MAC rediscovery."""
        if miner.identity.miner_id != self.miner.identity.miner_id:
            raise ValueError("cannot replace a coordinator with another miner identity")
        async with self._action_lock:
            self.miner = miner
            self._client = self._make_client(miner.endpoint)
            self._capabilities = None

    def async_apply_discovered_snapshot(self, snapshot: MinerSnapshot) -> None:
        """Publish a same-MAC discovery observation without a duplicate HTTP read."""
        if snapshot.identity.miner_id != self.miner.identity.miner_id:
            raise ValueError("cannot publish a different miner identity")
        self._has_snapshot = True
        self._last_success_at = datetime.now(UTC)
        self.async_set_updated_data(snapshot)

    async def async_get_capabilities(
        self, *, force_refresh: bool = False
    ) -> AsicCapabilities:
        """Fetch model capabilities only when required for a safe profile action."""
        if self._capabilities is not None and not force_refresh:
            return self._capabilities
        capabilities = await self._client.async_get_system_asic()
        self._capabilities = capabilities
        return capabilities

    async def async_get_logs(self) -> str:
        """Fetch bounded logs through the typed client for diagnostics or incidents."""
        return (await self._client.async_get_system_logs()).text

    async def async_patch_profile(self, profile: RecoveryProfile) -> None:
        """Apply a closed profile while the caller owns ``action_lock``."""
        await self._client.async_patch_system(profile)

    async def async_call_client_action(self, action: str) -> None:
        """Verify the enrolled MAC immediately before one named mutation."""
        async with self._action_lock:
            await self.async_refresh()
            if self.snapshot is None or not self.last_update_success:
                raise UpdateFailed("Miner could not be read before the action")
            if action == "restart":
                await self._client.async_restart()
                return
            if action == "pause":
                await self._client.async_pause()
                return
            if action == "resume":
                await self._client.async_resume()
                return
            if action == "identify":
                await self._client.async_identify()
                return
        raise ValueError("unsupported miner action")

    @override
    async def _async_update_data(self) -> MinerSnapshot:
        """Fetch only a same-MAC snapshot and retain known-good data on errors."""
        try:
            snapshot = await self._client.async_get_system_info()
        except AxeOSError as err:
            raise UpdateFailed(str(err)) from err

        if snapshot.identity.miner_id != self.miner.identity.miner_id:
            raise UpdateFailed("A different Bitaxe responded at the enrolled endpoint")

        updated = await self._registry.async_update_from_snapshot(snapshot)
        if updated is not None:
            self.miner = updated
        self._has_snapshot = True
        self._last_success_at = datetime.now(UTC)
        return snapshot
