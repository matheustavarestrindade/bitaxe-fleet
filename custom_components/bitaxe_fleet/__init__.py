"""Set up the Bitaxe Fleet integration."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, INTEGRATION_NAME, PLATFORMS
from .runtime import BitaxeFleetConfigEntry, BitaxeFleetRuntime


async def async_setup_entry(hass: HomeAssistant, entry: BitaxeFleetConfigEntry) -> bool:
    """Set up a Bitaxe Fleet config entry."""
    entry.runtime_data = await BitaxeFleetRuntime.async_create(hass, entry.entry_id)
    _async_register_fleet_device(hass, entry)
    await entry.runtime_data.async_start_miners(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: BitaxeFleetConfigEntry
) -> bool:
    """Unload a Bitaxe Fleet config entry."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    await entry.runtime_data.async_close()
    return True


def _async_register_fleet_device(
    hass: HomeAssistant, entry: BitaxeFleetConfigEntry
) -> None:
    """Create the persistent hub device that owns enrolled miner devices."""
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer=INTEGRATION_NAME,
        model="Fleet manager",
        name=INTEGRATION_NAME,
    )
