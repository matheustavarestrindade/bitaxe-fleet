"""Typed fleet metrics derived from fresh enabled-miner snapshots."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .axeos.models import MinerSnapshot
from .recovery import snapshot_condition


@dataclass(frozen=True, slots=True)
class FleetAggregates:
    """Current fleet totals and explicit coverage for each optional metric."""

    enabled_miners: int
    online_miners: int
    hashrate_coverage: int
    power_coverage: int
    uptime_coverage: int
    best_difficulty_coverage: int
    unhealthy_coverage: int
    overheat_coverage: int
    total_hashrate_gh_s: float | None
    total_hashrate_th_s: float | None
    total_power_w: float | None
    efficiency_j_th: float | None
    total_uptime_seconds: int | None
    best_difficulty: float | None
    unhealthy_miners: int | None
    overheating_miners: int | None

    @classmethod
    def empty(cls) -> FleetAggregates:
        """Return a no-data aggregate for a newly created fleet runtime."""
        return cls(
            enabled_miners=0,
            online_miners=0,
            hashrate_coverage=0,
            power_coverage=0,
            uptime_coverage=0,
            best_difficulty_coverage=0,
            unhealthy_coverage=0,
            overheat_coverage=0,
            total_hashrate_gh_s=None,
            total_hashrate_th_s=None,
            total_power_w=None,
            efficiency_j_th=None,
            total_uptime_seconds=None,
            best_difficulty=None,
            unhealthy_miners=None,
            overheating_miners=None,
        )


def calculate_fleet_aggregates(
    enabled_miners: int, snapshots: tuple[MinerSnapshot, ...]
) -> FleetAggregates:
    """Aggregate only fresh snapshots without converting absent data into zero."""
    hashrates: list[float] = []
    powers: list[float] = []
    uptimes: list[int] = []
    best_difficulties: list[float] = []
    unhealthy_coverage = 0
    overheat_coverage = 0
    unhealthy_miners = 0
    overheating_miners = 0

    for snapshot in snapshots:
        telemetry = snapshot.telemetry
        if telemetry.hashrate_gh_s is not None:
            hashrates.append(telemetry.hashrate_gh_s)
        if telemetry.power_w is not None:
            powers.append(telemetry.power_w)
        if telemetry.uptime_seconds is not None:
            uptimes.append(telemetry.uptime_seconds)
        if telemetry.best_difficulty is not None:
            best_difficulties.append(telemetry.best_difficulty)

        condition = snapshot_condition(snapshot)
        if condition != "unknown":
            unhealthy_coverage += 1
            if condition not in {"healthy", "paused"}:
                unhealthy_miners += 1

        overheat_mode = snapshot.health.overheat_mode
        if overheat_mode is not None:
            overheat_coverage += 1
            if overheat_mode != 0:
                overheating_miners += 1

    total_hashrate = _sum_or_none(hashrates)
    total_power = _sum_or_none(powers)
    return FleetAggregates(
        enabled_miners=enabled_miners,
        online_miners=len(snapshots),
        hashrate_coverage=len(hashrates),
        power_coverage=len(powers),
        uptime_coverage=len(uptimes),
        best_difficulty_coverage=len(best_difficulties),
        unhealthy_coverage=unhealthy_coverage,
        overheat_coverage=overheat_coverage,
        total_hashrate_gh_s=total_hashrate,
        total_hashrate_th_s=(
            total_hashrate / 1_000 if total_hashrate is not None else None
        ),
        total_power_w=total_power,
        efficiency_j_th=(
            total_power / (total_hashrate / 1_000)
            if total_power is not None
            and total_hashrate is not None
            and total_hashrate > 0
            else None
        ),
        total_uptime_seconds=sum(uptimes) if uptimes else None,
        best_difficulty=max(best_difficulties) if best_difficulties else None,
        unhealthy_miners=unhealthy_miners if unhealthy_coverage else None,
        overheating_miners=overheating_miners if overheat_coverage else None,
    )


def _sum_or_none(values: list[float]) -> float | None:
    """Keep a fully absent metric distinct from a valid aggregate of zero."""
    if not values:
        return None
    return math.fsum(values)
