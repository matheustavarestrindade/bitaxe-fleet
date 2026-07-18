"""Native Home Assistant health binary sensors for enrolled Bitaxe miners."""

from __future__ import annotations

from typing import override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import MinerCoordinator
from .entity import BitaxeFleetMinerEntity
from .runtime import BitaxeFleetConfigEntry

BINARY_SENSOR_DESCRIPTIONS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="mining",
        translation_key="mining",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    BinarySensorEntityDescription(
        key="fallback_pool",
        translation_key="fallback_pool",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    BinarySensorEntityDescription(
        key="overheating",
        translation_key="overheating",
        device_class=BinarySensorDeviceClass.HEAT,
    ),
    BinarySensorEntityDescription(
        key="power_fault",
        translation_key="power_fault",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    BinarySensorEntityDescription(
        key="hardware_fault",
        translation_key="hardware_fault",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BitaxeFleetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up health sensors for every currently enrolled miner."""

    @callback
    def _async_add_miner(coordinator: MinerCoordinator) -> None:
        """Create health sensors after approval without rebuilding the fleet."""
        async_add_entities(
            [
                BitaxeBinarySensor(coordinator, description)
                for description in BINARY_SENSOR_DESCRIPTIONS
            ]
        )

    async_add_entities(
        [
            BitaxeBinarySensor(coordinator, description)
            for coordinator in entry.runtime_data.coordinators.values()
            for description in BINARY_SENSOR_DESCRIPTIONS
        ]
    )
    entry.async_on_unload(
        async_dispatcher_connect(
            hass, entry.runtime_data.miner_added_signal, _async_add_miner
        )
    )


class BitaxeBinarySensor(BitaxeFleetMinerEntity, BinarySensorEntity):
    """One optional health state from a validated miner snapshot."""

    entity_description: BinarySensorEntityDescription

    def __init__(
        self, coordinator: MinerCoordinator, description: BinarySensorEntityDescription
    ) -> None:
        """Initialize the health sensor from its description and coordinator."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    @override
    def is_on(self) -> bool | None:
        """Return health states only when the current firmware exposes them."""
        snapshot = self.coordinator.snapshot
        if snapshot is None:
            return None
        health = snapshot.health
        match self.entity_description.key:
            case "mining":
                return (
                    not health.mining_paused
                    if health.mining_paused is not None
                    else None
                )
            case "fallback_pool":
                return health.using_fallback_pool
            case "overheating":
                return (
                    health.overheat_mode != 0
                    if health.overheat_mode is not None
                    else None
                )
            case "power_fault":
                return health.power_fault is not None
            case "hardware_fault":
                return health.hardware_fault is not None
        return None
