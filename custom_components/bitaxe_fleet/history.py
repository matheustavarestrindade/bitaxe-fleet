"""Bounded miner and fleet telemetry history from Home Assistant Recorder."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final, cast

from homeassistant.components.recorder import history as recorder_history
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.recorder import get_instance

from .axeos.models import MinerId
from .const import DOMAIN, HISTORY_WINDOW, MAX_HISTORY_POINTS

_HISTORY_SENSORS: Final = {
    "hashrate_gh_s": "hashrate",
    "power_w": "power",
    "temperature_c": "temperature",
}
_FLEET_HISTORY_SENSORS: Final = {
    "hashrate": "total_hashrate",
    "power": "total_power",
    "efficiency": "efficiency",
}


@dataclass(frozen=True, slots=True)
class TelemetryHistoryPoint:
    """One numeric-or-unavailable recorder observation for a graph series."""

    observed_at: datetime
    value: float | None


@dataclass(frozen=True, slots=True)
class MinerTelemetryHistory:
    """Bounded graph data for the three core miner telemetry measurements."""

    start_at: datetime
    end_at: datetime
    recorder_available: bool
    hashrate_gh_s: tuple[TelemetryHistoryPoint, ...]
    power_w: tuple[TelemetryHistoryPoint, ...]
    temperature_c: tuple[TelemetryHistoryPoint, ...]


@dataclass(frozen=True, slots=True)
class FleetTelemetryHistory:
    """One bounded aggregate history series selected by a fixed metric name."""

    start_at: datetime
    end_at: datetime
    recorder_available: bool
    metric: str
    points: tuple[TelemetryHistoryPoint, ...]


async def async_get_miner_telemetry_history(
    hass: HomeAssistant, miner_id: MinerId
) -> MinerTelemetryHistory:
    """Load one fixed recorder window without exposing caller-selected entities."""
    end_at = datetime.now(UTC)
    start_at = end_at - HISTORY_WINDOW
    entity_ids = _history_entity_ids(hass, miner_id)
    recorder_available, series = await _async_get_history_series(
        hass, start_at, end_at, entity_ids
    )
    return MinerTelemetryHistory(
        start_at=start_at,
        end_at=end_at,
        recorder_available=recorder_available,
        hashrate_gh_s=series.get("hashrate_gh_s", ()),
        power_w=series.get("power_w", ()),
        temperature_c=series.get("temperature_c", ()),
    )


async def async_get_fleet_telemetry_history(
    hass: HomeAssistant, entry_id: str, metric: str
) -> FleetTelemetryHistory:
    """Load one fixed fleet aggregate series without caller-selected entities."""
    sensor_key = _FLEET_HISTORY_SENSORS.get(metric)
    if sensor_key is None:
        msg = "Unsupported fleet history metric"
        raise ValueError(msg)

    end_at = datetime.now(UTC)
    start_at = end_at - HISTORY_WINDOW
    entity_id = _fleet_history_entity_id(hass, entry_id, sensor_key)
    recorder_available, series = await _async_get_history_series(
        hass,
        start_at,
        end_at,
        {"series": entity_id} if entity_id is not None else {},
    )
    return FleetTelemetryHistory(
        start_at=start_at,
        end_at=end_at,
        recorder_available=recorder_available,
        metric=metric,
        points=series.get("series", ()),
    )


def _history_entity_ids(hass: HomeAssistant, miner_id: MinerId) -> dict[str, str]:
    """Resolve stable unique IDs so user-renamed entity IDs remain supported."""
    unique_id_prefix = str(miner_id).replace(":", "")
    entity_registry = er.async_get(hass)
    entity_ids: dict[str, str] = {}
    for series_key, sensor_key in _HISTORY_SENSORS.items():
        entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{unique_id_prefix}_{sensor_key}"
        )
        if entity_id is not None:
            entity_ids[series_key] = entity_id
    return entity_ids


def _fleet_history_entity_id(
    hass: HomeAssistant, entry_id: str, sensor_key: str
) -> str | None:
    """Resolve one stable fleet aggregate ID after an entity rename."""
    return er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{entry_id}_{sensor_key}"
    )


async def _async_get_history_series(
    hass: HomeAssistant,
    start_at: datetime,
    end_at: datetime,
    entity_ids: Mapping[str, str],
) -> tuple[bool, dict[str, tuple[TelemetryHistoryPoint, ...]]]:
    """Query fixed entity IDs off the event loop and retain unavailable gaps."""
    try:
        recorder = get_instance(hass)
    except KeyError:
        return False, {}
    if not entity_ids:
        return True, {}

    try:
        states_by_entity_id = await recorder.async_add_executor_job(
            _query_recorder, hass, start_at, end_at, list(entity_ids.values())
        )
    except RuntimeError:
        return False, {}

    return (
        True,
        {
            series_key: _series_from_states(states_by_entity_id.get(entity_id, []))
            for series_key, entity_id in entity_ids.items()
        },
    )


def _query_recorder(
    hass: HomeAssistant,
    start_at: datetime,
    end_at: datetime,
    entity_ids: list[str],
) -> dict[str, list[State]]:
    """Read state history off the event loop with no attributes or raw payloads."""
    return cast(
        dict[str, list[State]],
        recorder_history.get_significant_states(
            hass,
            start_at,
            end_at,
            entity_ids,
            include_start_time_state=True,
            significant_changes_only=False,
            no_attributes=True,
        ),
    )


def _series_from_states(states: list[State]) -> tuple[TelemetryHistoryPoint, ...]:
    """Normalize state strings to finite graph values while retaining outages."""
    points = [
        TelemetryHistoryPoint(
            observed_at=state.last_updated.astimezone(UTC),
            value=_finite_value(state.state),
        )
        for state in states
    ]
    if len(points) <= MAX_HISTORY_POINTS:
        return tuple(points)
    return tuple(
        points[round(index * (len(points) - 1) / (MAX_HISTORY_POINTS - 1))]
        for index in range(MAX_HISTORY_POINTS)
    )


def _finite_value(value: str) -> float | None:
    """Represent unavailable or malformed recorder states as a graph gap."""
    try:
        number = float(value)
    except ValueError:
        return None
    return number if math.isfinite(number) else None
