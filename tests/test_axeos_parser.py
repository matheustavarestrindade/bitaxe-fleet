"""Tests for AxeOS parser validation and normalized immutable models."""

from __future__ import annotations

import json
from datetime import UTC
from ipaddress import IPv4Address
from pathlib import Path

import pytest

from custom_components.bitaxe_fleet.axeos.errors import (
    AxeOSInvalidEndpointError,
    AxeOSInvalidResponseError,
)
from custom_components.bitaxe_fleet.axeos.models import MinerEndpoint, RecoveryProfile
from custom_components.bitaxe_fleet.axeos.parser import (
    normalize_miner_id,
    parse_private_ipv4,
    parse_system_asic,
    parse_system_info,
    parse_system_logs,
)
from custom_components.bitaxe_fleet.const import MAX_AXEOS_LOG_RESPONSE_BYTES

_FIXTURES_PATH = Path(__file__).parent / "fixtures" / "axeos"


def _json_fixture(name: str) -> dict[str, object]:
    """Load one synthetic JSON fixture as an untrusted object."""
    raw: object = json.loads((_FIXTURES_PATH / name).read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    return {str(key): value for key, value in raw.items()}


def _endpoint() -> MinerEndpoint:
    """Return a private endpoint used only in parser tests."""
    return MinerEndpoint(host=IPv4Address("192.168.10.25"))


def test_parse_system_info_creates_typed_snapshot() -> None:
    """A complete documented response becomes typed identity, health, and settings."""
    snapshot = parse_system_info(
        _json_fixture("system_info_v2_14_synthetic.json"), _endpoint()
    )

    assert str(snapshot.identity.miner_id) == "02:12:34:56:78:9a"
    assert snapshot.identity.hostname == "bitaxe-lab"
    assert snapshot.identity.asic_model == "BM1368"
    assert snapshot.identity.board_version == "Bitaxe Supra"
    assert snapshot.identity.firmware_version == "v2.14.2"
    assert snapshot.telemetry.hashrate_gh_s == 654.32
    assert snapshot.telemetry.hashrate_1m_gh_s == 650.12
    assert snapshot.telemetry.hashrate_10m_gh_s == 648.5
    assert snapshot.telemetry.hashrate_1h_gh_s == 645.25
    assert snapshot.telemetry.power_w == 17.4
    assert snapshot.telemetry.temperature_c == 54.25
    assert snapshot.telemetry.secondary_temperature_c is None
    assert snapshot.telemetry.vr_temperature_c == 52.0
    assert snapshot.telemetry.fan_rpm == 4100
    assert snapshot.telemetry.shares_accepted == 4768
    assert snapshot.telemetry.share_rejection_reasons is not None
    assert snapshot.telemetry.share_rejection_reasons[0].message == "Stale"
    assert snapshot.telemetry.share_rejection_reasons[0].count == 2
    assert snapshot.configuration.frequency_mhz == 525.0
    assert snapshot.configuration.core_voltage_mv == 1200
    assert snapshot.configuration.overclock_enabled is True
    assert snapshot.configuration.automatic_fan_speed is True
    assert snapshot.configuration.target_temperature_c == 60
    assert snapshot.configuration.minimum_fan_speed_percent == 25
    assert snapshot.configuration.manual_fan_speed_percent == 100
    assert snapshot.configuration.to_recovery_profile() == RecoveryProfile(
        frequency_mhz=525.0,
        core_voltage_mv=1200,
        overclock_enabled=True,
        automatic_fan_speed=True,
        target_temperature_c=60,
        minimum_fan_speed_percent=25,
    )
    assert snapshot.health.mining_paused is False
    assert snapshot.health.using_fallback_pool is False
    assert snapshot.health.overheat_mode == 0
    assert snapshot.health.power_fault is None
    assert snapshot.health.hardware_fault is None
    assert snapshot.health.reset_reason == "Software reset"
    assert snapshot.observed_at.tzinfo is UTC


def test_parse_system_info_preserves_missing_optional_values() -> None:
    """A valid partial response retains unsupported fields as ``None``."""
    snapshot = parse_system_info(
        _json_fixture("system_info_partial_synthetic.json"), _endpoint()
    )

    assert snapshot.identity.asic_model == "BM1370"
    assert snapshot.telemetry.hashrate_gh_s == 1000.5
    assert snapshot.telemetry.power_w is None
    assert snapshot.telemetry.temperature_c is None
    assert snapshot.telemetry.secondary_temperature_c is None
    assert snapshot.configuration.frequency_mhz is None
    assert snapshot.configuration.manual_fan_speed_percent is None
    assert snapshot.configuration.to_recovery_profile() is None
    assert snapshot.health.mining_paused is None
    assert snapshot.health.power_fault is None


def test_parse_system_info_rejects_malformed_fixture() -> None:
    """Malformed documented fields cannot be silently converted or omitted."""
    with pytest.raises(AxeOSInvalidResponseError):
        parse_system_info(
            _json_fixture("system_info_malformed_synthetic.json"), _endpoint()
        )


@pytest.mark.parametrize(
    ("raw_mac", "normalized"),
    (
        ("02-12-34-56-78-9A", "02:12:34:56:78:9a"),
        ("02123456789a", "02:12:34:56:78:9a"),
        (" 02:12:34:56:78:9a ", "02:12:34:56:78:9a"),
    ),
)
def test_normalize_miner_id_accepts_documented_mac_forms(
    raw_mac: str, normalized: str
) -> None:
    """Separators do not affect the MAC-based permanent identity."""
    assert str(normalize_miner_id(raw_mac)) == normalized


@pytest.mark.parametrize(
    "raw_mac",
    ("01:12:34:56:78:9a", "00:00:00:00:00:00", "ff:ff:ff:ff:ff:ff", "not-a-mac"),
)
def test_normalize_miner_id_rejects_invalid_identity(raw_mac: str) -> None:
    """Multicast, broadcast, zero, and malformed MAC values cannot enroll."""
    with pytest.raises(AxeOSInvalidResponseError):
        normalize_miner_id(raw_mac)


@pytest.mark.parametrize(
    "host",
    ("8.8.8.8", "127.0.0.1", "169.254.1.1", "224.0.0.1", "example.com"),
)
def test_parse_private_ipv4_rejects_non_private_hosts(host: str) -> None:
    """Manual enrollment cannot become an arbitrary URL or public request."""
    with pytest.raises(AxeOSInvalidEndpointError):
        parse_private_ipv4(host)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("hashRate", "NaN"),
        ("hashRate", "Infinity"),
        ("sharesAccepted", -1),
        ("autofanspeed", "true"),
        ("miningPaused", 2),
        ("fanspeed", 101),
    ),
)
def test_parse_system_info_rejects_unsafe_documented_values(
    field: str, value: object
) -> None:
    """Invalid number, boolean, counter, and range variants cannot reach models."""
    payload = _json_fixture("system_info_v2_14_synthetic.json")
    payload[field] = value

    with pytest.raises(AxeOSInvalidResponseError):
        parse_system_info(payload, _endpoint())


def test_parse_system_info_rejects_generic_json_without_identity_signature() -> None:
    """MAC-like generic JSON cannot be mistaken for a supported AxeOS miner."""
    with pytest.raises(AxeOSInvalidResponseError):
        parse_system_info(
            {"macAddr": "02:12:34:56:78:9a", "version": "v1.0.0"}, _endpoint()
        )


def test_parse_system_info_error_does_not_include_untrusted_value() -> None:
    """Parser failures name a field but never repeat an untrusted response value."""
    secret = "unexpected-secret-value"
    payload = _json_fixture("system_info_partial_synthetic.json")
    payload["hashRate"] = secret

    with pytest.raises(AxeOSInvalidResponseError) as error:
        parse_system_info(payload, _endpoint())

    assert secret not in str(error.value)


def test_parse_system_asic_creates_typed_capabilities() -> None:
    """A documented ASIC response preserves capability choices in immutable tuples."""
    capabilities = parse_system_asic(_json_fixture("system_asic_v2_14_synthetic.json"))
    profile = RecoveryProfile(
        frequency_mhz=525.0,
        core_voltage_mv=1200,
        overclock_enabled=True,
        automatic_fan_speed=True,
        target_temperature_c=60,
        minimum_fan_speed_percent=25,
    )

    assert capabilities.asic_model == "BM1368"
    assert capabilities.device_model == "Supra"
    assert capabilities.asic_count == 1
    assert capabilities.default_frequency_mhz == 525.0
    assert capabilities.frequency_options_mhz == (400.0, 450.0, 500.0, 525.0, 550.0)
    assert capabilities.default_voltage_mv == 1200
    assert capabilities.voltage_options_mv == (1100, 1150, 1200, 1250)
    assert capabilities.supports_profile(profile)


def test_parse_system_asic_preserves_partial_capabilities() -> None:
    """Missing hardware-specific settings stay absent rather than becoming defaults."""
    capabilities = parse_system_asic(
        _json_fixture("system_asic_partial_synthetic.json")
    )

    assert capabilities.asic_model == "BM1397"
    assert capabilities.asic_count == 1
    assert capabilities.frequency_options_mhz is None
    assert capabilities.voltage_options_mv is None
    assert capabilities.default_frequency_mhz is None


def test_parse_system_asic_rejects_malformed_fixture() -> None:
    """Non-finite capability values cannot be used for profile validation."""
    with pytest.raises(AxeOSInvalidResponseError):
        parse_system_asic(_json_fixture("system_asic_malformed_synthetic.json"))


def test_parse_system_logs_preserves_bounded_plain_text() -> None:
    """Firmware logs remain opaque text, never a raw response mapping."""
    text = (_FIXTURES_PATH / "system_logs_v2_14_synthetic.txt").read_text(
        encoding="utf-8"
    )

    logs = parse_system_logs(text)

    assert logs.text == text
    assert "reconnecting" in logs.text


def test_parse_system_logs_accepts_partial_text() -> None:
    """A short retained log fragment is still valid plain-text diagnostic evidence."""
    text = (_FIXTURES_PATH / "system_logs_partial_synthetic.txt").read_text(
        encoding="utf-8"
    )

    assert parse_system_logs(text).text == text


@pytest.mark.parametrize("payload", (object(), "bad\x00log"))
def test_parse_system_logs_rejects_malformed_text(payload: object) -> None:
    """Non-text and NUL-containing responses cannot become log models."""
    with pytest.raises(AxeOSInvalidResponseError):
        parse_system_logs(payload)


def test_parse_system_logs_rejects_malformed_fixture() -> None:
    """A JSON response fixture cannot cross the plain-text logs boundary."""
    with pytest.raises(AxeOSInvalidResponseError):
        parse_system_logs(_json_fixture("system_logs_malformed_synthetic.json"))


def test_parse_system_logs_enforces_byte_limit() -> None:
    """Direct parser use cannot bypass the transport log-size limit."""
    with pytest.raises(AxeOSInvalidResponseError):
        parse_system_logs("x" * (MAX_AXEOS_LOG_RESPONSE_BYTES + 1))


def test_recovery_profile_rejects_invalid_domain_values() -> None:
    """A patch cannot be constructed from values outside the closed model bounds."""
    with pytest.raises(ValueError):
        RecoveryProfile(
            frequency_mhz=float("nan"),
            core_voltage_mv=1200,
            overclock_enabled=True,
            automatic_fan_speed=True,
            target_temperature_c=60,
            minimum_fan_speed_percent=25,
        )
