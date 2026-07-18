"""Validation and normalization for untrusted AxeOS API responses."""

from __future__ import annotations

import math
import re
from datetime import UTC, datetime
from ipaddress import IPv4Address, IPv4Network

from ..const import MAX_AXEOS_LOG_RESPONSE_BYTES, MAX_AXEOS_LOG_TEXT_BYTES
from .errors import AxeOSInvalidEndpointError, AxeOSInvalidResponseError
from .models import (
    AsicCapabilities,
    MinerConfiguration,
    MinerEndpoint,
    MinerHealth,
    MinerId,
    MinerIdentity,
    MinerLogs,
    MinerSnapshot,
    MinerTelemetry,
    ShareRejectionReason,
)

_MAX_TEXT_LENGTH = 128
_MAX_TEMPERATURE_C = 200.0
_MAX_FREQUENCY_MHZ = 10_000.0
_MAX_VOLTAGE_MV = 10_000.0
_MAX_ASIC_COUNT = 256
_MAX_OVERHEAT_MODE = 255
_HOSTNAME_PATTERN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,62})")
_MAC_PATTERN = re.compile(r"[0-9a-fA-F]{12}")
_PRIVATE_IPV4_NETWORKS: tuple[IPv4Network, ...] = (
    IPv4Network("10.0.0.0/8"),
    IPv4Network("172.16.0.0/12"),
    IPv4Network("192.168.0.0/16"),
)
_SYSTEM_INFO_OPERATION = "system info"
_SYSTEM_ASIC_OPERATION = "system ASIC"
_SYSTEM_LOGS_OPERATION = "system logs"


def parse_private_ipv4(value: object) -> IPv4Address:
    """Validate a user-supplied RFC 1918 IPv4 host."""
    if not isinstance(value, str):
        raise AxeOSInvalidEndpointError

    try:
        address = IPv4Address(value.strip())
    except ValueError:
        raise AxeOSInvalidEndpointError from None

    if not any(address in network for network in _PRIVATE_IPV4_NETWORKS):
        raise AxeOSInvalidEndpointError

    return address


def normalize_miner_id(value: object) -> MinerId:
    """Normalize and validate AxeOS ``macAddr`` as the permanent miner ID."""
    if not isinstance(value, str):
        raise AxeOSInvalidResponseError(_SYSTEM_INFO_OPERATION, "missing MAC address")

    compact = value.strip().replace(":", "").replace("-", "")
    if _MAC_PATTERN.fullmatch(compact) is None:
        raise AxeOSInvalidResponseError(_SYSTEM_INFO_OPERATION, "invalid MAC address")

    first_octet = int(compact[:2], 16)
    if first_octet & 1 or compact.lower() in {"000000000000", "ffffffffffff"}:
        raise AxeOSInvalidResponseError(_SYSTEM_INFO_OPERATION, "invalid MAC address")

    return MinerId(
        ":".join(compact[index : index + 2] for index in range(0, 12, 2)).lower()
    )


def parse_system_info(payload: object, endpoint: MinerEndpoint) -> MinerSnapshot:
    """Build a validated system-info snapshot from untrusted JSON."""
    info = _as_string_keyed_mapping(payload, _SYSTEM_INFO_OPERATION)
    asic_model = _optional_text(info, "ASICModel", _SYSTEM_INFO_OPERATION)
    if asic_model is None:
        raise AxeOSInvalidResponseError(
            _SYSTEM_INFO_OPERATION, "missing AxeOS identity fields"
        )

    identity = MinerIdentity(
        miner_id=normalize_miner_id(info.get("macAddr")),
        hostname=_optional_hostname(info),
        asic_model=asic_model,
        board_version=_optional_text(info, "boardVersion", _SYSTEM_INFO_OPERATION),
        firmware_version=_optional_text(info, "version", _SYSTEM_INFO_OPERATION)
        or _optional_text(info, "axeOSVersion", _SYSTEM_INFO_OPERATION),
    )
    telemetry = MinerTelemetry(
        hashrate_gh_s=_optional_number(
            info, "hashRate", _SYSTEM_INFO_OPERATION, minimum=0.0
        ),
        power_w=_optional_number(info, "power", _SYSTEM_INFO_OPERATION, minimum=0.0),
        temperature_c=_optional_temperature(info, "temp"),
        hashrate_1m_gh_s=_optional_number(
            info, "hashRate_1m", _SYSTEM_INFO_OPERATION, minimum=0.0
        ),
        hashrate_10m_gh_s=_optional_number(
            info, "hashRate_10m", _SYSTEM_INFO_OPERATION, minimum=0.0
        ),
        hashrate_1h_gh_s=_optional_number(
            info, "hashRate_1h", _SYSTEM_INFO_OPERATION, minimum=0.0
        ),
        expected_hashrate_gh_s=_optional_number(
            info, "expectedHashrate", _SYSTEM_INFO_OPERATION, minimum=0.0
        ),
        error_percentage=_optional_number(
            info, "errorPercentage", _SYSTEM_INFO_OPERATION, minimum=0.0, maximum=100.0
        ),
        input_voltage_mv=_optional_number(
            info, "voltage", _SYSTEM_INFO_OPERATION, minimum=0.0
        ),
        current_ma=_optional_number(
            info, "current", _SYSTEM_INFO_OPERATION, minimum=0.0
        ),
        core_voltage_actual_mv=_optional_number(
            info, "coreVoltageActual", _SYSTEM_INFO_OPERATION, minimum=0.0
        ),
        actual_frequency_mhz=_optional_number(
            info,
            "actualFrequency",
            _SYSTEM_INFO_OPERATION,
            minimum=0.0,
            maximum=_MAX_FREQUENCY_MHZ,
        ),
        secondary_temperature_c=_optional_temperature(
            info, "temp2", missing_sentinel=True
        ),
        vr_temperature_c=_optional_temperature(info, "vrTemp", missing_sentinel=True),
        fan_speed_percent=_optional_number(
            info, "fanspeed", _SYSTEM_INFO_OPERATION, minimum=0.0, maximum=100.0
        ),
        fan_rpm=_optional_int(info, "fanrpm", _SYSTEM_INFO_OPERATION, minimum=0),
        fan_2_rpm=_optional_int(info, "fan2rpm", _SYSTEM_INFO_OPERATION, minimum=0),
        shares_accepted=_optional_int(
            info, "sharesAccepted", _SYSTEM_INFO_OPERATION, minimum=0
        ),
        shares_rejected=_optional_int(
            info, "sharesRejected", _SYSTEM_INFO_OPERATION, minimum=0
        ),
        share_rejection_reasons=_optional_share_rejection_reasons(info),
        best_difficulty=_optional_number(
            info, "bestDiff", _SYSTEM_INFO_OPERATION, minimum=0.0
        ),
        best_session_difficulty=_optional_number(
            info, "bestSessionDiff", _SYSTEM_INFO_OPERATION, minimum=0.0
        ),
        pool_difficulty=_optional_number(
            info, "poolDifficulty", _SYSTEM_INFO_OPERATION, minimum=0.0
        ),
        pool_response_time_ms=_optional_number(
            info, "responseTime", _SYSTEM_INFO_OPERATION, minimum=0.0
        ),
        wifi_rssi_dbm=_optional_int(
            info, "wifiRSSI", _SYSTEM_INFO_OPERATION, minimum=-200, maximum=0
        ),
        uptime_seconds=_optional_int(
            info, "uptimeSeconds", _SYSTEM_INFO_OPERATION, minimum=0
        ),
        block_height=_optional_int(
            info, "blockHeight", _SYSTEM_INFO_OPERATION, minimum=0
        ),
        network_difficulty=_optional_number(
            info, "networkDifficulty", _SYSTEM_INFO_OPERATION, minimum=0.0
        ),
        blocks_found=_optional_int(
            info, "blockFound", _SYSTEM_INFO_OPERATION, minimum=0
        ),
    )
    configuration = MinerConfiguration(
        frequency_mhz=_optional_number(
            info,
            "frequency",
            _SYSTEM_INFO_OPERATION,
            minimum=1.0,
            maximum=_MAX_FREQUENCY_MHZ,
        ),
        core_voltage_mv=_optional_int(
            info,
            "coreVoltage",
            _SYSTEM_INFO_OPERATION,
            minimum=1,
            maximum=int(_MAX_VOLTAGE_MV),
        ),
        overclock_enabled=_optional_bool(
            info, "overclockEnabled", _SYSTEM_INFO_OPERATION
        ),
        automatic_fan_speed=_optional_bool(
            info, "autofanspeed", _SYSTEM_INFO_OPERATION
        ),
        target_temperature_c=_optional_int(
            info, "temptarget", _SYSTEM_INFO_OPERATION, minimum=0, maximum=100
        ),
        minimum_fan_speed_percent=_optional_int(
            info, "minFanSpeed", _SYSTEM_INFO_OPERATION, minimum=0, maximum=100
        ),
        manual_fan_speed_percent=_optional_int(
            info, "manualFanSpeed", _SYSTEM_INFO_OPERATION, minimum=0, maximum=100
        ),
    )
    health = MinerHealth(
        mining_paused=_optional_bool(info, "miningPaused", _SYSTEM_INFO_OPERATION),
        using_fallback_pool=_optional_bool(
            info, "isUsingFallbackStratum", _SYSTEM_INFO_OPERATION
        ),
        overheat_mode=_optional_int(
            info,
            "overheat_mode",
            _SYSTEM_INFO_OPERATION,
            minimum=0,
            maximum=_MAX_OVERHEAT_MODE,
        ),
        power_fault=_optional_text(info, "power_fault", _SYSTEM_INFO_OPERATION),
        hardware_fault=_optional_text(info, "hardware_fault", _SYSTEM_INFO_OPERATION),
        reset_reason=_optional_text(info, "resetReason", _SYSTEM_INFO_OPERATION),
        wifi_status=_optional_text(info, "wifiStatus", _SYSTEM_INFO_OPERATION),
    )
    return MinerSnapshot(
        endpoint=endpoint,
        identity=identity,
        telemetry=telemetry,
        observed_at=datetime.now(UTC),
        configuration=configuration,
        health=health,
    )


def parse_system_asic(payload: object) -> AsicCapabilities:
    """Build validated model-specific capabilities from untrusted JSON."""
    asic = _as_string_keyed_mapping(payload, _SYSTEM_ASIC_OPERATION)
    asic_model = _required_text(asic, "ASICModel", _SYSTEM_ASIC_OPERATION)
    frequency_options = _optional_number_tuple(
        asic,
        "frequencyOptions",
        _SYSTEM_ASIC_OPERATION,
        minimum=1.0,
        maximum=_MAX_FREQUENCY_MHZ,
    )
    voltage_options = _optional_int_tuple(
        asic,
        "voltageOptions",
        _SYSTEM_ASIC_OPERATION,
        minimum=1,
        maximum=int(_MAX_VOLTAGE_MV),
    )
    default_frequency = _optional_number(
        asic,
        "defaultFrequency",
        _SYSTEM_ASIC_OPERATION,
        minimum=1.0,
        maximum=_MAX_FREQUENCY_MHZ,
    )
    default_voltage = _optional_int(
        asic,
        "defaultVoltage",
        _SYSTEM_ASIC_OPERATION,
        minimum=1,
        maximum=int(_MAX_VOLTAGE_MV),
    )
    if frequency_options is not None and (
        default_frequency is not None and default_frequency not in frequency_options
    ):
        raise AxeOSInvalidResponseError(
            _SYSTEM_ASIC_OPERATION, "invalid defaultFrequency field"
        )
    if voltage_options is not None and (
        default_voltage is not None and default_voltage not in voltage_options
    ):
        raise AxeOSInvalidResponseError(
            _SYSTEM_ASIC_OPERATION, "invalid defaultVoltage field"
        )

    return AsicCapabilities(
        asic_model=asic_model,
        device_model=_optional_text(asic, "deviceModel", _SYSTEM_ASIC_OPERATION),
        swarm_color=_optional_text(asic, "swarmColor", _SYSTEM_ASIC_OPERATION),
        asic_count=_optional_int(
            asic,
            "asicCount",
            _SYSTEM_ASIC_OPERATION,
            minimum=0,
            maximum=_MAX_ASIC_COUNT,
        ),
        default_frequency_mhz=default_frequency,
        frequency_options_mhz=frequency_options,
        default_voltage_mv=default_voltage,
        voltage_options_mv=voltage_options,
    )


def parse_system_logs(payload: object) -> MinerLogs:
    """Validate a bounded plain-text firmware log response."""
    if not isinstance(payload, str):
        raise AxeOSInvalidResponseError(_SYSTEM_LOGS_OPERATION, "expected text")
    if "\x00" in payload:
        raise AxeOSInvalidResponseError(_SYSTEM_LOGS_OPERATION, "invalid text")

    try:
        byte_length = len(payload.encode("utf-8"))
    except UnicodeError:
        raise AxeOSInvalidResponseError(
            _SYSTEM_LOGS_OPERATION, "invalid text"
        ) from None
    if byte_length > MAX_AXEOS_LOG_RESPONSE_BYTES:
        raise AxeOSInvalidResponseError(_SYSTEM_LOGS_OPERATION, "response is too large")
    if byte_length <= MAX_AXEOS_LOG_TEXT_BYTES:
        return MinerLogs(text=payload)
    return MinerLogs(text=_log_tail(payload))


def _log_tail(payload: str) -> str:
    """Keep the newest bounded whole-line log tail for panel and diagnostics use."""
    encoded = payload.encode("utf-8")
    tail = encoded[-MAX_AXEOS_LOG_TEXT_BYTES:]
    newline = tail.find(b"\n")
    if newline >= 0:
        tail = tail[newline + 1 :]
    return tail.decode("utf-8", errors="ignore")


def _as_string_keyed_mapping(payload: object, operation: str) -> dict[str, object]:
    """Narrow a JSON object without letting ``Any`` enter domain code."""
    if not isinstance(payload, dict):
        raise AxeOSInvalidResponseError(operation, "expected a JSON object")

    result: dict[str, object] = {}
    for key, value in payload.items():
        if not isinstance(key, str):
            raise AxeOSInvalidResponseError(operation, "expected string keys")
        result[key] = value
    return result


def _optional_hostname(info: dict[str, object]) -> str | None:
    """Return a hostname only when it is safe to use as a device name."""
    hostname = _optional_text(info, "hostname", _SYSTEM_INFO_OPERATION)
    if hostname is None or _HOSTNAME_PATTERN.fullmatch(hostname) is None:
        return None
    return hostname


def _required_text(info: dict[str, object], key: str, operation: str) -> str:
    """Return one required bounded printable text field."""
    value = _optional_text(info, key, operation)
    if value is None:
        raise AxeOSInvalidResponseError(operation, f"missing {key} field")
    return value


def _optional_text(info: dict[str, object], key: str, operation: str) -> str | None:
    """Validate a bounded printable optional text field."""
    value = info.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise AxeOSInvalidResponseError(operation, f"invalid {key} field")

    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > _MAX_TEXT_LENGTH or not normalized.isprintable():
        raise AxeOSInvalidResponseError(operation, f"invalid {key} field")
    return normalized


def _optional_number(
    info: dict[str, object],
    key: str,
    operation: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float | None:
    """Validate a finite optional number with explicit bounds."""
    value = info.get(key)
    if value is None:
        return None
    number = _parse_number(value, key, operation)
    _validate_number_range(number, key, operation, minimum, maximum)
    return number


def _optional_int(
    info: dict[str, object],
    key: str,
    operation: str,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int | None:
    """Validate a finite optional whole number with explicit bounds."""
    value = info.get(key)
    if value is None:
        return None
    number = _parse_number(value, key, operation)
    if not number.is_integer():
        raise AxeOSInvalidResponseError(operation, f"invalid {key} field")
    integer = int(number)
    if (minimum is not None and integer < minimum) or (
        maximum is not None and integer > maximum
    ):
        raise AxeOSInvalidResponseError(operation, f"invalid {key} field")
    return integer


def _optional_bool(info: dict[str, object], key: str, operation: str) -> bool | None:
    """Validate documented JSON and numeric AxeOS boolean forms."""
    value = info.get(key)
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value == 0:
            return False
        if value == 1:
            return True
    if isinstance(value, str):
        normalized = value.strip()
        if normalized == "0":
            return False
        if normalized == "1":
            return True
    raise AxeOSInvalidResponseError(operation, f"invalid {key} field")


def _optional_temperature(
    info: dict[str, object], key: str, *, missing_sentinel: bool = False
) -> float | None:
    """Parse a hardware temperature while recognizing the documented ``-1`` sentinel."""
    value = info.get(key)
    if value is None:
        return None
    number = _parse_number(value, key, _SYSTEM_INFO_OPERATION)
    if missing_sentinel and number == -1:
        return None
    _validate_number_range(
        number,
        key,
        _SYSTEM_INFO_OPERATION,
        0.0,
        _MAX_TEMPERATURE_C,
    )
    return number


def _optional_share_rejection_reasons(
    info: dict[str, object],
) -> tuple[ShareRejectionReason, ...] | None:
    """Convert documented rejection-reason objects into immutable values."""
    value = info.get("sharesRejectedReasons")
    if value is None:
        return None
    if not isinstance(value, list):
        raise AxeOSInvalidResponseError(
            _SYSTEM_INFO_OPERATION, "invalid sharesRejectedReasons field"
        )

    reasons: list[ShareRejectionReason] = []
    for item in value:
        reason = _as_string_keyed_mapping(item, _SYSTEM_INFO_OPERATION)
        reasons.append(
            ShareRejectionReason(
                message=_required_text(reason, "message", _SYSTEM_INFO_OPERATION),
                count=_required_int(reason, "count", minimum=0),
            )
        )
    return tuple(reasons)


def _required_int(info: dict[str, object], key: str, *, minimum: int) -> int:
    """Return a required non-negative integer from a nested AxeOS object."""
    value = _optional_int(info, key, _SYSTEM_INFO_OPERATION, minimum=minimum)
    if value is None:
        raise AxeOSInvalidResponseError(_SYSTEM_INFO_OPERATION, f"missing {key} field")
    return value


def _optional_number_tuple(
    info: dict[str, object],
    key: str,
    operation: str,
    *,
    minimum: float,
    maximum: float,
) -> tuple[float, ...] | None:
    """Validate one non-empty numeric capability list without duplicate values."""
    value = info.get(key)
    if value is None:
        return None
    if not isinstance(value, list) or not value:
        raise AxeOSInvalidResponseError(operation, f"invalid {key} field")

    values: list[float] = []
    for item in value:
        number = _parse_number(item, key, operation)
        _validate_number_range(number, key, operation, minimum, maximum)
        if number in values:
            raise AxeOSInvalidResponseError(operation, f"invalid {key} field")
        values.append(number)
    return tuple(values)


def _optional_int_tuple(
    info: dict[str, object],
    key: str,
    operation: str,
    *,
    minimum: int,
    maximum: int,
) -> tuple[int, ...] | None:
    """Validate one non-empty integer capability list without duplicate values."""
    value = info.get(key)
    if value is None:
        return None
    if not isinstance(value, list) or not value:
        raise AxeOSInvalidResponseError(operation, f"invalid {key} field")

    values: list[int] = []
    for item in value:
        number = _parse_number(item, key, operation)
        if not number.is_integer():
            raise AxeOSInvalidResponseError(operation, f"invalid {key} field")
        integer = int(number)
        if not minimum <= integer <= maximum or integer in values:
            raise AxeOSInvalidResponseError(operation, f"invalid {key} field")
        values.append(integer)
    return tuple(values)


def _parse_number(value: object, key: str, operation: str) -> float:
    """Convert one documented number or numeric string without accepting booleans."""
    if isinstance(value, bool):
        raise AxeOSInvalidResponseError(operation, f"invalid {key} field")
    try:
        if isinstance(value, (int, float)):
            number = float(value)
        elif isinstance(value, str):
            number = float(value.strip())
        else:
            raise TypeError
    except OverflowError, TypeError, ValueError:
        raise AxeOSInvalidResponseError(operation, f"invalid {key} field") from None

    if not math.isfinite(number):
        raise AxeOSInvalidResponseError(operation, f"invalid {key} field")
    return number


def _validate_number_range(
    number: float,
    key: str,
    operation: str,
    minimum: float | None,
    maximum: float | None,
) -> None:
    """Reject documented numeric values outside a caller-supplied safe range."""
    if (minimum is not None and number < minimum) or (
        maximum is not None and number > maximum
    ):
        raise AxeOSInvalidResponseError(operation, f"invalid {key} field")
