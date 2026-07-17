"""Tests for Bitaxe Fleet config entry lifecycle management."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bitaxe_fleet.const import DOMAIN
from custom_components.bitaxe_fleet.runtime import BitaxeFleetRuntime


def _assert_runtime_open(runtime: BitaxeFleetRuntime) -> None:
    """Assert that a runtime still owns its resources."""
    assert not runtime.is_closed


def _assert_runtime_closed(runtime: BitaxeFleetRuntime) -> None:
    """Assert that a runtime has released its resources."""
    assert runtime.is_closed


async def test_setup_reload_and_unload_release_runtime(hass: HomeAssistant) -> None:
    """Setup, reload, and unload do not leave fleet runtime resources alive."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    first_runtime = entry.runtime_data
    assert isinstance(first_runtime, BitaxeFleetRuntime)
    _assert_runtime_open(first_runtime)

    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    _assert_runtime_closed(first_runtime)
    second_runtime = entry.runtime_data
    assert isinstance(second_runtime, BitaxeFleetRuntime)
    _assert_runtime_open(second_runtime)

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    _assert_runtime_closed(second_runtime)
