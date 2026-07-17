"""Shared entity behavior for Bitaxe Fleet miner entities."""

from __future__ import annotations

from typing import override

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import MinerCoordinator


class BitaxeFleetMinerEntity(CoordinatorEntity[MinerCoordinator]):
    """Base entity linked to one stable MAC-keyed miner device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MinerCoordinator, key: str) -> None:
        """Initialize stable entity identity for one metric."""
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{str(coordinator.miner.identity.miner_id).replace(':', '')}_{key}"
        )

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Return the miner device linked to the persistent fleet hub device."""
        snapshot = self.coordinator.snapshot
        if snapshot is None:
            endpoint = self.coordinator.miner.endpoint
            identity = self.coordinator.miner.identity
        else:
            endpoint = snapshot.endpoint
            identity = snapshot.identity

        return DeviceInfo(
            configuration_url=endpoint.base_url,
            connections={(dr.CONNECTION_NETWORK_MAC, str(identity.miner_id))},
            identifiers={(DOMAIN, str(identity.miner_id))},
            manufacturer=MANUFACTURER,
            model=identity.asic_model or identity.board_version,
            name=identity.display_name,
            sw_version=identity.firmware_version,
            via_device=(DOMAIN, self.coordinator.entry_id),
        )
