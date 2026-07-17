"""Runtime data owned by a Bitaxe Fleet config entry."""

from __future__ import annotations

from dataclasses import dataclass, field

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .axeos.client import AxeOSClient
from .axeos.models import MinerEndpoint, MinerId, MinerSnapshot
from .axeos.parser import parse_private_ipv4
from .coordinator import MinerCoordinator
from .storage import MinerRegistry


@dataclass(slots=True)
class BitaxeFleetRuntime:
    """Own resources that exist only while the fleet entry is loaded."""

    entry_id: str
    registry: MinerRegistry
    session: aiohttp.ClientSession
    coordinators: dict[MinerId, MinerCoordinator] = field(default_factory=dict)
    _closed: bool = field(default=False, init=False, repr=False)

    @classmethod
    async def async_create(
        cls, hass: HomeAssistant, entry_id: str
    ) -> BitaxeFleetRuntime:
        """Load persistent enrollment data and create runtime resources."""
        registry = MinerRegistry(hass, entry_id)
        await registry.async_load()
        return cls(
            entry_id=entry_id,
            registry=registry,
            session=async_get_clientsession(hass),
        )

    async def async_start_miners(
        self, hass: HomeAssistant, entry: BitaxeFleetConfigEntry
    ) -> None:
        """Create a coordinator for every persisted enrolled miner."""
        for miner in self.registry.miners:
            coordinator = MinerCoordinator(
                hass,
                entry,
                miner,
                AxeOSClient(self.session, miner.endpoint),
                self.registry,
            )
            self.coordinators[miner.identity.miner_id] = coordinator
            await coordinator.async_refresh()

    async def async_enroll_host(self, host: str) -> MinerSnapshot:
        """Validate and enroll an administrator-supplied private IPv4 miner."""
        endpoint = MinerEndpoint(host=parse_private_ipv4(host))
        client = AxeOSClient(self.session, endpoint)
        snapshot = await client.async_get_system_info()
        await self.registry.async_enroll(snapshot)
        return snapshot

    @property
    def is_closed(self) -> bool:
        """Return whether runtime resources have been released."""
        return self._closed

    async def async_close(self) -> None:
        """Release runtime resources exactly once."""
        if self._closed:
            return

        self._closed = True
        for coordinator in self.coordinators.values():
            await coordinator.async_shutdown()
        self.coordinators.clear()


type BitaxeFleetConfigEntry = ConfigEntry[BitaxeFleetRuntime]
