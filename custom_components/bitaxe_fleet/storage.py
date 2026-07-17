"""Versioned persistent enrollment storage."""

from __future__ import annotations

import asyncio
import logging
import re

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .axeos.errors import AxeOSError
from .axeos.models import (
    EnrolledMiner,
    MinerEndpoint,
    MinerId,
    MinerIdentity,
    MinerSnapshot,
)
from .axeos.parser import normalize_miner_id, parse_private_ipv4
from .const import DOMAIN, STORAGE_SCHEMA_VERSION

_LOGGER = logging.getLogger(__name__)
_HOSTNAME_PATTERN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,62})")


class MinerRegistry:
    """Persist and update only administrator-approved miners."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialize storage for one fleet config entry."""
        self._store = Store[dict[str, object]](
            hass,
            STORAGE_SCHEMA_VERSION,
            f"{DOMAIN}.{entry_id}",
            atomic_writes=True,
        )
        self._miners: dict[MinerId, EnrolledMiner] = {}
        self._lock = asyncio.Lock()
        self._loaded = False

    @property
    def miners(self) -> tuple[EnrolledMiner, ...]:
        """Return the currently enrolled miners."""
        return tuple(self._miners.values())

    async def async_load(self) -> None:
        """Load valid persisted enrollment records once."""
        async with self._lock:
            if self._loaded:
                return

            data: object = await self._store.async_load()
            if data is not None:
                self._miners = _deserialize_miners(data)
            self._loaded = True

    async def async_enroll(self, snapshot: MinerSnapshot) -> EnrolledMiner:
        """Create or update an explicitly approved MAC-keyed enrollment record."""
        await self.async_load()
        miner = EnrolledMiner(endpoint=snapshot.endpoint, identity=snapshot.identity)
        async with self._lock:
            self._miners[snapshot.identity.miner_id] = miner
            await self._store.async_save(self._serialize())
        return miner

    async def async_update_from_snapshot(self, snapshot: MinerSnapshot) -> None:
        """Refresh metadata for a miner that has already been enrolled."""
        await self.async_load()
        miner_id = snapshot.identity.miner_id
        miner = EnrolledMiner(endpoint=snapshot.endpoint, identity=snapshot.identity)
        async with self._lock:
            if self._miners.get(miner_id) == miner:
                return
            if miner_id not in self._miners:
                return
            self._miners[miner_id] = miner
            await self._store.async_save(self._serialize())

    def _serialize(self) -> dict[str, object]:
        """Create the closed JSON representation allowed in persistent storage."""
        miners: dict[str, object] = {}
        for miner_id, miner in self._miners.items():
            identity = miner.identity
            miners[str(miner_id)] = {
                "asic_model": identity.asic_model,
                "board_version": identity.board_version,
                "firmware_version": identity.firmware_version,
                "host": str(miner.endpoint.host),
                "hostname": identity.hostname,
                "miner_id": str(identity.miner_id),
            }
        return {"miners": miners, "schema_version": STORAGE_SCHEMA_VERSION}


def _deserialize_miners(data: object) -> dict[MinerId, EnrolledMiner]:
    """Validate storage data and isolate corrupt individual records."""
    if not isinstance(data, dict):
        _LOGGER.warning("Ignoring invalid Bitaxe Fleet enrollment storage")
        return {}

    root: dict[str, object] = {}
    for key, value in data.items():
        if not isinstance(key, str):
            _LOGGER.warning("Ignoring invalid Bitaxe Fleet enrollment storage")
            return {}
        root[key] = value

    schema_version = root.get("schema_version")
    if (
        not isinstance(schema_version, int)
        or isinstance(schema_version, bool)
        or schema_version != STORAGE_SCHEMA_VERSION
    ):
        _LOGGER.warning("Ignoring unsupported Bitaxe Fleet enrollment storage")
        return {}

    raw_miners = root.get("miners")
    if not isinstance(raw_miners, dict):
        _LOGGER.warning("Ignoring invalid Bitaxe Fleet enrollment storage")
        return {}

    miners: dict[MinerId, EnrolledMiner] = {}
    for key, value in raw_miners.items():
        if not isinstance(key, str):
            _LOGGER.warning("Ignoring invalid stored Bitaxe Fleet miner")
            continue
        miner = _deserialize_miner(value)
        if miner is None or key != str(miner.identity.miner_id):
            _LOGGER.warning("Ignoring invalid stored Bitaxe Fleet miner")
            continue
        miners[miner.identity.miner_id] = miner
    return miners


def _deserialize_miner(value: object) -> EnrolledMiner | None:
    """Convert one closed storage record to a validated domain object."""
    if not isinstance(value, dict):
        return None

    record: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            return None
        record[key] = item

    try:
        miner_id = normalize_miner_id(record.get("miner_id"))
        endpoint = MinerEndpoint(host=parse_private_ipv4(record.get("host")))
        identity = MinerIdentity(
            miner_id=miner_id,
            hostname=_stored_optional_hostname(record),
            asic_model=_stored_optional_text(record, "asic_model"),
            board_version=_stored_optional_text(record, "board_version"),
            firmware_version=_stored_optional_text(record, "firmware_version"),
        )
    except AxeOSError, ValueError:
        return None
    return EnrolledMiner(endpoint=endpoint, identity=identity)


def _stored_optional_text(record: dict[str, object], key: str) -> str | None:
    """Validate a persisted optional text value from the closed schema."""
    value = record.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError
    normalized = value.strip()
    if not normalized or len(normalized) > 128 or not normalized.isprintable():
        raise ValueError
    return normalized


def _stored_optional_hostname(record: dict[str, object]) -> str | None:
    """Validate the only persisted text field used directly as a device name."""
    hostname = _stored_optional_text(record, "hostname")
    if hostname is None or _HOSTNAME_PATTERN.fullmatch(hostname) is not None:
        return hostname
    raise ValueError
