"""Tests for safe WebSocket boundary validation and readiness behavior."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from unittest.mock import patch

import pytest
from homeassistant.components.websocket_api.connection import ActiveConnection
from homeassistant.core import HomeAssistant

from custom_components.bitaxe_fleet.aggregates import FleetAggregates
from custom_components.bitaxe_fleet.axeos.models import OverheatPolicy
from custom_components.bitaxe_fleet.axeos.parser import normalize_miner_id
from custom_components.bitaxe_fleet.history import (
    FleetTelemetryHistory,
    MinerTelemetryHistory,
    TelemetryHistoryPoint,
)
from custom_components.bitaxe_fleet.websocket import (
    _fleet_aggregates_dto,
    _fleet_history_dto,
    _history_dto,
    _policy_from_message,
    _runtime_or_error,
    async_register_websocket_commands,
    websocket_fleet_history,
)


class _Connection:
    """Capture WebSocket error messages without a live authenticated transport."""

    def __init__(self) -> None:
        """Initialize an empty ordered error collection."""
        self.errors: list[tuple[int, str, str]] = []

    def send_error(self, message_id: int, code: str, message: str) -> None:
        """Record one server-side error response."""
        self.errors.append((message_id, code, message))


def _valid_policy() -> dict[str, object]:
    """Return the full exact policy DTO accepted by the server boundary."""
    return {
        "automatic_profile_restore_enabled": True,
        "automatic_recovery_enabled": True,
        "consecutive_unhealthy_required": 3,
        "cooldown_seconds": 600,
        "max_attempts": 3,
        "overheat_policy": "restore_after_cooldown",
        "post_restart_timeout_seconds": 180,
        "rolling_window_seconds": 3600,
        "startup_grace_seconds": 180,
        "verification_timeout_seconds": 60,
    }


def test_websocket_reports_not_ready_without_an_internal_error(
    hass: HomeAssistant,
) -> None:
    """Commands sent before entry setup receive a stable safe error response."""
    connection = _Connection()

    runtime = _runtime_or_error(
        hass,
        cast(ActiveConnection, connection),
        {"id": 17},
    )

    assert runtime is None
    assert connection.errors == [(17, "not_ready", "Bitaxe Fleet is not ready")]


def test_websocket_registers_the_fleet_history_command(hass: HomeAssistant) -> None:
    """The automatic Lovelace card endpoint is available with panel commands."""
    with patch(
        "custom_components.bitaxe_fleet.websocket.async_register_command"
    ) as register_command:
        async_register_websocket_commands(hass)

    register_command.assert_any_call(hass, websocket_fleet_history)


def test_policy_boundary_requires_an_exact_strict_shape() -> None:
    """The panel cannot omit, extend, or loosely type recovery policy values."""
    policy = _policy_from_message(_valid_policy())

    assert policy.automatic_recovery_enabled is True
    assert policy.overheat_policy is OverheatPolicy.RESTORE_AFTER_COOLDOWN

    unknown_key = _valid_policy()
    unknown_key["unexpected"] = "value"
    with pytest.raises(ValueError, match="invalid policy"):
        _policy_from_message(unknown_key)

    bad_boolean = _valid_policy()
    bad_boolean["automatic_recovery_enabled"] = 1
    with pytest.raises(ValueError, match="invalid policy"):
        _policy_from_message(bad_boolean)


def test_history_dto_exposes_only_bounded_graph_data() -> None:
    """History responses retain points and omit recorder entity identifiers."""
    observed_at = datetime(2026, 7, 17, 12, 0, tzinfo=UTC)
    history = MinerTelemetryHistory(
        start_at=observed_at,
        end_at=observed_at,
        recorder_available=True,
        hashrate_gh_s=(TelemetryHistoryPoint(observed_at, 650.0),),
        power_w=(TelemetryHistoryPoint(observed_at, None),),
        temperature_c=(),
    )

    dto = _history_dto(normalize_miner_id("02:12:34:56:78:9a"), history)

    assert dto["available"] is True
    assert dto["schema_version"] == 1
    assert dto["series"] == {
        "hashrate_gh_s": [{"at": observed_at.isoformat(), "value": 650.0}],
        "power_w": [{"at": observed_at.isoformat(), "value": None}],
        "temperature_c": [],
    }
    assert "sensor." not in str(dto)


def test_fleet_aggregate_dto_retains_values_and_coverage() -> None:
    """Panel aggregate output contains no per-miner identity or endpoint data."""
    aggregates = FleetAggregates(
        enabled_miners=3,
        online_miners=2,
        hashrate_coverage=1,
        power_coverage=2,
        uptime_coverage=1,
        best_difficulty_coverage=2,
        unhealthy_coverage=2,
        overheat_coverage=1,
        total_hashrate_gh_s=650.0,
        total_hashrate_th_s=0.65,
        total_power_w=36.0,
        efficiency_j_th=55.38461538461539,
        total_uptime_seconds=3_600,
        best_difficulty=1_250_000.0,
        unhealthy_miners=1,
        overheating_miners=0,
    )

    dto = _fleet_aggregates_dto(aggregates)

    assert dto["total_hashrate_gh_s"] == 650.0
    assert dto["best_difficulty"] == 1_250_000.0
    assert dto["hashrate_coverage"] == 1
    assert dto["power_coverage"] == 2
    assert "miner_id" not in dto
    assert "endpoint" not in dto


def test_fleet_history_dto_exposes_one_bounded_metric_series() -> None:
    """Dashboard graph responses omit fleet entry and recorder entity IDs."""
    observed_at = datetime(2026, 7, 17, 12, 0, tzinfo=UTC)
    history = FleetTelemetryHistory(
        start_at=observed_at,
        end_at=observed_at,
        recorder_available=True,
        metric="efficiency",
        points=(TelemetryHistoryPoint(observed_at, 25.4),),
    )

    dto = _fleet_history_dto(history)

    assert dto == {
        "available": True,
        "end_at": observed_at.isoformat(),
        "metric": "efficiency",
        "schema_version": 1,
        "series": [{"at": observed_at.isoformat(), "value": 25.4}],
        "start_at": observed_at.isoformat(),
    }
    assert "sensor." not in str(dto)
    assert "entry-id" not in str(dto)
