"""Tests for same-MAC coordinator polling and mutating action safety."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from ipaddress import IPv4Address
from typing import cast

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bitaxe_fleet.axeos.client import AxeOSClientProtocol
from custom_components.bitaxe_fleet.axeos.models import (
    MinerEndpoint,
    MinerHealth,
    MinerIdentity,
    MinerSnapshot,
    MinerTelemetry,
)
from custom_components.bitaxe_fleet.axeos.parser import normalize_miner_id
from custom_components.bitaxe_fleet.const import DOMAIN
from custom_components.bitaxe_fleet.coordinator import MinerCoordinator
from custom_components.bitaxe_fleet.storage import MinerRegistry


class _FakeClient:
    """A typed-enough client double that records any attempted restart."""

    def __init__(self, snapshot: MinerSnapshot) -> None:
        """Initialize one read response and zero mutation calls."""
        self.snapshot = snapshot
        self.restart_calls = 0

    async def async_get_system_info(self) -> MinerSnapshot:
        """Return the endpoint's controlled system-info response."""
        return self.snapshot

    async def async_restart(self) -> None:
        """Record a restart request that must happen only after a same-MAC read."""
        self.restart_calls += 1

    async def async_pause(self) -> None:
        """Provide an unused protocol method for named coordinator actions."""

    async def async_resume(self) -> None:
        """Provide an unused protocol method for named coordinator actions."""

    async def async_identify(self) -> None:
        """Provide an unused protocol method for named coordinator actions."""


def _snapshot(mac: str) -> MinerSnapshot:
    """Create one synthetic response at the stable enrolled endpoint."""
    return MinerSnapshot(
        endpoint=MinerEndpoint(IPv4Address("192.168.10.25")),
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


async def test_action_refuses_an_ip_reused_by_a_different_miner(
    hass: HomeAssistant,
) -> None:
    """A fresh read with a changed MAC blocks the POST mutation completely."""
    expected = _snapshot("02:12:34:56:78:9a")
    client = _FakeClient(_snapshot("02:12:34:56:78:9b"))
    registry = MinerRegistry(hass, "test-entry")
    miner = await registry.async_enroll(expected)
    entry = MockConfigEntry(domain=DOMAIN)
    coordinator = MinerCoordinator(
        hass,
        entry,
        miner,
        cast(
            Callable[[MinerEndpoint], AxeOSClientProtocol],
            lambda _: client,
        ),
        registry,
    )

    with pytest.raises(UpdateFailed):
        await coordinator.async_call_client_action("restart")

    assert client.restart_calls == 0


async def test_action_runs_after_a_fresh_same_mac_read(hass: HomeAssistant) -> None:
    """The successful action path performs one verification GET and POST."""
    expected = _snapshot("02:12:34:56:78:9a")
    client = _FakeClient(expected)
    registry = MinerRegistry(hass, "test-entry")
    miner = await registry.async_enroll(expected)
    entry = MockConfigEntry(domain=DOMAIN)
    coordinator = MinerCoordinator(
        hass,
        entry,
        miner,
        cast(
            Callable[[MinerEndpoint], AxeOSClientProtocol],
            lambda _: client,
        ),
        registry,
    )

    await coordinator.async_call_client_action("restart")

    assert client.restart_calls == 1
