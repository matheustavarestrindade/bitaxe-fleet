"""Tests for the Bitaxe Fleet config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import SOURCE_USER, ConfigEntryState, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bitaxe_fleet.const import DOMAIN, INTEGRATION_NAME
from custom_components.bitaxe_fleet.runtime import BitaxeFleetRuntime


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


async def test_options_flow_enrolls_a_submitted_miner(hass: HomeAssistant) -> None:
    """Configure explicitly validates one submitted private miner host."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with patch.object(
        BitaxeFleetRuntime,
        "async_enroll_host",
        new=AsyncMock(),
    ) as enroll_host:
        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.options.async_configure(
            _flow_id(result), user_input={"host": "192.168.10.25"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    enroll_host.assert_awaited_once_with("192.168.10.25")
    await hass.async_block_till_done()
    assert entry.options["enrollment_revision"] == 1
    assert entry.state is ConfigEntryState.LOADED


async def test_options_flow_rejects_non_private_host(hass: HomeAssistant) -> None:
    """Configure never sends a request to a public or arbitrary hostname."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        _flow_id(result), user_input={"host": "8.8.8.8"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"host": "invalid_host"}
