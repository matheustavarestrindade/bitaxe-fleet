"""Tests for coordinator-backed Bitaxe Fleet sensors and device linkage."""

from __future__ import annotations

from datetime import UTC, datetime
from ipaddress import IPv4Address
from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bitaxe_fleet.axeos.models import (
    MinerEndpoint,
    MinerIdentity,
    MinerSnapshot,
    MinerTelemetry,
)
from custom_components.bitaxe_fleet.axeos.parser import normalize_miner_id
from custom_components.bitaxe_fleet.const import DOMAIN
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
        ),
        observed_at=datetime.now(UTC),
    )


async def test_enrolled_miner_creates_stable_sensors_and_linked_device(
    hass: HomeAssistant,
) -> None:
    """A persisted enrollment creates native sensors under one MAC-keyed device."""
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

    hashrate = entities_by_unique_id["02123456789a_hashrate"]
    power = entities_by_unique_id["02123456789a_power"]
    temperature = entities_by_unique_id["02123456789a_temperature"]
    hashrate_state = hass.states.get(hashrate.entity_id)
    power_state = hass.states.get(power.entity_id)
    temperature_state = hass.states.get(temperature.entity_id)
    assert hashrate_state is not None
    assert power_state is not None
    assert temperature_state is not None
    assert hashrate_state.state == "654.32"
    assert power_state.state == "17.4"
    assert temperature_state.state == "54.25"

    device_registry = dr.async_get(hass)
    hub = device_registry.async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    miner = device_registry.async_get_device(
        identifiers={(DOMAIN, "02:12:34:56:78:9a")}
    )
    assert hub is not None
    assert miner is not None
    assert miner.via_device_id == hub.id
