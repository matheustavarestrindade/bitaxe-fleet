"""Tests for bounded recorder-backed miner telemetry history."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import cast
from unittest.mock import patch

from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from custom_components.bitaxe_fleet.axeos.parser import normalize_miner_id
from custom_components.bitaxe_fleet.const import DOMAIN, HISTORY_WINDOW
from custom_components.bitaxe_fleet.history import (
    async_get_fleet_telemetry_history,
    async_get_miner_telemetry_history,
)


class _Recorder:
    """Return controlled recorder results without a database connection."""

    def __init__(self, result: dict[str, list[State]]) -> None:
        """Initialize the recorder result and captured executor arguments."""
        self.result = result
        self.calls: list[tuple[Callable[..., object], tuple[object, ...]]] = []

    async def async_add_executor_job(
        self, target: Callable[..., object], *args: object
    ) -> dict[str, list[State]]:
        """Capture the bounded query without running the real recorder backend."""
        self.calls.append((target, args))
        return self.result


def _register_history_sensors(hass: HomeAssistant) -> dict[str, str]:
    """Create renamed registry entries to prove history does not infer entity IDs."""
    unique_id_prefix = "02123456789a"
    entity_registry = er.async_get(hass)
    return {
        sensor_key: entity_registry.async_get_or_create(
            "sensor",
            DOMAIN,
            f"{unique_id_prefix}_{sensor_key}",
            suggested_object_id=f"renamed_{sensor_key}",
        ).entity_id
        for sensor_key in ("hashrate", "power", "temperature")
    }


def _register_fleet_history_sensors(hass: HomeAssistant) -> dict[str, str]:
    """Create renamed fleet entities to prove aggregate history is registry-safe."""
    entity_registry = er.async_get(hass)
    return {
        sensor_key: entity_registry.async_get_or_create(
            "sensor",
            DOMAIN,
            f"entry-id_{sensor_key}",
            suggested_object_id=f"renamed_fleet_{sensor_key}",
        ).entity_id
        for sensor_key in ("total_hashrate", "total_power", "efficiency")
    }


async def test_history_reads_renamed_entities_and_preserves_gaps(
    hass: HomeAssistant,
) -> None:
    """A fixed recorder query returns only finite values and unavailable gaps."""
    entity_ids = _register_history_sensors(hass)
    observed_at = datetime(2026, 7, 17, 12, 0, tzinfo=UTC)
    recorder = _Recorder(
        {
            entity_ids["hashrate"]: [
                State(entity_ids["hashrate"], "650.5", last_updated=observed_at),
                State(
                    entity_ids["hashrate"],
                    "unavailable",
                    last_updated=observed_at + timedelta(minutes=1),
                ),
            ],
            entity_ids["power"]: [
                State(entity_ids["power"], "17.4", last_updated=observed_at)
            ],
            entity_ids["temperature"]: [
                State(entity_ids["temperature"], "NaN", last_updated=observed_at)
            ],
        }
    )

    with patch(
        "custom_components.bitaxe_fleet.history.get_instance", return_value=recorder
    ):
        history = await async_get_miner_telemetry_history(
            hass, normalize_miner_id("02:12:34:56:78:9a")
        )

    assert history.recorder_available is True
    assert [point.value for point in history.hashrate_gh_s] == [650.5, None]
    assert [point.value for point in history.power_w] == [17.4]
    assert [point.value for point in history.temperature_c] == [None]
    assert len(recorder.calls) == 1
    _, arguments = recorder.calls[0]
    assert arguments[3] == list(entity_ids.values())
    start_at = cast(datetime, arguments[1])
    end_at = cast(datetime, arguments[2])
    assert end_at - start_at == HISTORY_WINDOW


async def test_history_reports_unavailable_recorder_without_storing_samples(
    hass: HomeAssistant,
) -> None:
    """A disabled Recorder results in a stable unavailable graph state."""
    with patch(
        "custom_components.bitaxe_fleet.history.get_instance", side_effect=KeyError
    ):
        history = await async_get_miner_telemetry_history(
            hass, normalize_miner_id("02:12:34:56:78:9a")
        )

    assert history.recorder_available is False
    assert history.hashrate_gh_s == ()
    assert history.power_w == ()
    assert history.temperature_c == ()


async def test_fleet_history_reads_only_the_selected_renamed_aggregate(
    hass: HomeAssistant,
) -> None:
    """A card metric resolves its stable hub entity ID and keeps graph gaps."""
    entity_ids = _register_fleet_history_sensors(hass)
    observed_at = datetime(2026, 7, 17, 12, 0, tzinfo=UTC)
    recorder = _Recorder(
        {
            entity_ids["efficiency"]: [
                State(entity_ids["efficiency"], "25.4", last_updated=observed_at),
                State(
                    entity_ids["efficiency"],
                    "unavailable",
                    last_updated=observed_at + timedelta(minutes=1),
                ),
            ]
        }
    )

    with patch(
        "custom_components.bitaxe_fleet.history.get_instance", return_value=recorder
    ):
        history = await async_get_fleet_telemetry_history(
            hass, "entry-id", "efficiency"
        )

    assert history.metric == "efficiency"
    assert history.recorder_available is True
    assert [point.value for point in history.points] == [25.4, None]
    assert len(recorder.calls) == 1
    _, arguments = recorder.calls[0]
    assert arguments[3] == [entity_ids["efficiency"]]
