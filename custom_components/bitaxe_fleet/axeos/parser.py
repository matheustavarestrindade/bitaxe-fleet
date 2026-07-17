"""Validation and normalization for untrusted AxeOS JSON."""

from __future__ import annotations

import math
import re
from datetime import UTC, datetime
from ipaddress import IPv4Address, IPv4Network

from .errors import AxeOSInvalidEndpointError, AxeOSInvalidResponseError
from .models import MinerEndpoint, MinerId, MinerIdentity, MinerSnapshot, MinerTelemetry

_MAX_TEXT_LENGTH = 128
_HOSTNAME_PATTERN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,62})")
_MAC_PATTERN = re.compile(r"[0-9a-fA-F]{12}")
_PRIVATE_IPV4_NETWORKS: tuple[IPv4Network, ...] = (
    IPv4Network("10.0.0.0/8"),
    IPv4Network("172.16.0.0/12"),
    IPv4Network("192.168.0.0/16"),
)


def parse_private_ipv4(value: object) -> IPv4Address:
    """Validate a user-supplied RFC 1918 IPv4 host."""
    if not isinstance(value, str):
        raise AxeOSInvalidEndpointError

    try:
        address = IPv4Address(value.strip())
    except ValueError as err:
        raise AxeOSInvalidEndpointError from err

    if not any(address in network for network in _PRIVATE_IPV4_NETWORKS):
        raise AxeOSInvalidEndpointError

    return address


def normalize_miner_id(value: object) -> MinerId:
    """Normalize and validate AxeOS ``macAddr`` as the permanent miner ID."""
    if not isinstance(value, str):
        raise AxeOSInvalidResponseError("system info", "missing MAC address")

    compact = value.strip().replace(":", "").replace("-", "")
    if _MAC_PATTERN.fullmatch(compact) is None:
        raise AxeOSInvalidResponseError("system info", "invalid MAC address")

    first_octet = int(compact[:2], 16)
    if first_octet & 1 or compact.lower() in {"000000000000", "ffffffffffff"}:
        raise AxeOSInvalidResponseError("system info", "invalid MAC address")

    return MinerId(
        ":".join(compact[index : index + 2] for index in range(0, 12, 2)).lower()
    )


def parse_system_info(payload: object, endpoint: MinerEndpoint) -> MinerSnapshot:
    """Build a validated system-info snapshot from untrusted JSON."""
    info = _as_string_keyed_mapping(payload)
    _require_axeos_signature(info)

    miner_id = normalize_miner_id(info.get("macAddr"))
    firmware_version = _optional_text(info, "version") or _optional_text(
        info, "axeOSVersion"
    )
    identity = MinerIdentity(
        miner_id=miner_id,
        hostname=_optional_hostname(info),
        asic_model=_optional_text(info, "ASICModel"),
        board_version=_optional_text(info, "boardVersion"),
        firmware_version=firmware_version,
    )
    telemetry = MinerTelemetry(
        hashrate_gh_s=_optional_nonnegative_number(info, "hashRate"),
        power_w=_optional_nonnegative_number(info, "power"),
        temperature_c=_optional_nonnegative_number(info, "temp"),
    )
    return MinerSnapshot(
        endpoint=endpoint,
        identity=identity,
        telemetry=telemetry,
        observed_at=datetime.now(UTC),
    )


def _as_string_keyed_mapping(payload: object) -> dict[str, object]:
    """Narrow a JSON object without letting ``Any`` enter domain code."""
    if not isinstance(payload, dict):
        raise AxeOSInvalidResponseError("system info", "expected a JSON object")

    result: dict[str, object] = {}
    for key, value in payload.items():
        if not isinstance(key, str):
            raise AxeOSInvalidResponseError("system info", "expected string keys")
        result[key] = value
    return result


def _require_axeos_signature(info: dict[str, object]) -> None:
    """Reject generic JSON services that merely expose a MAC-like value."""
    if _optional_text(info, "ASICModel") is None:
        raise AxeOSInvalidResponseError("system info", "missing AxeOS identity fields")


def _optional_hostname(info: dict[str, object]) -> str | None:
    """Return a hostname only when it is safe to use as a device name."""
    hostname = _optional_text(info, "hostname")
    if hostname is None or _HOSTNAME_PATTERN.fullmatch(hostname) is None:
        return None
    return hostname


def _optional_text(info: dict[str, object], key: str) -> str | None:
    """Validate a bounded printable optional text field."""
    value = info.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise AxeOSInvalidResponseError("system info", f"invalid {key} field")

    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > _MAX_TEXT_LENGTH or not normalized.isprintable():
        raise AxeOSInvalidResponseError("system info", f"invalid {key} field")
    return normalized


def _optional_nonnegative_number(info: dict[str, object], key: str) -> float | None:
    """Validate a finite optional non-negative measurement."""
    value = info.get(key)
    if value is None:
        return None
    if isinstance(value, bool):
        raise AxeOSInvalidResponseError("system info", f"invalid {key} field")

    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        try:
            number = float(value.strip())
        except ValueError as err:
            raise AxeOSInvalidResponseError(
                "system info", f"invalid {key} field"
            ) from err
    else:
        raise AxeOSInvalidResponseError("system info", f"invalid {key} field")

    if not math.isfinite(number) or number < 0:
        raise AxeOSInvalidResponseError("system info", f"invalid {key} field")
    return number
