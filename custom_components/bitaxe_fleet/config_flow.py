"""Configuration flow for Bitaxe Fleet."""

from __future__ import annotations

from typing import Any, override

import voluptuous as vol
from homeassistant import config_entries

from .const import DOMAIN, INTEGRATION_NAME


class BitaxeFleetConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the singleton Bitaxe Fleet config flow."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Create the fleet manager entry."""
        # Home Assistant defines form input as Any; this empty flow does not inspect it.
        if user_input is not None:
            return self.async_create_entry(title=INTEGRATION_NAME, data={})

        # Miner discovery runs after this one fleet manager is set up.
        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))
