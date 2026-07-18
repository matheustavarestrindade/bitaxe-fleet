"""Administrator-only Home Assistant services for explicit fleet actions."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import service

from .axeos.errors import AxeOSError
from .axeos.models import MinerId
from .axeos.parser import normalize_miner_id
from .const import DOMAIN
from .discovery.manager import DiscoveryError
from .runtime import BitaxeFleetRuntime, FleetActionError

_ATTR_MINER_ID = "miner_id"
_ATTR_NETWORK = "network"
_MINER_SCHEMA = vol.Schema({vol.Required(_ATTR_MINER_ID): str})
_SCAN_SCHEMA = vol.Schema({vol.Required(_ATTR_NETWORK): str})

type MinerOperation = Callable[[BitaxeFleetRuntime, str], Awaitable[None]]


@callback
def async_register_services(hass: HomeAssistant) -> None:
    """Register the fixed administrator-only service surface exactly once."""
    if hass.services.has_service(DOMAIN, "restart_miner"):
        return

    service.async_register_admin_service(
        hass, DOMAIN, "restart_miner", _async_restart, schema=_MINER_SCHEMA
    )
    service.async_register_admin_service(
        hass, DOMAIN, "pause_miner", _async_pause, schema=_MINER_SCHEMA
    )
    service.async_register_admin_service(
        hass, DOMAIN, "resume_miner", _async_resume, schema=_MINER_SCHEMA
    )
    service.async_register_admin_service(
        hass, DOMAIN, "identify_miner", _async_identify, schema=_MINER_SCHEMA
    )
    service.async_register_admin_service(
        hass, DOMAIN, "capture_profile", _async_capture_profile, schema=_MINER_SCHEMA
    )
    service.async_register_admin_service(
        hass, DOMAIN, "apply_profile", _async_apply_profile, schema=_MINER_SCHEMA
    )
    service.async_register_admin_service(
        hass, DOMAIN, "scan_network", _async_scan_network, schema=_SCAN_SCHEMA
    )


async def _async_restart(call: ServiceCall) -> None:
    """Run an explicit restart service call."""
    await _async_run_miner_action(call, "restart")


async def _async_pause(call: ServiceCall) -> None:
    """Run an explicit pause service call."""
    await _async_run_miner_action(call, "pause")


async def _async_resume(call: ServiceCall) -> None:
    """Run an explicit resume service call."""
    await _async_run_miner_action(call, "resume")


async def _async_identify(call: ServiceCall) -> None:
    """Run an explicit physical-identification service call."""
    await _async_run_miner_action(call, "identify")


async def _async_capture_profile(call: ServiceCall) -> None:
    """Capture one exact profile through the runtime safety boundary."""
    runtime = _runtime(call.hass)
    miner_id = _miner_id_from_call(call)
    try:
        await runtime.async_capture_profile(miner_id)
    except FleetActionError as err:
        raise ServiceValidationError(str(err)) from err


async def _async_apply_profile(call: ServiceCall) -> None:
    """Apply and verify one saved profile through the runtime safety boundary."""
    runtime = _runtime(call.hass)
    miner_id = _miner_id_from_call(call)
    try:
        await runtime.async_apply_profile(miner_id)
    except FleetActionError as err:
        raise ServiceValidationError(str(err)) from err


async def _async_scan_network(call: ServiceCall) -> None:
    """Start one bounded administrator-requested private-network scan."""
    runtime = _runtime(call.hass)
    network = call.data[_ATTR_NETWORK]
    if not isinstance(network, str):
        raise ServiceValidationError("network must be a private IPv4 CIDR")
    try:
        runtime.async_start_scan(network)
    except (AxeOSError, DiscoveryError, RuntimeError, ValueError) as err:
        raise ServiceValidationError("private-network scan could not start") from err


async def _async_run_miner_action(call: ServiceCall, action: str) -> None:
    """Route one explicit miner action through the typed runtime."""
    runtime = _runtime(call.hass)
    miner_id = _miner_id_from_call(call)
    try:
        await runtime.async_run_action(miner_id, action)
    except FleetActionError as err:
        raise ServiceValidationError(str(err)) from err


def _runtime(hass: HomeAssistant) -> BitaxeFleetRuntime:
    """Return the singleton loaded runtime without accepting arbitrary entry IDs."""
    entries = hass.config_entries.async_entries(DOMAIN)
    if len(entries) != 1:
        raise ServiceValidationError("Bitaxe Fleet is not configured")
    runtime = entries[0].runtime_data
    if not isinstance(runtime, BitaxeFleetRuntime):
        raise ServiceValidationError("Bitaxe Fleet is not ready")
    return runtime


def _miner_id_from_call(call: ServiceCall) -> MinerId:
    """Normalize one service MAC target before it reaches runtime code."""
    value = call.data[_ATTR_MINER_ID]
    try:
        return normalize_miner_id(value)
    except AxeOSError as err:
        raise ServiceValidationError("miner_id must be a valid MAC address") from err
