"""Tests for fresh-snapshot Bitaxe Fleet aggregate calculations."""

from __future__ import annotations

from datetime import UTC, datetime
from ipaddress import IPv4Address

import pytest

from custom_components.bitaxe_fleet.aggregates import calculate_fleet_aggregates
from custom_components.bitaxe_fleet.axeos.models import (
    MinerEndpoint,
    MinerHealth,
    MinerIdentity,
    MinerSnapshot,
    MinerTelemetry,
)
from custom_components.bitaxe_fleet.axeos.parser import normalize_miner_id


def _snapshot(
    *,
    hashrate_gh_s: float | None = 600.0,
    power_w: float | None = 18.0,
    uptime_seconds: int | None = 3_600,
    best_difficulty: float | None = 1_000_000.0,
    best_session_difficulty: float | None = 500_000.0,
    mining_paused: bool | None = False,
    overheat_mode: int | None = 0,
    power_fault: str | None = None,
) -> MinerSnapshot:
    """Build one valid current snapshot with independently optional fleet metrics."""
    return MinerSnapshot(
        endpoint=MinerEndpoint(IPv4Address("192.168.10.25")),
        identity=MinerIdentity(
            miner_id=normalize_miner_id("02:12:34:56:78:9a"),
            hostname="bitaxe-lab",
            asic_model="BM1368",
            board_version="Bitaxe Supra",
            firmware_version="v2.14.2",
        ),
        telemetry=MinerTelemetry(
            hashrate_gh_s=hashrate_gh_s,
            power_w=power_w,
            temperature_c=54.0,
            uptime_seconds=uptime_seconds,
            best_difficulty=best_difficulty,
            best_session_difficulty=best_session_difficulty,
        ),
        observed_at=datetime.now(UTC),
        health=MinerHealth(
            mining_paused=mining_paused,
            overheat_mode=overheat_mode,
            power_fault=power_fault,
        ),
    )


def test_fleet_aggregates_preserve_partial_coverage() -> None:
    """Available metrics contribute while every coverage count remains explicit."""
    aggregates = calculate_fleet_aggregates(
        3,
        (
            _snapshot(
                hashrate_gh_s=600.0,
                power_w=18.0,
                uptime_seconds=3_600,
                best_difficulty=1_250_000.0,
                best_session_difficulty=750_000.0,
            ),
            _snapshot(
                hashrate_gh_s=None,
                power_w=20.0,
                uptime_seconds=None,
                best_difficulty=2_500_000.0,
                best_session_difficulty=900_000.0,
                overheat_mode=1,
            ),
        ),
    )

    assert aggregates.enabled_miners == 3
    assert aggregates.online_miners == 2
    assert aggregates.total_hashrate_gh_s == 600.0
    assert aggregates.total_hashrate_th_s == 0.6
    assert aggregates.total_power_w == 38.0
    assert aggregates.efficiency_j_th == pytest.approx(63.333333333333336)
    assert aggregates.total_uptime_seconds == 3_600
    assert aggregates.best_difficulty == 2_500_000.0
    assert aggregates.best_session_difficulty == 900_000.0
    assert aggregates.hashrate_coverage == 1
    assert aggregates.power_coverage == 2
    assert aggregates.uptime_coverage == 1
    assert aggregates.best_difficulty_coverage == 2
    assert aggregates.best_session_difficulty_coverage == 2
    assert aggregates.unhealthy_miners == 1
    assert aggregates.unhealthy_coverage == 2
    assert aggregates.overheating_miners == 1
    assert aggregates.overheat_coverage == 2


def test_fleet_aggregates_keep_missing_metrics_unknown() -> None:
    """A fresh but unsupported value is not emitted as a fabricated zero."""
    aggregates = calculate_fleet_aggregates(
        1,
        (
            _snapshot(
                hashrate_gh_s=None,
                power_w=None,
                uptime_seconds=None,
                best_difficulty=None,
                best_session_difficulty=None,
                mining_paused=None,
                overheat_mode=None,
            ),
        ),
    )

    assert aggregates.online_miners == 1
    assert aggregates.total_hashrate_gh_s is None
    assert aggregates.total_hashrate_th_s is None
    assert aggregates.total_power_w is None
    assert aggregates.efficiency_j_th is None
    assert aggregates.total_uptime_seconds is None
    assert aggregates.best_difficulty is None
    assert aggregates.best_session_difficulty is None
    assert aggregates.best_session_difficulty_coverage == 0
    assert aggregates.unhealthy_miners is None
    assert aggregates.overheating_miners is None


def test_fleet_aggregates_keep_a_valid_zero_hashrate() -> None:
    """A reported zero is retained and can be classified independently of absence."""
    aggregates = calculate_fleet_aggregates(
        1,
        (_snapshot(hashrate_gh_s=0.0, power_w=0.0),),
    )

    assert aggregates.total_hashrate_gh_s == 0.0
    assert aggregates.total_power_w == 0.0
    assert aggregates.efficiency_j_th is None
    assert aggregates.unhealthy_miners == 1
    assert aggregates.overheating_miners == 0
