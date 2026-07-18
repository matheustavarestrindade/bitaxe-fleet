"""Immutable domain models for validated AxeOS data."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from ipaddress import IPv4Address
from typing import NewType

from ..const import DEFAULT_HTTP_PORT

MinerId = NewType("MinerId", str)


@dataclass(frozen=True, slots=True)
class MinerEndpoint:
    """A validated local endpoint used to contact one miner."""

    host: IPv4Address
    port: int = DEFAULT_HTTP_PORT

    @property
    def base_url(self) -> str:
        """Return the HTTP base URL for this private IPv4 endpoint."""
        if self.port == DEFAULT_HTTP_PORT:
            return f"http://{self.host}"
        return f"http://{self.host}:{self.port}"


@dataclass(frozen=True, slots=True)
class MinerIdentity:
    """Stable identity and safely displayable AxeOS metadata."""

    miner_id: MinerId
    hostname: str | None
    asic_model: str | None
    board_version: str | None
    firmware_version: str | None

    @property
    def display_name(self) -> str:
        """Return a stable, compact device name."""
        if self.hostname is not None:
            return self.hostname
        return f"Bitaxe {str(self.miner_id).replace(':', '')[-6:].upper()}"


@dataclass(frozen=True, slots=True)
class ShareRejectionReason:
    """One validated reason reported for rejected shares."""

    message: str
    count: int


@dataclass(frozen=True, slots=True)
class MinerTelemetry:
    """Optional telemetry present in a validated system-info response."""

    hashrate_gh_s: float | None
    power_w: float | None
    temperature_c: float | None
    hashrate_1m_gh_s: float | None = None
    hashrate_10m_gh_s: float | None = None
    hashrate_1h_gh_s: float | None = None
    expected_hashrate_gh_s: float | None = None
    error_percentage: float | None = None
    input_voltage_mv: float | None = None
    current_ma: float | None = None
    core_voltage_actual_mv: float | None = None
    actual_frequency_mhz: float | None = None
    secondary_temperature_c: float | None = None
    vr_temperature_c: float | None = None
    fan_speed_percent: float | None = None
    fan_rpm: int | None = None
    fan_2_rpm: int | None = None
    shares_accepted: int | None = None
    shares_rejected: int | None = None
    share_rejection_reasons: tuple[ShareRejectionReason, ...] | None = None
    best_difficulty: float | None = None
    best_session_difficulty: float | None = None
    pool_difficulty: float | None = None
    pool_response_time_ms: float | None = None
    wifi_rssi_dbm: int | None = None
    uptime_seconds: int | None = None
    block_height: int | None = None
    network_difficulty: float | None = None
    blocks_found: int | None = None


@dataclass(frozen=True, slots=True)
class MinerConfiguration:
    """Current safe-to-read recovery settings from AxeOS."""

    frequency_mhz: float | None = None
    core_voltage_mv: int | None = None
    overclock_enabled: bool | None = None
    automatic_fan_speed: bool | None = None
    target_temperature_c: int | None = None
    minimum_fan_speed_percent: int | None = None
    manual_fan_speed_percent: int | None = None

    def to_recovery_profile(self) -> RecoveryProfile | None:
        """Return a complete profile only when every approved setting is present."""
        frequency_mhz = self.frequency_mhz
        core_voltage_mv = self.core_voltage_mv
        overclock_enabled = self.overclock_enabled
        automatic_fan_speed = self.automatic_fan_speed
        target_temperature_c = self.target_temperature_c
        minimum_fan_speed_percent = self.minimum_fan_speed_percent
        if (
            frequency_mhz is None
            or core_voltage_mv is None
            or overclock_enabled is None
            or automatic_fan_speed is None
            or target_temperature_c is None
            or minimum_fan_speed_percent is None
        ):
            return None
        return RecoveryProfile(
            frequency_mhz=frequency_mhz,
            core_voltage_mv=core_voltage_mv,
            overclock_enabled=overclock_enabled,
            automatic_fan_speed=automatic_fan_speed,
            target_temperature_c=target_temperature_c,
            minimum_fan_speed_percent=minimum_fan_speed_percent,
        )


@dataclass(frozen=True, slots=True)
class RecoveryProfile:
    """The closed six-setting profile that may be sent to AxeOS."""

    frequency_mhz: float
    core_voltage_mv: int
    overclock_enabled: bool
    automatic_fan_speed: bool
    target_temperature_c: int
    minimum_fan_speed_percent: int

    def __post_init__(self) -> None:
        """Reject values that cannot safely form a bounded system patch."""
        object.__setattr__(
            self,
            "frequency_mhz",
            _validated_profile_float(self.frequency_mhz, 1.0, 10_000.0),
        )
        object.__setattr__(
            self,
            "core_voltage_mv",
            _validated_profile_int(self.core_voltage_mv, 1, 10_000),
        )
        object.__setattr__(
            self,
            "overclock_enabled",
            _validated_profile_bool(self.overclock_enabled),
        )
        object.__setattr__(
            self,
            "automatic_fan_speed",
            _validated_profile_bool(self.automatic_fan_speed),
        )
        object.__setattr__(
            self,
            "target_temperature_c",
            _validated_profile_int(self.target_temperature_c, 0, 100),
        )
        object.__setattr__(
            self,
            "minimum_fan_speed_percent",
            _validated_profile_int(self.minimum_fan_speed_percent, 0, 100),
        )


class OverheatPolicy(StrEnum):
    """How automatic recovery handles AxeOS thermal safety changes."""

    KEEP_SAFE_VALUES = "keep_safe_values"
    RESTORE_AFTER_COOLDOWN = "restore_after_cooldown"
    LOG_ONLY = "log_only"


@dataclass(frozen=True, slots=True)
class RecoveryPolicy:
    """Bounded per-miner automatic-recovery policy with safe defaults."""

    automatic_recovery_enabled: bool = False
    automatic_profile_restore_enabled: bool = False
    startup_grace_seconds: int = 180
    consecutive_unhealthy_required: int = 3
    cooldown_seconds: int = 600
    max_attempts: int = 3
    rolling_window_seconds: int = 3600
    post_restart_timeout_seconds: int = 180
    verification_timeout_seconds: int = 60
    overheat_policy: OverheatPolicy = OverheatPolicy.KEEP_SAFE_VALUES

    def __post_init__(self) -> None:
        """Reject persisted policy values outside conservative operational bounds."""
        for value in (
            self.automatic_recovery_enabled,
            self.automatic_profile_restore_enabled,
        ):
            _validated_profile_bool(value)
        object.__setattr__(
            self,
            "startup_grace_seconds",
            _validated_policy_int(self.startup_grace_seconds, 0, 3600),
        )
        object.__setattr__(
            self,
            "consecutive_unhealthy_required",
            _validated_policy_int(self.consecutive_unhealthy_required, 1, 20),
        )
        object.__setattr__(
            self,
            "cooldown_seconds",
            _validated_policy_int(self.cooldown_seconds, 0, 86_400),
        )
        object.__setattr__(
            self,
            "max_attempts",
            _validated_policy_int(self.max_attempts, 1, 20),
        )
        object.__setattr__(
            self,
            "rolling_window_seconds",
            _validated_policy_int(self.rolling_window_seconds, 60, 604_800),
        )
        object.__setattr__(
            self,
            "post_restart_timeout_seconds",
            _validated_policy_int(self.post_restart_timeout_seconds, 30, 3600),
        )
        object.__setattr__(
            self,
            "verification_timeout_seconds",
            _validated_policy_int(self.verification_timeout_seconds, 10, 3600),
        )
        if not isinstance(self.overheat_policy, OverheatPolicy):
            raise ValueError("invalid recovery policy")


@dataclass(frozen=True, slots=True)
class MinerHealth:
    """Validated system-info state used by health and recovery logic."""

    mining_paused: bool | None = None
    using_fallback_pool: bool | None = None
    overheat_mode: int | None = None
    power_fault: str | None = None
    hardware_fault: str | None = None
    reset_reason: str | None = None
    wifi_status: str | None = None


@dataclass(frozen=True, slots=True)
class AsicCapabilities:
    """Model-specific frequency and voltage capabilities returned by AxeOS."""

    asic_model: str
    device_model: str | None
    swarm_color: str | None
    asic_count: int | None
    default_frequency_mhz: float | None
    frequency_options_mhz: tuple[float, ...] | None
    default_voltage_mv: int | None
    voltage_options_mv: tuple[int, ...] | None

    def supports_profile(self, profile: RecoveryProfile) -> bool:
        """Return whether both ASIC-tuned values are explicitly supported."""
        frequencies = self.frequency_options_mhz
        voltages = self.voltage_options_mv
        return (
            frequencies is not None
            and voltages is not None
            and profile.frequency_mhz in frequencies
            and profile.core_voltage_mv in voltages
        )


@dataclass(frozen=True, slots=True)
class MinerLogs:
    """Bounded plain-text firmware logs returned by AxeOS."""

    text: str


@dataclass(frozen=True, slots=True)
class MinerSnapshot:
    """One immutable observation returned by AxeOS."""

    endpoint: MinerEndpoint
    identity: MinerIdentity
    telemetry: MinerTelemetry
    observed_at: datetime
    configuration: MinerConfiguration = field(default_factory=MinerConfiguration)
    health: MinerHealth = field(default_factory=MinerHealth)


@dataclass(frozen=True, slots=True)
class EnrolledMiner:
    """Persistent metadata for one administrator-approved miner."""

    endpoint: MinerEndpoint
    identity: MinerIdentity
    display_name: str | None = None
    enabled: bool = True
    recovery_profile: RecoveryProfile | None = None
    recovery_policy: RecoveryPolicy = field(default_factory=RecoveryPolicy)


def _validated_profile_float(value: object, minimum: float, maximum: float) -> float:
    """Validate one finite profile float without accepting wire-format strings."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("invalid recovery profile")
    try:
        number = float(value)
    except OverflowError:
        raise ValueError("invalid recovery profile") from None
    if not math.isfinite(number) or not minimum <= number <= maximum:
        raise ValueError("invalid recovery profile")
    return number


def _validated_profile_int(value: object, minimum: int, maximum: int) -> int:
    """Validate one integral profile field with its documented bounds."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("invalid recovery profile")
    if not minimum <= value <= maximum:
        raise ValueError("invalid recovery profile")
    return value


def _validated_profile_bool(value: object) -> bool:
    """Require actual domain booleans in a profile constructor."""
    if not isinstance(value, bool):
        raise ValueError("invalid recovery profile")
    return value


def _validated_policy_int(value: object, minimum: int, maximum: int) -> int:
    """Validate a bounded whole-number recovery-policy value."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("invalid recovery policy")
    if not minimum <= value <= maximum:
        raise ValueError("invalid recovery policy")
    return value
