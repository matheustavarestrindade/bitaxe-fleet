"""Native Home Assistant sensors for enrolled Bitaxe miners."""

from __future__ import annotations

from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .aggregates import FleetAggregates
from .const import DOMAIN
from .coordinator import MinerCoordinator
from .entity import BitaxeFleetMinerEntity
from .runtime import BitaxeFleetConfigEntry, BitaxeFleetRuntime

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
    SensorEntityDescription(
        key="hashrate_1m",
        translation_key="hashrate_1m",
        icon="mdi:speedometer",
        native_unit_of_measurement="GH/s",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="hashrate_10m",
        translation_key="hashrate_10m",
        icon="mdi:speedometer",
        native_unit_of_measurement="GH/s",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="hashrate_1h",
        translation_key="hashrate_1h",
        icon="mdi:speedometer",
        native_unit_of_measurement="GH/s",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="expected_hashrate",
        translation_key="expected_hashrate",
        icon="mdi:speedometer-medium",
        native_unit_of_measurement="GH/s",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="error_percentage",
        translation_key="error_percentage",
        icon="mdi:percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="voltage",
        translation_key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="current",
        translation_key="current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="secondary_temperature",
        translation_key="secondary_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="vr_temperature",
        translation_key="vr_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="frequency",
        translation_key="frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.MEGAHERTZ,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="actual_frequency",
        translation_key="actual_frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.MEGAHERTZ,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="core_voltage",
        translation_key="core_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="fan_speed",
        translation_key="fan_speed",
        icon="mdi:fan",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="fan_rpm",
        translation_key="fan_rpm",
        icon="mdi:fan",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="fan_2_rpm",
        translation_key="fan_2_rpm",
        icon="mdi:fan",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="shares_accepted",
        translation_key="shares_accepted",
        icon="mdi:check-circle-outline",
        native_unit_of_measurement="shares",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="shares_rejected",
        translation_key="shares_rejected",
        icon="mdi:close-circle-outline",
        native_unit_of_measurement="shares",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="best_difficulty",
        translation_key="best_difficulty",
        icon="mdi:trophy-outline",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="best_session_difficulty",
        translation_key="best_session_difficulty",
        icon="mdi:trophy-outline",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pool_difficulty",
        translation_key="pool_difficulty",
        icon="mdi:pool",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pool_response_time",
        translation_key="pool_response_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="wifi_signal",
        translation_key="wifi_signal",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement="dBm",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="uptime",
        translation_key="uptime",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="block_height",
        translation_key="block_height",
        icon="mdi:bitcoin",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="network_difficulty",
        translation_key="network_difficulty",
        icon="mdi:chart-line",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="blocks_found",
        translation_key="blocks_found",
        icon="mdi:bitcoin",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)

FLEET_SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="total_hashrate",
        translation_key="total_hashrate",
        icon="mdi:speedometer",
        native_unit_of_measurement="GH/s",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="total_hashrate_th",
        translation_key="total_hashrate_th",
        icon="mdi:speedometer",
        native_unit_of_measurement="TH/s",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="total_power",
        translation_key="total_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="efficiency",
        translation_key="efficiency",
        icon="mdi:lightning-bolt-circle",
        native_unit_of_measurement="J/TH",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="total_uptime",
        translation_key="total_uptime",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="best_difficulty",
        translation_key="fleet_best_difficulty",
        icon="mdi:trophy-outline",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="best_session_difficulty",
        translation_key="fleet_best_session_difficulty",
        icon="mdi:trophy-outline",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="online_miners",
        translation_key="online_miners",
        icon="mdi:access-point-check",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="unhealthy_miners",
        translation_key="unhealthy_miners",
        icon="mdi:alert-circle-outline",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="overheating_miners",
        translation_key="overheating_miners",
        icon="mdi:thermometer-alert",
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BitaxeFleetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for every currently enrolled miner."""

    @callback
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
            BitaxeFleetAggregateSensor(entry.runtime_data, description)
            for description in FLEET_SENSOR_DESCRIPTIONS
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
    def native_value(self) -> float | int | None:
        """Return the selected optional telemetry value without fabricated zeros."""
        snapshot = self.coordinator.snapshot
        if snapshot is None:
            return None
        telemetry = snapshot.telemetry
        match self.entity_description.key:
            case "hashrate":
                return telemetry.hashrate_gh_s
            case "power":
                return telemetry.power_w
            case "temperature":
                return telemetry.temperature_c
            case "hashrate_1m":
                return telemetry.hashrate_1m_gh_s
            case "hashrate_10m":
                return telemetry.hashrate_10m_gh_s
            case "hashrate_1h":
                return telemetry.hashrate_1h_gh_s
            case "expected_hashrate":
                return telemetry.expected_hashrate_gh_s
            case "error_percentage":
                return telemetry.error_percentage
            case "voltage":
                return (
                    telemetry.input_voltage_mv / 1000
                    if telemetry.input_voltage_mv is not None
                    else None
                )
            case "current":
                return (
                    telemetry.current_ma / 1000
                    if telemetry.current_ma is not None
                    else None
                )
            case "secondary_temperature":
                return telemetry.secondary_temperature_c
            case "vr_temperature":
                return telemetry.vr_temperature_c
            case "frequency":
                return snapshot.configuration.frequency_mhz
            case "actual_frequency":
                return telemetry.actual_frequency_mhz
            case "core_voltage":
                return telemetry.core_voltage_actual_mv
            case "fan_speed":
                return telemetry.fan_speed_percent
            case "fan_rpm":
                return telemetry.fan_rpm
            case "fan_2_rpm":
                return telemetry.fan_2_rpm
            case "shares_accepted":
                return telemetry.shares_accepted
            case "shares_rejected":
                return telemetry.shares_rejected
            case "best_difficulty":
                return telemetry.best_difficulty
            case "best_session_difficulty":
                return telemetry.best_session_difficulty
            case "pool_difficulty":
                return telemetry.pool_difficulty
            case "pool_response_time":
                return telemetry.pool_response_time_ms
            case "wifi_signal":
                return telemetry.wifi_rssi_dbm
            case "uptime":
                return telemetry.uptime_seconds
            case "block_height":
                return telemetry.block_height
            case "network_difficulty":
                return telemetry.network_difficulty
            case "blocks_found":
                return telemetry.blocks_found
        return None


class BitaxeFleetAggregateSensor(SensorEntity):
    """One cached aggregate linked to the persistent fleet hub device."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    entity_description: SensorEntityDescription

    def __init__(
        self, runtime: BitaxeFleetRuntime, description: SensorEntityDescription
    ) -> None:
        """Initialize a stable hub-linked sensor from its aggregate description."""
        self._runtime = runtime
        self.entity_description = description
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, runtime.entry_id)},
        )
        self._attr_unique_id = f"{runtime.entry_id}_{description.key}"

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to the runtime's cached aggregate refreshes."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self._runtime.fleet_updated_signal,
                self._async_handle_fleet_update,
            )
        )

    @callback
    def _async_handle_fleet_update(self) -> None:
        """Write the already-calculated state without polling a miner."""
        self.async_write_ha_state()

    @property
    @override
    def native_value(self) -> float | int | None:
        """Return the selected aggregate without fabricating missing metrics."""
        aggregates = self._runtime.fleet_aggregates
        match self.entity_description.key:
            case "total_hashrate":
                return aggregates.total_hashrate_gh_s
            case "total_hashrate_th":
                return aggregates.total_hashrate_th_s
            case "total_power":
                return aggregates.total_power_w
            case "efficiency":
                return aggregates.efficiency_j_th
            case "total_uptime":
                return aggregates.total_uptime_seconds
            case "best_difficulty":
                return aggregates.best_difficulty
            case "best_session_difficulty":
                return aggregates.best_session_difficulty
            case "online_miners":
                return aggregates.online_miners
            case "unhealthy_miners":
                return aggregates.unhealthy_miners
            case "overheating_miners":
                return aggregates.overheating_miners
        return None

    @property
    @override
    def extra_state_attributes(self) -> dict[str, int]:
        """Expose coverage so partial values remain distinguishable from full totals."""
        return _coverage_attributes(self._runtime.fleet_aggregates)


def _coverage_attributes(aggregates: FleetAggregates) -> dict[str, int]:
    """Return common aggregate coverage without miner identity or endpoints."""
    return {
        "enabled_miners": aggregates.enabled_miners,
        "online_miners": aggregates.online_miners,
        "hashrate_coverage": aggregates.hashrate_coverage,
        "power_coverage": aggregates.power_coverage,
        "uptime_coverage": aggregates.uptime_coverage,
        "best_difficulty_coverage": aggregates.best_difficulty_coverage,
        "best_session_difficulty_coverage": (
            aggregates.best_session_difficulty_coverage
        ),
        "unhealthy_coverage": aggregates.unhealthy_coverage,
        "overheat_coverage": aggregates.overheat_coverage,
    }
