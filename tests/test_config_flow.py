"""Tests for the Bitaxe Fleet config flow."""

from __future__ import annotations

from homeassistant.config_entries import SOURCE_USER, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bitaxe_fleet.const import DOMAIN, INTEGRATION_NAME


def _flow_id(result: ConfigFlowResult) -> str:
    """Return a flow ID after verifying the result contains one."""
    flow_id = result.get("flow_id")
    assert isinstance(flow_id, str)
    return flow_id


async def test_user_flow_creates_fleet_entry(hass: HomeAssistant) -> None:
    """The initial flow creates the one fleet manager entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        _flow_id(result), user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == INTEGRATION_NAME
    assert result["data"] == {}

    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1


async def test_second_config_flow_aborts(hass: HomeAssistant) -> None:
    """The manifest enforces one fleet manager config entry."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
