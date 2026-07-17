"""Bounded asynchronous HTTP client for the AxeOS system-info endpoint."""

from __future__ import annotations

from json import JSONDecodeError, loads
from typing import Protocol

import aiohttp

from ..const import (
    AXEOS_CONNECT_TIMEOUT_SECONDS,
    AXEOS_READ_TIMEOUT_SECONDS,
    AXEOS_REQUEST_TIMEOUT_SECONDS,
    MAX_AXEOS_RESPONSE_BYTES,
    SYSTEM_INFO_PATH,
)
from .errors import (
    AxeOSConnectionError,
    AxeOSHTTPError,
    AxeOSInvalidResponseError,
    AxeOSTimeoutError,
)
from .models import MinerEndpoint, MinerSnapshot
from .parser import parse_system_info


class AxeOSClientProtocol(Protocol):
    """Injectable read-only client interface used by coordinators."""

    async def async_get_system_info(self) -> MinerSnapshot:
        """Fetch one validated system-info snapshot."""


class AxeOSClient:
    """Read-only client for one validated private miner endpoint."""

    def __init__(self, session: aiohttp.ClientSession, endpoint: MinerEndpoint) -> None:
        """Initialize the client with Home Assistant's shared HTTP session."""
        self._session = session
        self.endpoint = endpoint

    async def async_get_system_info(self) -> MinerSnapshot:
        """Fetch and parse the current AxeOS system information."""
        payload = await self._async_get_json(SYSTEM_INFO_PATH, "system info")
        return parse_system_info(payload, self.endpoint)

    async def _async_get_json(self, path: str, operation: str) -> object:
        """Perform one bounded GET request without following redirects."""
        try:
            async with self._session.get(
                f"{self.endpoint.base_url}{path}",
                allow_redirects=False,
                headers={"Accept": "application/json"},
                timeout=aiohttp.ClientTimeout(
                    total=AXEOS_REQUEST_TIMEOUT_SECONDS,
                    connect=AXEOS_CONNECT_TIMEOUT_SECONDS,
                    sock_read=AXEOS_READ_TIMEOUT_SECONDS,
                ),
            ) as response:
                if not 200 <= response.status < 300:
                    raise AxeOSHTTPError(operation, response.status)
                if response.content_type != "application/json":
                    raise AxeOSInvalidResponseError(operation, "expected JSON")
                body = await response.content.read(MAX_AXEOS_RESPONSE_BYTES + 1)
        except TimeoutError as err:
            raise AxeOSTimeoutError(operation) from err
        except aiohttp.ClientConnectionError as err:
            raise AxeOSConnectionError(operation) from err
        except aiohttp.ClientError as err:
            raise AxeOSConnectionError(operation) from err

        if len(body) > MAX_AXEOS_RESPONSE_BYTES:
            raise AxeOSInvalidResponseError(operation, "response is too large")

        try:
            parsed: object = loads(body)
        except (JSONDecodeError, UnicodeDecodeError) as err:
            raise AxeOSInvalidResponseError(operation, "malformed JSON") from err
        return parsed
