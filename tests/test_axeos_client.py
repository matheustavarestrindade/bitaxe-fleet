"""Tests for bounded AxeOS HTTP reads, logs, capabilities, and mutations."""

from __future__ import annotations

import json
from ipaddress import IPv4Address
from typing import Protocol, cast
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.bitaxe_fleet.axeos.client import (
    AxeOSClient,
    _async_read_response_body,
)
from custom_components.bitaxe_fleet.axeos.errors import (
    AxeOSAuthenticationError,
    AxeOSConnectionError,
    AxeOSHTTPError,
    AxeOSInvalidResponseError,
    AxeOSMutationUncertainError,
    AxeOSTimeoutError,
)
from custom_components.bitaxe_fleet.axeos.models import MinerEndpoint, RecoveryProfile
from custom_components.bitaxe_fleet.const import (
    MAX_AXEOS_LOG_TEXT_BYTES,
    MAX_AXEOS_RESPONSE_BYTES,
)


class AiohttpClientMocker(Protocol):
    """The small portion of Home Assistant's HTTP mock used by these tests."""

    def get(self, url: str, **kwargs: object) -> None:
        """Register a mocked GET response."""

    def patch(self, url: str, **kwargs: object) -> None:
        """Register a mocked PATCH response."""

    def post(self, url: str, **kwargs: object) -> None:
        """Register a mocked POST response."""

    @property
    def call_count(self) -> int:
        """Return the number of requests observed by the mock."""


class _ChunkedContent:
    """Return a response body in deliberately incomplete stream reads."""

    def __init__(self, body: bytes, chunk_size: int) -> None:
        """Initialize an unread byte buffer and its fixed stream chunk size."""
        self._body = body
        self._chunk_size = chunk_size

    async def read(self, maximum: int) -> bytes:
        """Return no more than the configured chunk size for each call."""
        if not self._body:
            return b""
        size = min(maximum, self._chunk_size)
        chunk, self._body = self._body[:size], self._body[size:]
        return chunk


class _ChunkedResponse:
    """Supply the small response surface consumed by the bounded body reader."""

    def __init__(self, body: bytes) -> None:
        """Initialize a response which splits its body into tiny reads."""
        self.content_length = len(body)
        self.content = _ChunkedContent(body, chunk_size=3)


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


def _system_asic() -> dict[str, object]:
    """Return a valid model-specific AxeOS capability response."""
    return {
        "ASICModel": "BM1368",
        "asicCount": 1,
        "defaultFrequency": 525,
        "defaultVoltage": 1200,
        "frequencyOptions": [450, 500, 525],
        "voltageOptions": [1100, 1150, 1200],
    }


def _profile() -> RecoveryProfile:
    """Return one complete valid six-field recovery profile."""
    return RecoveryProfile(
        frequency_mhz=525.0,
        core_voltage_mv=1200,
        overclock_enabled=True,
        automatic_fan_speed=True,
        target_temperature_c=60,
        minimum_fan_speed_percent=25,
    )


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


async def test_client_drains_streamed_response_chunks_before_json_parsing() -> None:
    """A valid response split by TCP framing cannot become malformed JSON."""
    body = b'{"ASICModel":"BM1368","macAddr":"02:12:34:56:78:9a"}'

    received = await _async_read_response_body(
        cast(aiohttp.ClientResponse, _ChunkedResponse(body)),
        "system info",
        max_response_bytes=1024,
    )

    assert received == body


async def test_client_reads_typed_asic_capabilities(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The ASIC endpoint is parsed into capabilities instead of raw JSON."""
    endpoint = _endpoint()
    aioclient_mock.get(
        f"{endpoint.base_url}/api/system/asic",
        headers={"Content-Type": "application/json"},
        json=_system_asic(),
    )

    capabilities = await AxeOSClient(
        async_get_clientsession(hass), endpoint
    ).async_get_system_asic()

    assert capabilities.asic_model == "BM1368"
    assert capabilities.frequency_options_mhz == (450.0, 500.0, 525.0)
    assert capabilities.voltage_options_mv == (1100, 1150, 1200)


async def test_client_reads_bounded_plain_text_logs(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Logs require text/plain and return only an immutable text model."""
    endpoint = _endpoint()
    aioclient_mock.get(
        f"{endpoint.base_url}/api/system/logs",
        headers={"Content-Type": "text/plain; charset=utf-8"},
        text="I (120) boot complete\n",
    )

    logs = await AxeOSClient(
        async_get_clientsession(hass), endpoint
    ).async_get_system_logs()

    assert logs.text == "I (120) boot complete\n"


async def test_client_keeps_a_bounded_tail_of_large_valid_logs(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Large valid AxeOS logs remain usable without reaching the panel in full."""
    endpoint = _endpoint()
    aioclient_mock.get(
        f"{endpoint.base_url}/api/system/logs",
        headers={"Content-Type": "text/plain"},
        text=("old line\n" * 10_000) + "newest line\n",
    )

    logs = await AxeOSClient(
        async_get_clientsession(hass), endpoint
    ).async_get_system_logs()

    assert "newest line" in logs.text
    assert len(logs.text.encode("utf-8")) <= MAX_AXEOS_LOG_TEXT_BYTES


async def test_client_rejects_unexpected_content_types(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """JSON endpoints and text logs cannot silently accept each other's media type."""
    endpoint = _endpoint()
    aioclient_mock.get(
        f"{endpoint.base_url}/api/system/info",
        headers={"Content-Type": "text/plain"},
        text=json.dumps(_system_info()),
    )

    with pytest.raises(AxeOSInvalidResponseError):
        await AxeOSClient(
            async_get_clientsession(hass), endpoint
        ).async_get_system_info()

    aioclient_mock.get(
        f"{endpoint.base_url}/api/system/logs",
        headers={"Content-Type": "application/json"},
        json={"message": "not a text log"},
    )

    with pytest.raises(AxeOSInvalidResponseError):
        await AxeOSClient(
            async_get_clientsession(hass), endpoint
        ).async_get_system_logs()


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


async def test_client_maps_read_timeout_and_connection_failures(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Read transport failures remain distinguishable for coordinator availability."""
    endpoint = _endpoint()
    aioclient_mock.get(
        f"{endpoint.base_url}/api/system/info",
        exc=TimeoutError(),
    )

    with pytest.raises(AxeOSTimeoutError):
        await AxeOSClient(
            async_get_clientsession(hass), endpoint
        ).async_get_system_info()

    aioclient_mock.get(
        f"{endpoint.base_url}/api/system/asic",
        exc=aiohttp.ClientConnectionError(),
    )

    with pytest.raises(AxeOSConnectionError):
        await AxeOSClient(
            async_get_clientsession(hass), endpoint
        ).async_get_system_asic()


async def test_client_rejects_oversized_response_without_parsing_it(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """All JSON response bodies are capped before JSON decoding."""
    endpoint = _endpoint()
    aioclient_mock.get(
        f"{endpoint.base_url}/api/system/info",
        content=b"x" * (MAX_AXEOS_RESPONSE_BYTES + 1),
        headers={"Content-Type": "application/json"},
    )

    with pytest.raises(AxeOSInvalidResponseError):
        await AxeOSClient(
            async_get_clientsession(hass), endpoint
        ).async_get_system_info()


async def test_client_hides_error_payload_and_endpoint(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """HTTP errors expose safe status metadata but never response body or endpoint."""
    endpoint = _endpoint()
    secret = "response-payload-secret"
    aioclient_mock.get(
        f"{endpoint.base_url}/api/system/info",
        status=401,
        text=secret,
    )

    with pytest.raises(AxeOSAuthenticationError) as error:
        await AxeOSClient(
            async_get_clientsession(hass), endpoint
        ).async_get_system_info()

    assert secret not in str(error.value)
    assert str(endpoint.host) not in str(error.value)


async def test_client_patch_uses_only_the_closed_profile_allowlist(
    hass: HomeAssistant,
) -> None:
    """No raw mapping or manual fan speed can enter a system settings PATCH."""
    endpoint = _endpoint()
    client = AxeOSClient(async_get_clientsession(hass), endpoint)
    request_body = AsyncMock(return_value=b"{}")

    with patch.object(client, "_async_request_body", request_body):
        await client.async_patch_system(_profile())

    assert request_body.await_count == 1
    request_call = request_body.await_args
    assert request_call is not None
    body = request_call.kwargs["body"]
    assert isinstance(body, bytes)
    raw_patch: object = json.loads(body)
    assert isinstance(raw_patch, dict)
    assert raw_patch == {
        "frequency": 525.0,
        "coreVoltage": 1200,
        "overclockEnabled": 1,
        "autofanspeed": 1,
        "temptarget": 60,
        "minFanSpeed": 25,
    }
    assert "manualFanSpeed" not in raw_patch
    assert "hostname" not in raw_patch
    assert "stratumPassword" not in raw_patch


async def test_client_mutation_timeout_is_uncertain_and_not_retried(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A timed-out mutation is sent once and requires a read before any retry."""
    endpoint = _endpoint()
    aioclient_mock.post(
        f"{endpoint.base_url}/api/system/restart",
        exc=TimeoutError(),
    )

    with pytest.raises(AxeOSMutationUncertainError):
        await AxeOSClient(async_get_clientsession(hass), endpoint).async_restart()

    assert aioclient_mock.call_count == 1


async def test_client_mutation_connection_failure_is_uncertain(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A lost PATCH connection cannot be reported as a definite failure or success."""
    endpoint = _endpoint()
    aioclient_mock.patch(
        f"{endpoint.base_url}/api/system",
        exc=aiohttp.ClientConnectionError(),
    )

    with pytest.raises(AxeOSMutationUncertainError):
        await AxeOSClient(async_get_clientsession(hass), endpoint).async_patch_system(
            _profile()
        )


async def test_client_marks_malformed_mutation_success_as_uncertain(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """An unusable 2xx mutation response never becomes a false success."""
    endpoint = _endpoint()
    aioclient_mock.patch(
        f"{endpoint.base_url}/api/system",
        headers={"Content-Type": "application/json"},
        text="not-json",
    )

    with pytest.raises(AxeOSMutationUncertainError):
        await AxeOSClient(async_get_clientsession(hass), endpoint).async_patch_system(
            _profile()
        )


async def test_client_mutation_http_failure_is_definite(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A returned HTTP failure is distinguishable from an uncertain transport loss."""
    endpoint = _endpoint()
    aioclient_mock.patch(f"{endpoint.base_url}/api/system", status=400)

    with pytest.raises(AxeOSHTTPError) as error:
        await AxeOSClient(async_get_clientsession(hass), endpoint).async_patch_system(
            _profile()
        )

    assert error.value.status == 400


async def test_client_accepts_json_patch_success(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A documented JSON PATCH acknowledgement completes the single operation."""
    endpoint = _endpoint()
    aioclient_mock.patch(
        f"{endpoint.base_url}/api/system",
        headers={"Content-Type": "application/json"},
        json={"status": "success"},
    )

    await AxeOSClient(async_get_clientsession(hass), endpoint).async_patch_system(
        _profile()
    )


async def test_client_posts_each_closed_action_once(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Restart, pause, resume, and identify use their documented POST paths."""
    endpoint = _endpoint()
    aioclient_mock.post(
        f"{endpoint.base_url}/api/system/restart",
        headers={"Content-Type": "application/json"},
        json={"message": "restart requested"},
    )
    aioclient_mock.post(
        f"{endpoint.base_url}/api/system/pause",
        headers={"Content-Type": "application/json"},
        json={"message": "pause requested"},
    )
    aioclient_mock.post(
        f"{endpoint.base_url}/api/system/resume",
        headers={"Content-Type": "application/json"},
        json={"message": "resume requested"},
    )
    aioclient_mock.post(
        f"{endpoint.base_url}/api/system/identify",
        headers={"Content-Type": "application/json"},
        json={"message": "identify requested"},
    )
    client = AxeOSClient(async_get_clientsession(hass), endpoint)

    await client.async_restart()
    await client.async_pause()
    await client.async_resume()
    await client.async_identify()
