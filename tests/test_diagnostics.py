"""Tests for privacy-safe Bitaxe Fleet diagnostics."""

from __future__ import annotations

from datetime import UTC, datetime
from ipaddress import IPv4Address
from typing import cast

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bitaxe_fleet.axeos.models import (
    MinerEndpoint,
    MinerHealth,
    MinerIdentity,
    MinerSnapshot,
    MinerTelemetry,
)
from custom_components.bitaxe_fleet.axeos.parser import normalize_miner_id
from custom_components.bitaxe_fleet.const import DOMAIN, STORAGE_SCHEMA_VERSION
from custom_components.bitaxe_fleet.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.bitaxe_fleet.runtime import (
    BitaxeFleetConfigEntry,
    BitaxeFleetRuntime,
)


def _snapshot() -> MinerSnapshot:
    """Create a known miner record that contains identifiers diagnostics must omit."""
    return MinerSnapshot(
        endpoint=MinerEndpoint(IPv4Address("192.168.10.25")),
        identity=MinerIdentity(
            miner_id=normalize_miner_id("02:12:34:56:78:9a"),
            hostname="bitaxe-lab",
            asic_model="BM1368",
            board_version="Bitaxe Supra",
            firmware_version="v2.14.2",
        ),
        telemetry=MinerTelemetry(
            hashrate_gh_s=500.0,
            power_w=17.4,
            temperature_c=54.0,
        ),
        observed_at=datetime.now(UTC),
        health=MinerHealth(),
    )


async def test_diagnostics_exclude_endpoint_and_identity_values(
    hass: HomeAssistant,
) -> None:
    """Support diagnostics contain only feature summaries, never household IDs."""
    runtime = await BitaxeFleetRuntime.async_create(hass, "test-entry")
    await runtime.registry.async_enroll(_snapshot())
    entry = MockConfigEntry(domain=DOMAIN)
    entry.runtime_data = runtime

    diagnostics = await async_get_config_entry_diagnostics(
        hass, cast(BitaxeFleetConfigEntry, entry)
    )

    assert diagnostics["storage_schema_version"] == STORAGE_SCHEMA_VERSION
    assert diagnostics["miners"] == [
        {
            "capabilities_loaded": False,
            "enabled": True,
            "firmware_version": "v2.14.2",
            "has_profile": False,
            "last_update_success": False,
            "model": "BM1368",
            "snapshot_fields": {},
        }
    ]
    rendered = repr(diagnostics)
    for identifier in ("192.168.10.25", "02:12:34:56:78:9a", "bitaxe-lab"):
        assert identifier not in rendered
    await runtime.async_close()
