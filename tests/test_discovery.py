"""Tests for explicit candidate discovery and private-network boundaries."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from ipaddress import IPv4Address
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from zeroconf import Zeroconf

from custom_components.bitaxe_fleet.axeos.client import AxeOSClient
from custom_components.bitaxe_fleet.axeos.errors import AxeOSInvalidEndpointError
from custom_components.bitaxe_fleet.axeos.models import (
    MinerEndpoint,
    MinerHealth,
    MinerIdentity,
    MinerSnapshot,
    MinerTelemetry,
)
from custom_components.bitaxe_fleet.axeos.parser import normalize_miner_id
from custom_components.bitaxe_fleet.discovery.active_scan import parse_private_network
from custom_components.bitaxe_fleet.discovery.manager import (
    CandidateChangedError,
    DiscoveryManager,
)
from custom_components.bitaxe_fleet.discovery.models import DiscoverySource
from custom_components.bitaxe_fleet.storage import MinerRegistry


class _FakeClient:
    """Return controlled system-info snapshots without opening a socket."""

    def __init__(self, snapshots: list[MinerSnapshot]) -> None:
        """Initialize the ordered snapshots returned by each probe."""
        self._snapshots = snapshots

    async def async_get_system_info(self) -> MinerSnapshot:
        """Return the next fully validated synthetic response."""
        return self._snapshots.pop(0)


class _ServiceInfo:
    """A minimal resolved mDNS result used to exercise address filtering."""

    port = 80

    async def async_request(self, zeroconf: Zeroconf, timeout_ms: int) -> bool:
        """Report a resolved service without touching a real multicast socket."""
        del zeroconf, timeout_ms
        return True

    def parsed_addresses(self) -> list[str]:
        """Return loopback, link-local, and valid RFC 1918 addresses."""
        return ["127.0.0.1", "169.254.10.25", "192.168.10.25"]


def _snapshot(host: str, mac: str) -> MinerSnapshot:
    """Create one synthetic read-only AxeOS observation."""
    return MinerSnapshot(
        endpoint=MinerEndpoint(IPv4Address(host)),
        identity=MinerIdentity(
            miner_id=normalize_miner_id(mac),
            hostname="bitaxe-lab",
            asic_model="BM1368",
            board_version="Bitaxe Supra",
            firmware_version="v2.14.2",
        ),
        telemetry=MinerTelemetry(
            hashrate_gh_s=500.0,
            power_w=17.4,
            temperature_c=54.0,
        ),
        observed_at=datetime.now(UTC),
        health=MinerHealth(),
    )


def _manager(
    hass: HomeAssistant, registry: MinerRegistry, snapshots: list[MinerSnapshot]
) -> DiscoveryManager:
    """Create a manager with no-op runtime callbacks and a fake typed client."""
    client = _FakeClient(snapshots)

    async def known(_: MinerSnapshot, __: object) -> None:
        """Ignore known-miner notifications in isolated discovery tests."""

    async def approved(_: object) -> None:
        """Ignore approval notifications in isolated discovery tests."""

    return DiscoveryManager(
        hass,
        registry,
        cast(Callable[[MinerEndpoint], AxeOSClient], lambda _: client),
        known,
        approved,
    )


async def test_discovery_requires_a_final_same_mac_approval_read(
    hass: HomeAssistant,
) -> None:
    """A changed device at a candidate IP cannot be silently approved."""
    registry = MinerRegistry(hass, "test-entry")
    first = _snapshot("192.168.10.25", "02:12:34:56:78:9a")
    replacement = _snapshot("192.168.10.25", "02:12:34:56:78:9b")
    manager = _manager(hass, registry, [first, replacement])

    discovered = await manager._async_probe_endpoint(
        first.endpoint, DiscoverySource.ACTIVE_SCAN
    )
    assert discovered is True

    with pytest.raises(CandidateChangedError):
        await manager.async_approve_candidate(first.identity.miner_id)

    assert registry.miners == ()
    assert manager.candidates == ()


async def test_mdns_probes_only_rfc1918_ipv4_addresses(hass: HomeAssistant) -> None:
    """Loopback and link-local mDNS records cannot escape the endpoint boundary."""
    registry = MinerRegistry(hass, "test-entry")
    manager = _manager(hass, registry, [])
    probe = AsyncMock(return_value=False)

    with (
        patch(
            "custom_components.bitaxe_fleet.discovery.manager.AsyncServiceInfo",
            return_value=_ServiceInfo(),
        ),
        patch.object(manager, "_async_probe_endpoint", new=probe),
    ):
        await manager._async_probe_service(
            cast(Zeroconf, object()),
            "_axeos._sub._http._tcp.local.",
            "bitaxe._axeos._sub._http._tcp.local.",
        )

    probe.assert_awaited_once_with(
        MinerEndpoint(IPv4Address("192.168.10.25")), DiscoverySource.MDNS
    )


def test_active_scan_rejects_non_private_or_unbounded_networks() -> None:
    """Administrators can scan only compact RFC 1918 IPv4 ranges."""
    assert str(parse_private_network("192.168.10.11/30")) == "192.168.10.8/30"

    for network in ("127.0.0.0/24", "169.254.0.0/24", "192.168.0.0/16"):
        with pytest.raises(AxeOSInvalidEndpointError):
            parse_private_network(network)
