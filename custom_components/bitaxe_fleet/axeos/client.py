"""Bounded asynchronous HTTP client for documented AxeOS system endpoints."""

from __future__ import annotations

from json import JSONDecodeError, dumps, loads
from typing import Protocol

import aiohttp

from ..const import (
    AXEOS_CONNECT_TIMEOUT_SECONDS,
    AXEOS_READ_TIMEOUT_SECONDS,
    AXEOS_REQUEST_TIMEOUT_SECONDS,
    MAX_AXEOS_LOG_RESPONSE_BYTES,
    MAX_AXEOS_RESPONSE_BYTES,
    SYSTEM_INFO_PATH,
)
from .errors import (
    AxeOSAuthenticationError,
    AxeOSConnectionError,
    AxeOSError,
    AxeOSHTTPError,
    AxeOSInvalidResponseError,
    AxeOSMutationUncertainError,
    AxeOSTimeoutError,
    AxeOSUnsupportedError,
)
from .models import (
    AsicCapabilities,
    MinerEndpoint,
    MinerLogs,
    MinerSnapshot,
    RecoveryProfile,
)
from .parser import parse_system_asic, parse_system_info, parse_system_logs

_SYSTEM_ASIC_PATH = "/api/system/asic"
_SYSTEM_LOGS_PATH = "/api/system/logs"
_SYSTEM_PATH = "/api/system"
_SYSTEM_RESTART_PATH = "/api/system/restart"
_SYSTEM_PAUSE_PATH = "/api/system/pause"
_SYSTEM_RESUME_PATH = "/api/system/resume"
_SYSTEM_IDENTIFY_PATH = "/api/system/identify"
_JSON_CONTENT_TYPE = "application/json"
_TEXT_CONTENT_TYPE = "text/plain"
_MAX_MUTATION_REQUEST_BYTES = 1024


class AxeOSClientProtocol(Protocol):
    """Injectable typed client interface used by fleet managers."""

    async def async_get_system_info(self) -> MinerSnapshot:
        """Fetch one validated system-info snapshot."""

    async def async_get_system_asic(self) -> AsicCapabilities:
        """Fetch validated model-specific ASIC capabilities."""

    async def async_get_system_logs(self) -> MinerLogs:
        """Fetch bounded plain-text firmware logs."""

    async def async_patch_system(self, profile: RecoveryProfile) -> None:
        """Apply exactly one closed recovery-profile patch."""

    async def async_restart(self) -> None:
        """Request one software restart."""

    async def async_pause(self) -> None:
        """Request that mining pause."""

    async def async_resume(self) -> None:
        """Request that mining resume."""

    async def async_identify(self) -> None:
        """Request physical device identification."""


class AxeOSClient:
    """Typed client for one validated private miner endpoint."""

    def __init__(self, session: aiohttp.ClientSession, endpoint: MinerEndpoint) -> None:
        """Initialize the client with Home Assistant's shared HTTP session."""
        self._session = session
        self.endpoint = endpoint

    async def async_get_system_info(self) -> MinerSnapshot:
        """Fetch and parse the current AxeOS system information."""
        payload = await self._async_get_json(SYSTEM_INFO_PATH, "system info")
        return parse_system_info(payload, self.endpoint)

    async def async_get_system_asic(self) -> AsicCapabilities:
        """Fetch and parse current model-specific ASIC capabilities."""
        payload = await self._async_get_json(_SYSTEM_ASIC_PATH, "system ASIC")
        return parse_system_asic(payload)

    async def async_get_system_logs(self) -> MinerLogs:
        """Fetch bounded text logs without accepting a JSON response."""
        text = await self._async_get_text(
            _SYSTEM_LOGS_PATH,
            "system logs",
            max_response_bytes=MAX_AXEOS_LOG_RESPONSE_BYTES,
        )
        return parse_system_logs(text)

    async def async_patch_system(self, profile: RecoveryProfile) -> None:
        """Apply only the six approved recovery settings in one PATCH request."""
        await self._async_mutate(
            "PATCH",
            _SYSTEM_PATH,
            "system settings update",
            _serialize_recovery_profile(profile),
        )

    async def async_restart(self) -> None:
        """Request a software restart exactly once."""
        await self._async_mutate("POST", _SYSTEM_RESTART_PATH, "restart", None)

    async def async_pause(self) -> None:
        """Request that mining pauses exactly once."""
        await self._async_mutate("POST", _SYSTEM_PAUSE_PATH, "pause", None)

    async def async_resume(self) -> None:
        """Request that mining resumes exactly once."""
        await self._async_mutate("POST", _SYSTEM_RESUME_PATH, "resume", None)

    async def async_identify(self) -> None:
        """Request physical identification exactly once."""
        await self._async_mutate("POST", _SYSTEM_IDENTIFY_PATH, "identify", None)

    async def _async_get_json(self, path: str, operation: str) -> object:
        """Perform one bounded redirect-free JSON GET request."""
        body = await self._async_request_body(
            "GET",
            path,
            operation,
            _JSON_CONTENT_TYPE,
            body=None,
            is_mutation=False,
        )
        return _decode_json(body, operation)

    async def _async_get_text(
        self, path: str, operation: str, *, max_response_bytes: int
    ) -> str:
        """Perform one bounded redirect-free plain-text GET request."""
        body = await self._async_request_body(
            "GET",
            path,
            operation,
            _TEXT_CONTENT_TYPE,
            body=None,
            is_mutation=False,
            max_response_bytes=max_response_bytes,
        )
        try:
            return body.decode("utf-8")
        except UnicodeDecodeError:
            raise AxeOSInvalidResponseError(operation, "invalid text") from None

    async def _async_mutate(
        self, method: str, path: str, operation: str, body: bytes | None
    ) -> None:
        """Send one mutation without retrying an outcome that may have applied."""
        try:
            response_body = await self._async_request_body(
                method,
                path,
                operation,
                _JSON_CONTENT_TYPE,
                body=body,
                is_mutation=True,
                allow_empty_response=True,
            )
            if response_body:
                _decode_json(response_body, operation)
        except TimeoutError, aiohttp.ClientError, AxeOSInvalidResponseError:
            raise AxeOSMutationUncertainError(operation) from None

    async def _async_request_body(
        self,
        method: str,
        path: str,
        operation: str,
        expected_content_type: str,
        *,
        body: bytes | None,
        is_mutation: bool,
        allow_empty_response: bool = False,
        max_response_bytes: int = MAX_AXEOS_RESPONSE_BYTES,
    ) -> bytes:
        """Perform exactly one bounded request without following redirects."""
        headers = {"Accept": expected_content_type}
        if body is not None:
            headers["Content-Type"] = _JSON_CONTENT_TYPE

        try:
            async with self._session.request(
                method,
                f"{self.endpoint.base_url}{path}",
                allow_redirects=False,
                data=body,
                headers=headers,
                timeout=aiohttp.ClientTimeout(
                    total=AXEOS_REQUEST_TIMEOUT_SECONDS,
                    connect=AXEOS_CONNECT_TIMEOUT_SECONDS,
                    sock_read=AXEOS_READ_TIMEOUT_SECONDS,
                ),
            ) as response:
                if not 200 <= response.status < 300:
                    raise _http_error(operation, response.status)
                response_body = await _async_read_response_body(
                    response,
                    operation,
                    max_response_bytes=max_response_bytes,
                )
                if not response_body and allow_empty_response:
                    # AxeOS documents an empty 200 response for successful PATCH.
                    return response_body
                if not _has_content_type(response.content_type, expected_content_type):
                    raise AxeOSInvalidResponseError(
                        operation, f"expected {expected_content_type}"
                    )
                return response_body
        except TimeoutError:
            if is_mutation:
                raise AxeOSMutationUncertainError(operation) from None
            raise AxeOSTimeoutError(operation) from None
        except aiohttp.ClientError:
            if is_mutation:
                raise AxeOSMutationUncertainError(operation) from None
            raise AxeOSConnectionError(operation) from None


async def _async_read_response_body(
    response: aiohttp.ClientResponse, operation: str, *, max_response_bytes: int
) -> bytes:
    """Read a bounded body while draining the documented known-length response."""
    expected_length = getattr(response, "content_length", None)
    if expected_length is not None and expected_length > max_response_bytes:
        raise AxeOSInvalidResponseError(operation, "response is too large")
    chunks: list[bytes] = []
    received_length = 0
    remaining = max_response_bytes + 1
    while remaining:
        chunk = await response.content.read(remaining)
        if not chunk:
            break
        chunks.append(chunk)
        received_length += len(chunk)
        remaining -= len(chunk)
        if expected_length is None or received_length >= expected_length:
            break
    body = b"".join(chunks)
    if len(body) > max_response_bytes:
        raise AxeOSInvalidResponseError(operation, "response is too large")
    return body


def _decode_json(body: bytes, operation: str) -> object:
    """Decode a bounded JSON body without exposing it to callers."""
    try:
        return loads(body)
    except JSONDecodeError, RecursionError, UnicodeDecodeError:
        raise AxeOSInvalidResponseError(operation, "malformed JSON") from None


def _has_content_type(value: object, expected: str) -> bool:
    """Accept a media type with optional parameters, never a different type."""
    return isinstance(value, str) and value.split(";", 1)[0].strip().lower() == expected


def _http_error(operation: str, status: int) -> AxeOSError:
    """Map safe HTTP metadata to the most specific transport error type."""
    if status in {401, 403}:
        return AxeOSAuthenticationError(operation, status)
    if status in {404, 405, 501}:
        return AxeOSUnsupportedError(operation, status)
    return AxeOSHTTPError(operation, status)


def _serialize_recovery_profile(profile: RecoveryProfile) -> bytes:
    """Serialize the closed six-key profile allowlist for one PATCH request."""
    if not isinstance(profile, RecoveryProfile):
        raise TypeError("profile must be a RecoveryProfile")

    body = dumps(
        {
            "frequency": profile.frequency_mhz,
            "coreVoltage": profile.core_voltage_mv,
            "overclockEnabled": int(profile.overclock_enabled),
            "autofanspeed": int(profile.automatic_fan_speed),
            "temptarget": profile.target_temperature_c,
            "minFanSpeed": profile.minimum_fan_speed_percent,
        },
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")
    if len(body) > _MAX_MUTATION_REQUEST_BYTES:
        raise ValueError("recovery profile request is too large")
    return body
