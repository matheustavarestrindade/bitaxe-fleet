"""Tests for administrator service registration and readiness failures."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from custom_components.bitaxe_fleet.const import DOMAIN
from custom_components.bitaxe_fleet.services import _runtime, async_register_services


def test_services_register_the_closed_administrator_surface(
    hass: HomeAssistant,
) -> None:
    """Only the documented explicit controls are registered under the domain."""
    async_register_services(hass)

    for service_name in (
        "restart_miner",
        "pause_miner",
        "resume_miner",
        "identify_miner",
        "capture_profile",
        "apply_profile",
        "scan_network",
    ):
        assert hass.services.has_service(DOMAIN, service_name)


def test_services_fail_safely_before_the_singleton_entry_is_ready(
    hass: HomeAssistant,
) -> None:
    """A service cannot infer or operate on an arbitrary unavailable runtime."""
    with pytest.raises(ServiceValidationError, match="not configured"):
        _runtime(hass)
