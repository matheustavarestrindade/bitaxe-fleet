"""Versioned persistent fleet state without raw AxeOS payload retention."""

from __future__ import annotations

import asyncio
import logging
import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .axeos.errors import AxeOSError
from .axeos.models import (
    EnrolledMiner,
    MinerEndpoint,
    MinerId,
    MinerIdentity,
    MinerSnapshot,
    OverheatPolicy,
    RecoveryPolicy,
    RecoveryProfile,
)
from .axeos.parser import normalize_miner_id, parse_private_ipv4
from .const import (
    DOMAIN,
    MAX_STORED_INCIDENTS,
    STORAGE_SCHEMA_VERSION,
    STORAGE_STORE_VERSION,
)
from .redaction import redact_text

_LOGGER = logging.getLogger(__name__)
_LEGACY_SCHEMA_VERSION = 1
_HOSTNAME_PATTERN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,62})")
_MAX_TEXT_LENGTH = 128
_MAX_INCIDENT_DETAIL_LENGTH = 512


@dataclass(frozen=True, slots=True)
class FleetIncident:
    """Bounded, redaction-ready incident summary retained for an enrolled miner."""

    incident_id: str
    miner_id: MinerId
    occurred_at: datetime
    cause: str
    outcome: str
    detail: str


@dataclass(frozen=True, slots=True)
class _LoadedState:
    """Validated Store state and whether deployed data needs an immediate rewrite."""

    miners: dict[MinerId, EnrolledMiner]
    rejected_candidates: frozenset[MinerId]
    incidents: tuple[FleetIncident, ...]
    needs_migration_save: bool


class MinerRegistry:
    """Persist approved miners, rejections, profiles, policies, and incidents."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialize state for one singleton fleet config entry."""
        # Keep the Home Assistant Store envelope version stable and migrate the
        # explicit integration schema below so deployed v1 data remains readable.
        self._store = Store[dict[str, object]](
            hass,
            STORAGE_STORE_VERSION,
            f"{DOMAIN}.{entry_id}",
            atomic_writes=True,
        )
        self._miners: dict[MinerId, EnrolledMiner] = {}
        self._rejected_candidates: set[MinerId] = set()
        self._incidents: list[FleetIncident] = []
        self._lock = asyncio.Lock()
        self._loaded = False

    @property
    def miners(self) -> tuple[EnrolledMiner, ...]:
        """Return immutable approved miner records."""
        return tuple(self._miners.values())

    @property
    def rejected_candidates(self) -> frozenset[MinerId]:
        """Return MAC identities that an administrator explicitly rejected."""
        return frozenset(self._rejected_candidates)

    @property
    def incidents(self) -> tuple[FleetIncident, ...]:
        """Return bounded incident summaries in newest-first order."""
        return tuple(reversed(self._incidents))

    def get(self, miner_id: MinerId) -> EnrolledMiner | None:
        """Return an approved miner by permanent identity."""
        return self._miners.get(miner_id)

    async def async_load(self) -> None:
        """Load, validate, and migrate persisted state exactly once."""
        async with self._lock:
            if self._loaded:
                return

            data: object = await self._store.async_load()
            if data is not None:
                loaded = _deserialize_state(data)
                self._miners = loaded.miners
                self._rejected_candidates = set(loaded.rejected_candidates)
                self._incidents = list(loaded.incidents)
                if loaded.needs_migration_save:
                    await self._store.async_save(self._serialize())
            self._loaded = True

    async def async_enroll(self, snapshot: MinerSnapshot) -> EnrolledMiner:
        """Approve a snapshot while preserving existing user-owned fleet state."""
        await self.async_load()
        miner_id = snapshot.identity.miner_id
        async with self._lock:
            existing = self._miners.get(miner_id)
            miner = _enrolled_from_snapshot(snapshot, existing)
            self._miners[miner_id] = miner
            self._rejected_candidates.discard(miner_id)
            await self._store.async_save(self._serialize())
        return miner

    async def async_update_from_snapshot(
        self, snapshot: MinerSnapshot
    ) -> EnrolledMiner | None:
        """Update metadata only when the snapshot belongs to an approved MAC."""
        await self.async_load()
        miner_id = snapshot.identity.miner_id
        async with self._lock:
            existing = self._miners.get(miner_id)
            if existing is None:
                return None
            miner = _enrolled_from_snapshot(snapshot, existing)
            if miner == existing:
                return miner
            self._miners[miner_id] = miner
            await self._store.async_save(self._serialize())
            return miner

    async def async_set_enabled(
        self, miner_id: MinerId, enabled: bool
    ) -> EnrolledMiner:
        """Enable or disable an approved miner without changing its identity."""
        await self.async_load()
        if not isinstance(enabled, bool):
            raise ValueError("enabled must be boolean")
        async with self._lock:
            miner = self._require_miner(miner_id)
            updated = EnrolledMiner(
                endpoint=miner.endpoint,
                identity=miner.identity,
                display_name=miner.display_name,
                enabled=enabled,
                recovery_profile=miner.recovery_profile,
                recovery_policy=miner.recovery_policy,
            )
            self._miners[miner_id] = updated
            await self._store.async_save(self._serialize())
            return updated

    async def async_set_display_name(
        self, miner_id: MinerId, display_name: str | None
    ) -> EnrolledMiner:
        """Save a bounded administrator-approved miner name."""
        await self.async_load()
        normalized = _validate_optional_display_name(display_name)
        async with self._lock:
            miner = self._require_miner(miner_id)
            updated = EnrolledMiner(
                endpoint=miner.endpoint,
                identity=miner.identity,
                display_name=normalized,
                enabled=miner.enabled,
                recovery_profile=miner.recovery_profile,
                recovery_policy=miner.recovery_policy,
            )
            self._miners[miner_id] = updated
            await self._store.async_save(self._serialize())
            return updated

    async def async_set_recovery_profile(
        self, miner_id: MinerId, profile: RecoveryProfile | None
    ) -> EnrolledMiner:
        """Persist a validated closed profile for one approved miner."""
        await self.async_load()
        if profile is not None and not isinstance(profile, RecoveryProfile):
            raise ValueError("invalid recovery profile")
        async with self._lock:
            miner = self._require_miner(miner_id)
            updated = EnrolledMiner(
                endpoint=miner.endpoint,
                identity=miner.identity,
                display_name=miner.display_name,
                enabled=miner.enabled,
                recovery_profile=profile,
                recovery_policy=miner.recovery_policy,
            )
            self._miners[miner_id] = updated
            await self._store.async_save(self._serialize())
            return updated

    async def async_set_recovery_policy(
        self, miner_id: MinerId, policy: RecoveryPolicy
    ) -> EnrolledMiner:
        """Persist one complete validated recovery policy for an approved miner."""
        await self.async_load()
        if not isinstance(policy, RecoveryPolicy):
            raise ValueError("invalid recovery policy")
        async with self._lock:
            miner = self._require_miner(miner_id)
            updated = EnrolledMiner(
                endpoint=miner.endpoint,
                identity=miner.identity,
                display_name=miner.display_name,
                enabled=miner.enabled,
                recovery_profile=miner.recovery_profile,
                recovery_policy=policy,
            )
            self._miners[miner_id] = updated
            await self._store.async_save(self._serialize())
            return updated

    async def async_reject_candidate(self, miner_id: MinerId) -> None:
        """Remember an explicit rejection so rediscovery does not re-prompt."""
        await self.async_load()
        async with self._lock:
            self._rejected_candidates.add(miner_id)
            await self._store.async_save(self._serialize())

    async def async_remove(self, miner_id: MinerId) -> bool:
        """Remove an approved miner and its associated policy/profile state."""
        await self.async_load()
        async with self._lock:
            if miner_id not in self._miners:
                return False
            del self._miners[miner_id]
            self._incidents = [
                incident
                for incident in self._incidents
                if incident.miner_id != miner_id
            ]
            await self._store.async_save(self._serialize())
            return True

    async def async_record_incident(
        self, miner_id: MinerId, cause: str, outcome: str, detail: str
    ) -> FleetIncident:
        """Append a bounded incident summary without endpoint or payload data."""
        await self.async_load()
        incident = FleetIncident(
            incident_id=uuid4().hex,
            miner_id=miner_id,
            occurred_at=datetime.now(UTC),
            cause=_validate_incident_text(cause),
            outcome=_validate_incident_text(outcome),
            detail=_validate_incident_detail(redact_text(detail)),
        )
        async with self._lock:
            self._incidents.append(incident)
            del self._incidents[:-MAX_STORED_INCIDENTS]
            await self._store.async_save(self._serialize())
        return incident

    def _require_miner(self, miner_id: MinerId) -> EnrolledMiner:
        """Return an enrolled miner or raise a safe application-level error."""
        miner = self._miners.get(miner_id)
        if miner is None:
            raise KeyError("unknown miner")
        return miner

    def _serialize(self) -> dict[str, object]:
        """Create the closed JSON shape permitted in Home Assistant storage."""
        miners: dict[str, object] = {}
        for miner_id, miner in self._miners.items():
            identity = miner.identity
            miners[str(miner_id)] = {
                "asic_model": identity.asic_model,
                "board_version": identity.board_version,
                "display_name": miner.display_name,
                "enabled": miner.enabled,
                "firmware_version": identity.firmware_version,
                "host": str(miner.endpoint.host),
                "hostname": identity.hostname,
                "miner_id": str(identity.miner_id),
                "recovery_policy": _serialize_policy(miner.recovery_policy),
                "recovery_profile": _serialize_profile(miner.recovery_profile),
            }
        return {
            "incidents": [
                _serialize_incident(incident) for incident in self._incidents
            ],
            "miners": miners,
            "rejected_candidates": sorted(
                str(miner_id) for miner_id in self._rejected_candidates
            ),
            "schema_version": STORAGE_SCHEMA_VERSION,
        }


def _enrolled_from_snapshot(
    snapshot: MinerSnapshot, existing: EnrolledMiner | None
) -> EnrolledMiner:
    """Replace mutable endpoint/metadata while preserving approved fleet settings."""
    if existing is None:
        return EnrolledMiner(endpoint=snapshot.endpoint, identity=snapshot.identity)
    return EnrolledMiner(
        endpoint=snapshot.endpoint,
        identity=snapshot.identity,
        display_name=existing.display_name,
        enabled=existing.enabled,
        recovery_profile=existing.recovery_profile,
        recovery_policy=existing.recovery_policy,
    )


def _deserialize_state(data: object) -> _LoadedState:
    """Validate v1/v2 stored data and migrate deployed v1 records in memory."""
    root = _as_string_mapping(data)
    if root is None:
        _LOGGER.warning("Ignoring invalid Bitaxe Fleet enrollment storage")
        return _LoadedState({}, frozenset(), (), False)

    schema_version = root.get("schema_version")
    if schema_version == _LEGACY_SCHEMA_VERSION:
        return _LoadedState(
            miners=_deserialize_miners(root.get("miners"), legacy=True),
            rejected_candidates=frozenset(),
            incidents=(),
            needs_migration_save=True,
        )
    if schema_version != STORAGE_SCHEMA_VERSION or isinstance(schema_version, bool):
        _LOGGER.warning("Ignoring unsupported Bitaxe Fleet enrollment storage")
        return _LoadedState({}, frozenset(), (), False)

    return _LoadedState(
        miners=_deserialize_miners(root.get("miners"), legacy=False),
        rejected_candidates=_deserialize_rejections(root.get("rejected_candidates")),
        incidents=_deserialize_incidents(root.get("incidents")),
        needs_migration_save=False,
    )


def _deserialize_miners(value: object, *, legacy: bool) -> dict[MinerId, EnrolledMiner]:
    """Validate individual miner records while isolating corrupt records."""
    records = _as_string_mapping(value)
    if records is None:
        _LOGGER.warning("Ignoring invalid Bitaxe Fleet miner records")
        return {}

    miners: dict[MinerId, EnrolledMiner] = {}
    for key, raw_record in records.items():
        miner = _deserialize_miner(raw_record, legacy=legacy)
        if miner is None or key != str(miner.identity.miner_id):
            _LOGGER.warning("Ignoring invalid stored Bitaxe Fleet miner")
            continue
        miners[miner.identity.miner_id] = miner
    return miners


def _deserialize_miner(value: object, *, legacy: bool) -> EnrolledMiner | None:
    """Convert one closed storage record into a fully validated domain object."""
    record = _as_string_mapping(value)
    if record is None:
        return None

    try:
        identity = MinerIdentity(
            miner_id=normalize_miner_id(record.get("miner_id")),
            hostname=_stored_optional_hostname(record),
            asic_model=_stored_optional_text(record, "asic_model"),
            board_version=_stored_optional_text(record, "board_version"),
            firmware_version=_stored_optional_text(record, "firmware_version"),
        )
        endpoint = MinerEndpoint(host=parse_private_ipv4(record.get("host")))
        if legacy:
            return EnrolledMiner(endpoint=endpoint, identity=identity)
        return EnrolledMiner(
            endpoint=endpoint,
            identity=identity,
            display_name=_stored_optional_text(record, "display_name"),
            enabled=_stored_bool(record, "enabled", default=True),
            recovery_profile=_deserialize_profile(record.get("recovery_profile")),
            recovery_policy=_deserialize_policy(record.get("recovery_policy")),
        )
    except AxeOSError, ValueError:
        return None


def _deserialize_rejections(value: object) -> frozenset[MinerId]:
    """Load only valid normalized rejected candidate identities."""
    if value is None:
        return frozenset()
    if not isinstance(value, list):
        _LOGGER.warning("Ignoring invalid Bitaxe Fleet rejected candidates")
        return frozenset()

    rejected: set[MinerId] = set()
    for item in value:
        try:
            rejected.add(normalize_miner_id(item))
        except AxeOSError:
            _LOGGER.warning("Ignoring invalid rejected Bitaxe Fleet candidate")
    return frozenset(rejected)


def _deserialize_incidents(value: object) -> tuple[FleetIncident, ...]:
    """Load bounded valid incident summaries while isolating corrupt entries."""
    if value is None:
        return ()
    if not isinstance(value, list):
        _LOGGER.warning("Ignoring invalid Bitaxe Fleet incidents")
        return ()

    incidents: list[FleetIncident] = []
    for raw_incident in value[-MAX_STORED_INCIDENTS:]:
        incident = _deserialize_incident(raw_incident)
        if incident is None:
            _LOGGER.warning("Ignoring invalid Bitaxe Fleet incident")
            continue
        incidents.append(incident)
    return tuple(incidents)


def _deserialize_incident(value: object) -> FleetIncident | None:
    """Convert one stored incident without preserving invalid raw values."""
    record = _as_string_mapping(value)
    if record is None:
        return None
    try:
        incident_id = _stored_required_text(record, "incident_id", 64)
        miner_id = normalize_miner_id(record.get("miner_id"))
        occurred_at = _stored_datetime(record.get("occurred_at"))
        cause = _stored_required_text(record, "cause", _MAX_TEXT_LENGTH)
        outcome = _stored_required_text(record, "outcome", _MAX_TEXT_LENGTH)
        detail = _stored_required_text(record, "detail", _MAX_INCIDENT_DETAIL_LENGTH)
    except AxeOSError, ValueError:
        return None
    return FleetIncident(
        incident_id,
        miner_id,
        occurred_at,
        cause,
        outcome,
        _validate_incident_detail(redact_text(detail)),
    )


def _deserialize_profile(value: object) -> RecoveryProfile | None:
    """Deserialize exactly the six profile fields or reject the whole profile."""
    if value is None:
        return None
    record = _as_string_mapping(value)
    if record is None:
        raise ValueError("invalid recovery profile")
    return RecoveryProfile(
        frequency_mhz=_stored_float(record, "frequency_mhz"),
        core_voltage_mv=_stored_int(record, "core_voltage_mv"),
        overclock_enabled=_stored_bool(record, "overclock_enabled"),
        automatic_fan_speed=_stored_bool(record, "automatic_fan_speed"),
        target_temperature_c=_stored_int(record, "target_temperature_c"),
        minimum_fan_speed_percent=_stored_int(record, "minimum_fan_speed_percent"),
    )


def _deserialize_policy(value: object) -> RecoveryPolicy:
    """Deserialize a complete safe policy, defaulting only when absent."""
    if value is None:
        return RecoveryPolicy()
    record = _as_string_mapping(value)
    if record is None:
        raise ValueError("invalid recovery policy")
    overheat_value = record.get("overheat_policy")
    if not isinstance(overheat_value, str):
        raise ValueError("invalid recovery policy")
    return RecoveryPolicy(
        automatic_recovery_enabled=_stored_bool(record, "automatic_recovery_enabled"),
        automatic_profile_restore_enabled=_stored_bool(
            record, "automatic_profile_restore_enabled"
        ),
        startup_grace_seconds=_stored_int(record, "startup_grace_seconds"),
        consecutive_unhealthy_required=_stored_int(
            record, "consecutive_unhealthy_required"
        ),
        cooldown_seconds=_stored_int(record, "cooldown_seconds"),
        max_attempts=_stored_int(record, "max_attempts"),
        rolling_window_seconds=_stored_int(record, "rolling_window_seconds"),
        post_restart_timeout_seconds=_stored_int(
            record, "post_restart_timeout_seconds"
        ),
        verification_timeout_seconds=_stored_int(
            record, "verification_timeout_seconds"
        ),
        overheat_policy=OverheatPolicy(overheat_value),
    )


def _serialize_profile(profile: RecoveryProfile | None) -> dict[str, object] | None:
    """Serialize the exact closed profile schema."""
    if profile is None:
        return None
    return {
        "automatic_fan_speed": profile.automatic_fan_speed,
        "core_voltage_mv": profile.core_voltage_mv,
        "frequency_mhz": profile.frequency_mhz,
        "minimum_fan_speed_percent": profile.minimum_fan_speed_percent,
        "overclock_enabled": profile.overclock_enabled,
        "target_temperature_c": profile.target_temperature_c,
    }


def _serialize_policy(policy: RecoveryPolicy) -> dict[str, object]:
    """Serialize all policy fields explicitly rather than retaining extensions."""
    return {
        "automatic_profile_restore_enabled": policy.automatic_profile_restore_enabled,
        "automatic_recovery_enabled": policy.automatic_recovery_enabled,
        "consecutive_unhealthy_required": policy.consecutive_unhealthy_required,
        "cooldown_seconds": policy.cooldown_seconds,
        "max_attempts": policy.max_attempts,
        "overheat_policy": policy.overheat_policy.value,
        "post_restart_timeout_seconds": policy.post_restart_timeout_seconds,
        "rolling_window_seconds": policy.rolling_window_seconds,
        "startup_grace_seconds": policy.startup_grace_seconds,
        "verification_timeout_seconds": policy.verification_timeout_seconds,
    }


def _serialize_incident(incident: FleetIncident) -> dict[str, object]:
    """Serialize one bounded incident without endpoint or payload data."""
    return {
        "cause": incident.cause,
        "detail": incident.detail,
        "incident_id": incident.incident_id,
        "miner_id": str(incident.miner_id),
        "occurred_at": incident.occurred_at.isoformat(),
        "outcome": incident.outcome,
    }


def _as_string_mapping(value: object) -> dict[str, object] | None:
    """Narrow untrusted JSON-shaped data without leaking ``Any`` inward."""
    if not isinstance(value, dict):
        return None
    mapping: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            return None
        mapping[key] = item
    return mapping


def _stored_optional_text(record: dict[str, object], key: str) -> str | None:
    """Read a bounded printable optional stored string."""
    value = record.get(key)
    if value is None:
        return None
    return _validate_text(value, _MAX_TEXT_LENGTH)


def _stored_required_text(record: dict[str, object], key: str, limit: int) -> str:
    """Read a bounded required stored string."""
    value = record.get(key)
    if value is None:
        raise ValueError("missing stored text")
    return _validate_text(value, limit)


def _stored_optional_hostname(record: dict[str, object]) -> str | None:
    """Validate the only persisted text used directly as a device name."""
    hostname = _stored_optional_text(record, "hostname")
    if hostname is None or _HOSTNAME_PATTERN.fullmatch(hostname) is not None:
        return hostname
    raise ValueError("invalid hostname")


def _stored_bool(
    record: dict[str, object], key: str, *, default: bool | None = None
) -> bool:
    """Read a strict stored boolean with an optional migration default."""
    value = record.get(key, default)
    if not isinstance(value, bool):
        raise ValueError("invalid stored boolean")
    return value


def _stored_int(record: dict[str, object], key: str) -> int:
    """Read a strict finite stored integer."""
    value = record.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("invalid stored integer")
    return value


def _stored_float(record: dict[str, object], key: str) -> float:
    """Read a strict finite stored numeric value."""
    value = record.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("invalid stored number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("invalid stored number")
    return number


def _stored_datetime(value: object) -> datetime:
    """Read an aware ISO-8601 timestamp from storage."""
    if not isinstance(value, str):
        raise ValueError("invalid stored timestamp")
    try:
        timestamp = datetime.fromisoformat(value)
    except ValueError:
        raise ValueError("invalid stored timestamp") from None
    if timestamp.tzinfo is None:
        raise ValueError("invalid stored timestamp")
    return timestamp.astimezone(UTC)


def _validate_optional_display_name(value: object) -> str | None:
    """Validate an optional administrator-selected display name."""
    if value is None:
        return None
    return _validate_text(value, _MAX_TEXT_LENGTH)


def _validate_incident_text(value: object) -> str:
    """Validate bounded incident category or outcome text."""
    return _validate_text(value, _MAX_TEXT_LENGTH)


def _validate_incident_detail(value: object) -> str:
    """Validate bounded incident detail text before persistence."""
    return _validate_text(value, _MAX_INCIDENT_DETAIL_LENGTH)


def _validate_text(value: object, limit: int) -> str:
    """Normalize a safe printable string without preserving malformed data."""
    if not isinstance(value, str):
        raise ValueError("invalid stored text")
    normalized = value.strip()
    if not normalized or len(normalized) > limit or not normalized.isprintable():
        raise ValueError("invalid stored text")
    return normalized
