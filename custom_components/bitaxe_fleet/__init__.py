"""Set up the Bitaxe Fleet integration."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .axeos.errors import AxeOSError
from .axeos.parser import normalize_miner_id
from .const import DOMAIN, INTEGRATION_NAME, PLATFORMS
from .panel import async_register_panel
from .runtime import BitaxeFleetConfigEntry, BitaxeFleetRuntime
from .services import async_register_services
from .websocket import async_register_websocket_commands


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register global administrator APIs and the fleet panel once."""
    del config
    async_register_services(hass)
    async_register_websocket_commands(hass)
    await async_register_panel(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: BitaxeFleetConfigEntry) -> bool:
    """Set up a Bitaxe Fleet config entry."""
    entry.runtime_data = await BitaxeFleetRuntime.async_create(hass, entry.entry_id)
    _async_register_fleet_device(hass, entry)
    await entry.runtime_data.async_start(entry)
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


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    entry: BitaxeFleetConfigEntry,
    device_entry: dr.DeviceEntry,
) -> bool:
    """Allow removing an enrolled miner but never the singleton fleet hub device."""
    if (DOMAIN, entry.entry_id) in device_entry.identifiers:
        return False
    miner_id: str | None = None
    for domain, identifier in device_entry.identifiers:
        if domain == DOMAIN:
            miner_id = identifier
            break
    if miner_id is None:
        return False
    try:
        normalized = normalize_miner_id(miner_id)
    except AxeOSError:
        return False
    if not await entry.runtime_data.async_remove_miner(normalized):
        return False
    await hass.config_entries.async_reload(entry.entry_id)
    return True
