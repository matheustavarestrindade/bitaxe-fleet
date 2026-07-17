"""Tests for AxeOS system-info validation and normalization."""

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
from custom_components.bitaxe_fleet.axeos.models import MinerEndpoint
from custom_components.bitaxe_fleet.axeos.parser import (
    normalize_miner_id,
    parse_private_ipv4,
    parse_system_info,
)

_FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "axeos" / "system_info_v2_14_synthetic.json"
)


def _system_info() -> dict[str, object]:
    """Load the synthetic system-info fixture as an untrusted JSON object."""
    raw: object = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    return {str(key): value for key, value in raw.items()}


def _endpoint() -> MinerEndpoint:
    """Return a private endpoint used only in parser tests."""
    return MinerEndpoint(host=IPv4Address("192.168.10.25"))


def test_parse_system_info_creates_typed_snapshot() -> None:
    """Known valid AxeOS fields produce immutable domain values."""
    snapshot = parse_system_info(_system_info(), _endpoint())

    assert str(snapshot.identity.miner_id) == "02:12:34:56:78:9a"
    assert snapshot.identity.hostname == "bitaxe-lab"
    assert snapshot.identity.asic_model == "BM1368"
    assert snapshot.identity.board_version == "Bitaxe Supra"
    assert snapshot.identity.firmware_version == "v2.14.2"
    assert snapshot.telemetry.hashrate_gh_s == 654.32
    assert snapshot.telemetry.power_w == 17.4
    assert snapshot.telemetry.temperature_c == 54.25
    assert snapshot.observed_at.tzinfo is UTC


def test_parse_system_info_preserves_missing_optional_telemetry() -> None:
    """Absent optional metrics remain absent instead of becoming zero values."""
    payload = _system_info()
    payload.pop("hashRate")
    payload.pop("power")
    payload.pop("temp")

    snapshot = parse_system_info(payload, _endpoint())

    assert snapshot.telemetry.hashrate_gh_s is None
    assert snapshot.telemetry.power_w is None
    assert snapshot.telemetry.temperature_c is None


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


def test_parse_system_info_rejects_generic_json_and_unsafe_numbers() -> None:
    """MAC-like generic JSON and non-finite telemetry cannot reach entities."""
    with pytest.raises(AxeOSInvalidResponseError):
        parse_system_info(
            {"macAddr": "02:12:34:56:78:9a", "version": "v1.0.0"}, _endpoint()
        )

    payload = _system_info()
    payload["hashRate"] = "NaN"
    with pytest.raises(AxeOSInvalidResponseError):
        parse_system_info(payload, _endpoint())
