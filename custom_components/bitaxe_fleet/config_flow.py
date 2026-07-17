"""Configuration flow for Bitaxe Fleet."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, override

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .axeos.errors import (
    AxeOSConnectionError,
    AxeOSError,
    AxeOSInvalidEndpointError,
    AxeOSTimeoutError,
)
from .const import CONF_ENROLLMENT_REVISION, CONF_HOST, DOMAIN, INTEGRATION_NAME
from .runtime import BitaxeFleetRuntime


class BitaxeFleetConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the singleton Bitaxe Fleet config flow."""

    VERSION = 1

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> BitaxeFleetOptionsFlow:
        """Create the flow used to manually enroll miners."""
        del config_entry
        return BitaxeFleetOptionsFlow()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Create the fleet manager entry."""
        # Home Assistant defines form input as Any; this empty flow does not inspect it.
        if user_input is not None:
            return self.async_create_entry(title=INTEGRATION_NAME, data={})

        # Administrators add private miner hosts through Configure after setup.
        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))


class BitaxeFleetOptionsFlow(config_entries.OptionsFlowWithReload):
    """Manually enroll private IPv4 AxeOS miners into the singleton fleet."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Validate the submitted host and persist explicit enrollment approval."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input.get(CONF_HOST)
            runtime = self.config_entry.runtime_data
            if not isinstance(runtime, BitaxeFleetRuntime):
                errors["base"] = "not_ready"
            elif not isinstance(host, str):
                errors[CONF_HOST] = "invalid_host"
            else:
                try:
                    await runtime.async_enroll_host(host)
                except AxeOSInvalidEndpointError:
                    errors[CONF_HOST] = "invalid_host"
                except AxeOSConnectionError, AxeOSTimeoutError:
                    errors["base"] = "cannot_connect"
                except AxeOSError:
                    errors["base"] = "not_bitaxe"
                else:
                    return self.async_create_entry(
                        data=_next_enrollment_options(self.config_entry.options)
                    )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )


def _next_enrollment_options(options: Mapping[str, Any]) -> dict[str, Any]:
    """Advance a harmless revision so OptionsFlowWithReload reloads the entry."""
    next_options = dict(options)
    revision = next_options.get(CONF_ENROLLMENT_REVISION, 0)
    if not isinstance(revision, int) or isinstance(revision, bool):
        revision = 0
    next_options[CONF_ENROLLMENT_REVISION] = revision + 1
    return next_options
