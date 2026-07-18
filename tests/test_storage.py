"""Tests for MAC-keyed persistent miner enrollment storage."""

from __future__ import annotations

from datetime import UTC, datetime
from ipaddress import IPv4Address

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from custom_components.bitaxe_fleet.axeos.models import (
    MinerEndpoint,
    MinerIdentity,
    MinerSnapshot,
    MinerTelemetry,
)
from custom_components.bitaxe_fleet.axeos.parser import normalize_miner_id
from custom_components.bitaxe_fleet.const import (
    DOMAIN,
    STORAGE_SCHEMA_VERSION,
    STORAGE_STORE_VERSION,
)
from custom_components.bitaxe_fleet.storage import MinerRegistry


def _snapshot(host: str) -> MinerSnapshot:
    """Create one synthetic validated observation for registry tests."""
    identity = MinerIdentity(
        miner_id=normalize_miner_id("02:12:34:56:78:9a"),
        hostname="bitaxe-lab",
        asic_model="BM1368",
        board_version="Bitaxe Supra",
        firmware_version="v2.14.2",
    )
    return MinerSnapshot(
        endpoint=MinerEndpoint(host=IPv4Address(host)),
        identity=identity,
        telemetry=MinerTelemetry(
            hashrate_gh_s=654.32,
            power_w=17.4,
            temperature_c=54.25,
        ),
        observed_at=datetime.now(UTC),
    )


async def test_registry_persists_enrollment_and_endpoint_changes(
    hass: HomeAssistant,
) -> None:
    """The same MAC at a new private host remains one enrollment record."""
    registry = MinerRegistry(hass, "test-entry")
    await registry.async_enroll(_snapshot("192.168.10.25"))
    await registry.async_enroll(_snapshot("192.168.10.26"))

    restored = MinerRegistry(hass, "test-entry")
    await restored.async_load()

    assert len(restored.miners) == 1
    miner = restored.miners[0]
    assert str(miner.identity.miner_id) == "02:12:34:56:78:9a"
    assert str(miner.endpoint.host) == "192.168.10.26"
    assert miner.identity.asic_model == "BM1368"
    assert miner.identity.firmware_version == "v2.14.2"


async def test_registry_does_not_auto_enroll_unknown_snapshots(
    hass: HomeAssistant,
) -> None:
    """Polling metadata can never turn an unapproved candidate into a miner."""
    registry = MinerRegistry(hass, "test-entry")
    await registry.async_update_from_snapshot(_snapshot("192.168.10.25"))

    assert registry.miners == ()


async def test_registry_isolates_invalid_persisted_top_level_data(
    hass: HomeAssistant,
) -> None:
    """Corrupt storage cannot prevent the hub from setting up."""
    key = f"{DOMAIN}.test-entry"
    await Store[list[object]](hass, STORAGE_STORE_VERSION, key).async_save([])

    registry = MinerRegistry(hass, "test-entry")
    await registry.async_load()

    assert registry.miners == ()


async def test_registry_redacts_incident_details_before_persistence(
    hass: HomeAssistant,
) -> None:
    """Persisted incident text cannot retain addresses or credentials from callers."""
    registry = MinerRegistry(hass, "test-entry")
    miner_id = _snapshot("192.168.10.25").identity.miner_id

    incident = await registry.async_record_incident(
        miner_id,
        "manual_action",
        "failed",
        "password=hunter2 host=192.168.10.25",
    )

    assert incident.detail == "**REDACTED_SECRET** **REDACTED_SECRET**"
    restored = MinerRegistry(hass, "test-entry")
    await restored.async_load()
    assert restored.incidents[0].detail == incident.detail


async def test_registry_migrates_the_released_v1_enrollment_shape(
    hass: HomeAssistant,
) -> None:
    """The v0.2.0 enrollment record remains usable after schema-2 migration."""
    key = f"{DOMAIN}.test-entry"
    miner_id = "02:12:34:56:78:9a"
    await Store[dict[str, object]](hass, STORAGE_STORE_VERSION, key).async_save(
        {
            "schema_version": 1,
            "miners": {
                miner_id: {
                    "asic_model": "BM1368",
                    "board_version": "Bitaxe Supra",
                    "firmware_version": "v2.14.2",
                    "host": "192.168.10.25",
                    "hostname": "bitaxe-lab",
                    "miner_id": miner_id,
                }
            },
        }
    )

    registry = MinerRegistry(hass, "test-entry")
    await registry.async_load()
    migrated = await Store[dict[str, object]](
        hass, STORAGE_STORE_VERSION, key
    ).async_load()

    assert registry.miners[0].recovery_profile is None
    assert registry.miners[0].recovery_policy.automatic_recovery_enabled is False
    assert isinstance(migrated, dict)
    assert migrated["schema_version"] == STORAGE_SCHEMA_VERSION
    assert migrated["rejected_candidates"] == []
    assert migrated["incidents"] == []
