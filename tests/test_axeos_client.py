"""Tests for bounded read-only AxeOS HTTP requests."""

from __future__ import annotations

from ipaddress import IPv4Address
from typing import Protocol

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.bitaxe_fleet.axeos.client import AxeOSClient
from custom_components.bitaxe_fleet.axeos.errors import AxeOSHTTPError
from custom_components.bitaxe_fleet.axeos.models import MinerEndpoint


class AiohttpClientMocker(Protocol):
    """The small portion of Home Assistant's HTTP mock used by these tests."""

    def get(self, url: str, **kwargs: object) -> None:
        """Register a mocked GET response."""


def _endpoint() -> MinerEndpoint:
    """Return the synthetic private endpoint used by client tests."""
    return MinerEndpoint(host=IPv4Address("192.168.10.25"))


def _system_info() -> dict[str, object]:
    """Return a minimal valid AxeOS system-info response."""
    return {
        "ASICModel": "BM1368",
        "hashRate": 654.32,
        "macAddr": "02:12:34:56:78:9a",
        "power": 17.4,
        "temp": 54.25,
        "version": "v2.14.2",
    }


async def test_client_reads_valid_system_info(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The client accepts bounded JSON and returns validated domain data."""
    endpoint = _endpoint()
    aioclient_mock.get(
        f"{endpoint.base_url}/api/system/info",
        headers={"Content-Type": "application/json"},
        json=_system_info(),
    )

    snapshot = await AxeOSClient(
        async_get_clientsession(hass), endpoint
    ).async_get_system_info()

    assert str(snapshot.identity.miner_id) == "02:12:34:56:78:9a"
    assert snapshot.telemetry.hashrate_gh_s == 654.32


async def test_client_rejects_redirects_without_following_them(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A redirect is a rejected response, never a second arbitrary request."""
    endpoint = _endpoint()
    aioclient_mock.get(
        f"{endpoint.base_url}/api/system/info",
        headers={"Location": "http://8.8.8.8/"},
        status=302,
    )

    with pytest.raises(AxeOSHTTPError) as error:
        await AxeOSClient(
            async_get_clientsession(hass), endpoint
        ).async_get_system_info()

    assert error.value.status == 302
