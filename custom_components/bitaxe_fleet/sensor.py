"""Native Home Assistant sensors for enrolled Bitaxe miners."""

from __future__ import annotations

from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfPower, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import MinerCoordinator
from .entity import BitaxeFleetMinerEntity
from .runtime import BitaxeFleetConfigEntry

SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="hashrate",
        translation_key="hashrate",
        icon="mdi:speedometer",
        native_unit_of_measurement="GH/s",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="power",
        translation_key="power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BitaxeFleetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for every currently enrolled miner."""

    def _async_add_miner(coordinator: MinerCoordinator) -> None:
        """Create sensors after discovery approval without rebuilding the fleet."""
        async_add_entities(
            [
                BitaxeSensor(coordinator, description)
                for description in SENSOR_DESCRIPTIONS
            ]
        )

    async_add_entities(
        [
            BitaxeSensor(coordinator, description)
            for coordinator in entry.runtime_data.coordinators.values()
            for description in SENSOR_DESCRIPTIONS
        ]
    )
    entry.async_on_unload(
        async_dispatcher_connect(
            hass, entry.runtime_data.miner_added_signal, _async_add_miner
        )
    )


class BitaxeSensor(BitaxeFleetMinerEntity, SensorEntity):
    """One optional measurement from a validated miner snapshot."""

    entity_description: SensorEntityDescription

    def __init__(
        self, coordinator: MinerCoordinator, description: SensorEntityDescription
    ) -> None:
        """Initialize the sensor from its description and coordinator."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    @override
    def native_value(self) -> float | None:
        """Return the selected optional telemetry value without fabricated zeros."""
        snapshot = self.coordinator.snapshot
        if snapshot is None:
            return None
        if self.entity_description.key == "hashrate":
            return snapshot.telemetry.hashrate_gh_s
        if self.entity_description.key == "power":
            return snapshot.telemetry.power_w
        if self.entity_description.key == "temperature":
            return snapshot.telemetry.temperature_c
        return None
