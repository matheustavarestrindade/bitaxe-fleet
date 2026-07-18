"""Tests for runtime capture/apply profile safety boundaries."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from ipaddress import IPv4Address
from typing import cast

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bitaxe_fleet.axeos.client import AxeOSClientProtocol
from custom_components.bitaxe_fleet.axeos.models import (
    AsicCapabilities,
    MinerConfiguration,
    MinerEndpoint,
    MinerHealth,
    MinerIdentity,
    MinerSnapshot,
    MinerTelemetry,
    RecoveryProfile,
)
from custom_components.bitaxe_fleet.axeos.parser import normalize_miner_id
from custom_components.bitaxe_fleet.const import DOMAIN
from custom_components.bitaxe_fleet.coordinator import MinerCoordinator
from custom_components.bitaxe_fleet.runtime import BitaxeFleetRuntime, FleetActionError


class _FakeClient:
    """Return controlled reads and retain only typed closed-profile PATCH values."""

    def __init__(self, snapshots: list[MinerSnapshot]) -> None:
        """Initialize snapshot read-back sequence and empty mutation history."""
        self._snapshots = snapshots
        self.patched_profiles: list[RecoveryProfile] = []

    async def async_get_system_info(self) -> MinerSnapshot:
        """Return the next snapshot, retaining the last for repeated safe reads."""
        if len(self._snapshots) > 1:
            return self._snapshots.pop(0)
        return self._snapshots[0]

    async def async_get_system_asic(self) -> AsicCapabilities:
        """Return capabilities that explicitly allow the test profile values."""
        return AsicCapabilities(
            asic_model="BM1368",
            device_model="Bitaxe Supra",
            swarm_color=None,
            asic_count=1,
            default_frequency_mhz=525.0,
            frequency_options_mhz=(450.0, 500.0, 525.0),
            default_voltage_mv=1200,
            voltage_options_mv=(1100, 1150, 1200),
        )

    async def async_patch_system(self, profile: RecoveryProfile) -> None:
        """Record exactly the closed profile received by the transport boundary."""
        self.patched_profiles.append(profile)


def _profile() -> RecoveryProfile:
    """Return one valid six-field recovery profile."""
    return RecoveryProfile(
        frequency_mhz=525.0,
        core_voltage_mv=1200,
        overclock_enabled=True,
        automatic_fan_speed=True,
        target_temperature_c=60,
        minimum_fan_speed_percent=25,
    )


def _snapshot(profile: RecoveryProfile) -> MinerSnapshot:
    """Create a complete system-info response matching one saved profile."""
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
            hashrate_gh_s=500.0,
            power_w=17.4,
            temperature_c=54.0,
        ),
        observed_at=datetime.now(UTC),
        configuration=MinerConfiguration(
            frequency_mhz=profile.frequency_mhz,
            core_voltage_mv=profile.core_voltage_mv,
            overclock_enabled=profile.overclock_enabled,
            automatic_fan_speed=profile.automatic_fan_speed,
            target_temperature_c=profile.target_temperature_c,
            minimum_fan_speed_percent=profile.minimum_fan_speed_percent,
            manual_fan_speed_percent=40,
        ),
        health=MinerHealth(),
    )


async def _runtime_with_client(
    hass: HomeAssistant, client: _FakeClient
) -> tuple[BitaxeFleetRuntime, MinerCoordinator]:
    """Build a live runtime/coordinator pair without an HTTP transport."""
    runtime = await BitaxeFleetRuntime.async_create(hass, "test-entry")
    initial = client._snapshots[0]
    miner = await runtime.registry.async_enroll(initial)
    entry = MockConfigEntry(domain=DOMAIN)
    coordinator = MinerCoordinator(
        hass,
        entry,
        miner,
        cast(
            Callable[[MinerEndpoint], AxeOSClientProtocol],
            lambda _: client,
        ),
        runtime.registry,
    )
    runtime.coordinators[miner.identity.miner_id] = coordinator
    return runtime, coordinator


async def test_runtime_captures_and_applies_only_a_complete_supported_profile(
    hass: HomeAssistant,
) -> None:
    """Capture stores six values; apply validates capabilities and read-back."""
    profile = _profile()
    client = _FakeClient([_snapshot(profile), _snapshot(profile), _snapshot(profile)])
    runtime, coordinator = await _runtime_with_client(hass, client)

    captured = await runtime.async_capture_profile(coordinator.miner.identity.miner_id)
    await runtime.async_apply_profile(coordinator.miner.identity.miner_id)

    assert captured == profile
    assert client.patched_profiles == [profile]
    assert coordinator.miner.recovery_profile == profile
    stored_miner = runtime.registry.get(coordinator.miner.identity.miner_id)
    assert stored_miner is not None
    assert stored_miner.recovery_profile == profile
    await runtime.async_close()


async def test_runtime_rejects_profile_read_back_drift(hass: HomeAssistant) -> None:
    """A successful PATCH cannot become a false success after read-back drift."""
    profile = _profile()
    drifted = RecoveryProfile(
        frequency_mhz=500.0,
        core_voltage_mv=1200,
        overclock_enabled=True,
        automatic_fan_speed=True,
        target_temperature_c=60,
        minimum_fan_speed_percent=25,
    )
    client = _FakeClient([_snapshot(profile), _snapshot(drifted)])
    runtime, coordinator = await _runtime_with_client(hass, client)
    await runtime.registry.async_set_recovery_profile(
        coordinator.miner.identity.miner_id, profile
    )

    with pytest.raises(FleetActionError, match="read-back did not match"):
        await runtime.async_apply_profile(coordinator.miner.identity.miner_id)

    assert client.patched_profiles == [profile]
    assert runtime.registry.incidents[0].outcome == "drift"
    await runtime.async_close()
