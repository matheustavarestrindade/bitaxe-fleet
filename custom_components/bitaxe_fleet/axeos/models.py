"""Immutable domain models for validated AxeOS data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
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
class MinerTelemetry:
    """Optional telemetry present in a validated system-info response."""

    hashrate_gh_s: float | None
    power_w: float | None
    temperature_c: float | None


@dataclass(frozen=True, slots=True)
class MinerSnapshot:
    """One immutable observation returned by AxeOS."""

    endpoint: MinerEndpoint
    identity: MinerIdentity
    telemetry: MinerTelemetry
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class EnrolledMiner:
    """Persistent metadata for one administrator-approved miner."""

    endpoint: MinerEndpoint
    identity: MinerIdentity
