"""Administrator-only Home Assistant panel registration for Bitaxe Fleet."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_when_setup

_LOGGER = logging.getLogger(__name__)
_PANEL_URL_PATH = "bitaxe-fleet"
_PANEL_COMPONENT = "bitaxe-fleet-panel"
_STATIC_URL = "/bitaxe_fleet_panel/bitaxe-fleet-panel.js"
_STATIC_FILENAME = "bitaxe-fleet-panel.js"
_REGISTERED_KEY = "bitaxe_fleet_panel_registered"


async def async_register_panel(hass: HomeAssistant) -> None:
    """Serve and register the compiled panel once for administrator users only."""
    if hass.data.get(_REGISTERED_KEY):
        return
    bundle = _bundle_path()
    if not bundle.is_file():
        _LOGGER.warning("Bitaxe Fleet panel bundle is unavailable")
        return

    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                url_path=_STATIC_URL,
                path=str(bundle),
                cache_headers=False,
            )
        ]
    )
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=_PANEL_URL_PATH,
        webcomponent_name=_PANEL_COMPONENT,
        sidebar_title="Bitaxe Fleet",
        sidebar_icon="mdi:server-network",
        module_url=_STATIC_URL,
        require_admin=True,
    )
    async_when_setup(hass, frontend.DOMAIN, _async_register_dashboard_card)
    hass.data[_REGISTERED_KEY] = True


async def _async_register_dashboard_card(hass: HomeAssistant, _: str) -> None:
    """Load the shared panel module once the Home Assistant frontend is ready."""
    frontend.add_extra_js_url(hass, _STATIC_URL)


def _bundle_path() -> Path:
    """Prefer the HACS-packaged bundle and fall back to a local frontend build."""
    integration_directory = Path(__file__).parent
    packaged = integration_directory / "frontend" / _STATIC_FILENAME
    if packaged.is_file():
        return packaged
    return integration_directory.parents[1] / "frontend" / "dist" / _STATIC_FILENAME
