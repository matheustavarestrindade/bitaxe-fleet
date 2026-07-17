"""Per-miner coordinators backed by validated AxeOS snapshots."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, override

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .axeos.client import AxeOSClientProtocol
from .axeos.errors import AxeOSError
from .axeos.models import EnrolledMiner, MinerSnapshot
from .const import DOMAIN, MINER_POLL_INTERVAL
from .storage import MinerRegistry

if TYPE_CHECKING:
    from .runtime import BitaxeFleetConfigEntry

_LOGGER = logging.getLogger(__name__)


class MinerCoordinator(DataUpdateCoordinator[MinerSnapshot]):
    """Poll one enrolled miner without letting transport data reach entities."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: BitaxeFleetConfigEntry,
        miner: EnrolledMiner,
        client: AxeOSClientProtocol,
        registry: MinerRegistry,
    ) -> None:
        """Initialize a coordinator for one stable miner identity."""
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
        self._client = client
        self._has_snapshot = False
        self._registry = registry

    @property
    def snapshot(self) -> MinerSnapshot | None:
        """Return a snapshot only after at least one successful update."""
        if not self._has_snapshot or not self.last_update_success:
            return None
        return self.data

    @override
    async def _async_update_data(self) -> MinerSnapshot:
        """Fetch a fresh snapshot and persist only validated enrolled metadata."""
        try:
            snapshot = await self._client.async_get_system_info()
        except AxeOSError as err:
            raise UpdateFailed(str(err)) from err

        await self._registry.async_update_from_snapshot(snapshot)
        self._has_snapshot = True
        return snapshot
