"""Set up the Bitaxe Fleet integration."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .runtime import BitaxeFleetConfigEntry, BitaxeFleetRuntime


async def async_setup_entry(hass: HomeAssistant, entry: BitaxeFleetConfigEntry) -> bool:
    """Set up a Bitaxe Fleet config entry."""
    entry.runtime_data = BitaxeFleetRuntime(entry_id=entry.entry_id)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: BitaxeFleetConfigEntry
) -> bool:
    """Unload a Bitaxe Fleet config entry."""
    await entry.runtime_data.async_close()
    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: BitaxeFleetConfigEntry
) -> None:
    """Reload the singleton fleet manager after an entry update."""
    await hass.config_entries.async_reload(entry.entry_id)
