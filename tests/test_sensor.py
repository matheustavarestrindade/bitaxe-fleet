"""Tests for coordinator-backed Bitaxe Fleet sensors and device linkage."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from ipaddress import IPv4Address
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bitaxe_fleet.axeos.errors import AxeOSConnectionError
from custom_components.bitaxe_fleet.axeos.models import (
    MinerConfiguration,
    MinerEndpoint,
    MinerHealth,
    MinerIdentity,
    MinerSnapshot,
    MinerTelemetry,
)
from custom_components.bitaxe_fleet.axeos.parser import normalize_miner_id
from custom_components.bitaxe_fleet.binary_sensor import BINARY_SENSOR_DESCRIPTIONS
from custom_components.bitaxe_fleet.const import DOMAIN
from custom_components.bitaxe_fleet.sensor import (
    FLEET_SENSOR_DESCRIPTIONS,
    SENSOR_DESCRIPTIONS,
)
from custom_components.bitaxe_fleet.storage import MinerRegistry


def _snapshot() -> MinerSnapshot:
    """Create a synthetic current miner response."""
    identity = MinerIdentity(
        miner_id=normalize_miner_id("02:12:34:56:78:9a"),
        hostname="bitaxe-lab",
        asic_model="BM1368",
        board_version="Bitaxe Supra",
        firmware_version="v2.14.2",
    )
    return MinerSnapshot(
        endpoint=MinerEndpoint(host=IPv4Address("192.168.10.25")),
        identity=identity,
        telemetry=MinerTelemetry(
            hashrate_gh_s=654.32,
            power_w=17.4,
            temperature_c=54.25,
            hashrate_1m_gh_s=650.12,
            hashrate_10m_gh_s=648.5,
            hashrate_1h_gh_s=645.25,
            expected_hashrate_gh_s=650.0,
            error_percentage=0.25,
            input_voltage_mv=5100.0,
            current_ma=3400.0,
            core_voltage_actual_mv=1192.0,
            actual_frequency_mhz=523.0,
            secondary_temperature_c=53.5,
            vr_temperature_c=52.0,
            fan_speed_percent=48.5,
            fan_rpm=4100,
            fan_2_rpm=4200,
            shares_accepted=4768,
            shares_rejected=2,
            best_difficulty=1_250_000.0,
            best_session_difficulty=250_000.0,
            pool_difficulty=1000.0,
            pool_response_time_ms=125.5,
            wifi_rssi_dbm=-55,
            uptime_seconds=18_574,
            block_height=900_000,
            network_difficulty=146_472_570_619_930.0,
            blocks_found=1,
        ),
        observed_at=datetime.now(UTC),
        configuration=MinerConfiguration(frequency_mhz=525.0),
        health=MinerHealth(
            mining_paused=False,
            using_fallback_pool=True,
            overheat_mode=1,
            power_fault="undervoltage",
            hardware_fault="ASIC fault",
        ),
    )


async def test_enrolled_miner_creates_native_entities_and_linked_device(
    hass: HomeAssistant,
) -> None:
    """A persisted enrollment creates every native entity under one miner device."""
    entry = MockConfigEntry(domain=DOMAIN)
    registry = MinerRegistry(hass, entry.entry_id)
    snapshot = _snapshot()
    await registry.async_enroll(snapshot)
    entry.add_to_hass(hass)

    with patch(
        "custom_components.bitaxe_fleet.axeos.client.AxeOSClient.async_get_system_info",
        new=AsyncMock(return_value=snapshot),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    entities_by_unique_id = {
        registry_entry.unique_id: registry_entry for registry_entry in entries
    }

    expected_sensor_states = {
        "hashrate": "654.32",
        "power": "17.4",
        "temperature": "54.25",
        "hashrate_1m": "650.12",
        "hashrate_10m": "648.5",
        "hashrate_1h": "645.25",
        "expected_hashrate": "650.0",
        "error_percentage": "0.25",
        "voltage": "5.1",
        "current": "3.4",
        "secondary_temperature": "53.5",
        "vr_temperature": "52.0",
        "frequency": "525.0",
        "actual_frequency": "523.0",
        "core_voltage": "1192.0",
        "fan_speed": "48.5",
        "fan_rpm": "4100",
        "fan_2_rpm": "4200",
        "shares_accepted": "4768",
        "shares_rejected": "2",
        "best_difficulty": "1250000.0",
        "best_session_difficulty": "250000.0",
        "pool_difficulty": "1000.0",
        "pool_response_time": "125.5",
        "wifi_signal": "-55",
        "uptime": "18574",
        "block_height": "900000",
        "network_difficulty": "1.4647257061993e+14",
        "blocks_found": "1",
    }
    assert {description.key for description in SENSOR_DESCRIPTIONS} == set(
        expected_sensor_states
    )
    for key, expected_state in expected_sensor_states.items():
        state = hass.states.get(entities_by_unique_id[f"02123456789a_{key}"].entity_id)
        assert state is not None
        assert state.state == expected_state

    expected_fleet_sensor_states = {
        "total_hashrate": "654.32",
        "total_hashrate_th": "0.65432",
        "total_power": "17.4",
        "total_uptime": "18574",
        "best_difficulty": "1250000.0",
        "online_miners": "1",
        "unhealthy_miners": "1",
        "overheating_miners": "1",
    }
    assert {description.key for description in FLEET_SENSOR_DESCRIPTIONS} == {
        *expected_fleet_sensor_states,
        "efficiency",
    }
    for key, expected_state in expected_fleet_sensor_states.items():
        state = hass.states.get(
            entities_by_unique_id[f"{entry.entry_id}_{key}"].entity_id
        )
        assert state is not None
        assert state.state == expected_state
        assert state.attributes["enabled_miners"] == 1
        assert state.attributes["online_miners"] == 1

    efficiency = hass.states.get(
        entities_by_unique_id[f"{entry.entry_id}_efficiency"].entity_id
    )
    assert efficiency is not None
    assert float(efficiency.state) == pytest.approx(17.4 / (654.32 / 1_000))

    expected_binary_states = {
        "mining": "on",
        "fallback_pool": "on",
        "overheating": "on",
        "power_fault": "on",
        "hardware_fault": "on",
    }
    assert {description.key for description in BINARY_SENSOR_DESCRIPTIONS} == set(
        expected_binary_states
    )
    for key, expected_state in expected_binary_states.items():
        state = hass.states.get(entities_by_unique_id[f"02123456789a_{key}"].entity_id)
        assert state is not None
        assert state.state == expected_state

    device_registry = dr.async_get(hass)
    hub = device_registry.async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    miner = device_registry.async_get_device(
        identifiers={(DOMAIN, "02:12:34:56:78:9a")}
    )
    assert hub is not None
    assert miner is not None
    assert miner.via_device_id == hub.id
    assert entities_by_unique_id[f"{entry.entry_id}_total_hashrate"].device_id == hub.id


async def test_explicit_enrollment_adds_every_entity_platform(
    hass: HomeAssistant,
) -> None:
    """An explicit post-setup enrollment immediately creates both entity platforms."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    snapshot = _snapshot()

    with patch(
        "custom_components.bitaxe_fleet.axeos.client.AxeOSClient.async_get_system_info",
        new=AsyncMock(return_value=snapshot),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert len(
            er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
        ) == len(FLEET_SENSOR_DESCRIPTIONS)

        await entry.runtime_data.async_enroll_host("192.168.10.25")
        await hass.async_block_till_done()

    entries = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    assert len(entries) == (
        len(FLEET_SENSOR_DESCRIPTIONS)
        + len(SENSOR_DESCRIPTIONS)
        + len(BINARY_SENSOR_DESCRIPTIONS)
    )


async def test_optional_miner_entities_remain_unknown(hass: HomeAssistant) -> None:
    """Unsupported firmware fields remain unavailable instead of becoming zero."""
    snapshot = replace(
        _snapshot(),
        telemetry=MinerTelemetry(
            hashrate_gh_s=654.32,
            power_w=17.4,
            temperature_c=54.25,
        ),
        configuration=MinerConfiguration(),
        health=MinerHealth(),
    )
    entry = MockConfigEntry(domain=DOMAIN)
    registry = MinerRegistry(hass, entry.entry_id)
    await registry.async_enroll(snapshot)
    entry.add_to_hass(hass)

    with patch(
        "custom_components.bitaxe_fleet.axeos.client.AxeOSClient.async_get_system_info",
        new=AsyncMock(return_value=snapshot),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entries_by_unique_id = {
        registry_entry.unique_id: registry_entry
        for registry_entry in er.async_entries_for_config_entry(
            er.async_get(hass), entry.entry_id
        )
    }
    voltage = hass.states.get(entries_by_unique_id["02123456789a_voltage"].entity_id)
    mining = hass.states.get(entries_by_unique_id["02123456789a_mining"].entity_id)
    assert voltage is not None
    assert mining is not None
    assert voltage.state == STATE_UNKNOWN
    assert mining.state == STATE_UNKNOWN


async def test_fleet_aggregates_refresh_after_a_coordinator_update(
    hass: HomeAssistant,
) -> None:
    """The hub entities reuse the runtime aggregate cache after every fresh update."""
    entry = MockConfigEntry(domain=DOMAIN)
    registry = MinerRegistry(hass, entry.entry_id)
    snapshot = _snapshot()
    await registry.async_enroll(snapshot)
    entry.add_to_hass(hass)

    with patch(
        "custom_components.bitaxe_fleet.axeos.client.AxeOSClient.async_get_system_info",
        new=AsyncMock(return_value=snapshot),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    coordinator = entry.runtime_data.get_coordinator(snapshot.identity.miner_id)
    assert coordinator is not None
    coordinator.async_apply_discovered_snapshot(
        replace(
            snapshot,
            telemetry=replace(
                snapshot.telemetry,
                hashrate_gh_s=1_250.0,
                power_w=25.0,
            ),
        )
    )
    await hass.async_block_till_done()

    entries_by_unique_id = {
        registry_entry.unique_id: registry_entry
        for registry_entry in er.async_entries_for_config_entry(
            er.async_get(hass), entry.entry_id
        )
    }
    total_hashrate = hass.states.get(
        entries_by_unique_id[f"{entry.entry_id}_total_hashrate"].entity_id
    )
    total_power = hass.states.get(
        entries_by_unique_id[f"{entry.entry_id}_total_power"].entity_id
    )
    assert total_hashrate is not None
    assert total_power is not None
    assert total_hashrate.state == "1250.0"
    assert total_power.state == "25.0"


async def test_fleet_aggregates_exclude_a_stale_coordinator(
    hass: HomeAssistant,
) -> None:
    """A failed refresh excludes the retained last-good snapshot from fleet totals."""
    entry = MockConfigEntry(domain=DOMAIN)
    registry = MinerRegistry(hass, entry.entry_id)
    snapshot = _snapshot()
    await registry.async_enroll(snapshot)
    entry.add_to_hass(hass)

    with patch(
        "custom_components.bitaxe_fleet.axeos.client.AxeOSClient.async_get_system_info",
        new=AsyncMock(
            side_effect=[snapshot, AxeOSConnectionError("system info")],
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        coordinator = entry.runtime_data.get_coordinator(snapshot.identity.miner_id)
        assert coordinator is not None
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    entries_by_unique_id = {
        registry_entry.unique_id: registry_entry
        for registry_entry in er.async_entries_for_config_entry(
            er.async_get(hass), entry.entry_id
        )
    }
    total_hashrate = hass.states.get(
        entries_by_unique_id[f"{entry.entry_id}_total_hashrate"].entity_id
    )
    online_miners = hass.states.get(
        entries_by_unique_id[f"{entry.entry_id}_online_miners"].entity_id
    )
    assert total_hashrate is not None
    assert online_miners is not None
    assert total_hashrate.state == STATE_UNKNOWN
    assert total_hashrate.attributes["online_miners"] == 0
    assert online_miners.state == "0"
