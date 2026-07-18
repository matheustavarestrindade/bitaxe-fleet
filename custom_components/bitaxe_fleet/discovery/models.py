"""Validated discovery candidates and scan status values."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from ..axeos.models import MinerEndpoint, MinerId, MinerIdentity, MinerSnapshot


class DiscoverySource(StrEnum):
    """A read-only source that observed a possible miner endpoint."""

    MDNS = "mdns"
    ACTIVE_SCAN = "active_scan"
    MANUAL = "manual"


@dataclass(frozen=True, slots=True)
class DiscoveryCandidate:
    """A validated but not yet administrator-approved AxeOS miner."""

    endpoint: MinerEndpoint
    identity: MinerIdentity
    first_seen_at: datetime
    last_seen_at: datetime
    source: DiscoverySource

    @classmethod
    def from_snapshot(
        cls, snapshot: MinerSnapshot, source: DiscoverySource
    ) -> DiscoveryCandidate:
        """Create an approval candidate from one validated read-only observation."""
        return cls(
            endpoint=snapshot.endpoint,
            identity=snapshot.identity,
            first_seen_at=snapshot.observed_at,
            last_seen_at=snapshot.observed_at,
            source=source,
        )

    def updated(
        self, snapshot: MinerSnapshot, source: DiscoverySource
    ) -> DiscoveryCandidate:
        """Keep a stable candidate while refreshing its mutable endpoint metadata."""
        return DiscoveryCandidate(
            endpoint=snapshot.endpoint,
            identity=snapshot.identity,
            first_seen_at=self.first_seen_at,
            last_seen_at=snapshot.observed_at,
            source=source,
        )


@dataclass(frozen=True, slots=True)
class DiscoveryScanStatus:
    """Bounded progress information for one explicit private-network scan."""

    network: str | None
    running: bool
    total_hosts: int
    completed_hosts: int
    discovered_candidates: int
    started_at: datetime | None
    completed_at: datetime | None
    error: str | None

    @classmethod
    def idle(cls) -> DiscoveryScanStatus:
        """Return the initial no-scan status."""
        return cls(
            network=None,
            running=False,
            total_hosts=0,
            completed_hosts=0,
            discovered_candidates=0,
            started_at=None,
            completed_at=None,
            error=None,
        )


@dataclass(frozen=True, slots=True)
class DiscoveryApproval:
    """A candidate identity paired with the snapshot used for final approval."""

    miner_id: MinerId
    snapshot: MinerSnapshot
