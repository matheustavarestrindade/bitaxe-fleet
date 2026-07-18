"""Bounded recursive redaction for diagnostics, incidents, and panel log output."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

_SENSITIVE_KEY_PARTS = (
    "address",
    "certificate",
    "credential",
    "hostname",
    "ip",
    "mac",
    "password",
    "pool",
    "secret",
    "ssid",
    "token",
    "url",
    "user",
    "wallet",
    "wifi",
)
_IPV4_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_MAC_PATTERN = re.compile(
    r"\b(?:(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}|[0-9A-Fa-f]{12})\b"
)
_URL_PATTERN = re.compile(r"\b[a-zA-Z][a-zA-Z0-9+.-]*://[^\s<>\"']+")
_SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"\b(?:api[_-]?key|host(?:name)?|pass(?:word)?|pool|secret|ssid|stratum|"
    r"token|user(?:name)?|wallet)\s*[:=]\s*(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)",
    re.IGNORECASE,
)
_BITCOIN_ADDRESS_PATTERN = re.compile(
    r"\b(?:bc1[ac-hj-np-z02-9]{11,87}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})\b",
    re.IGNORECASE,
)
_REDACTED = "**REDACTED**"


def redact_data(value: object) -> object:
    """Recursively redact sensitive keys and free-text network identifiers."""
    if isinstance(value, Mapping):
        redacted: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                continue
            if _is_sensitive_key(key):
                redacted[key] = _REDACTED
            else:
                redacted[key] = redact_data(item)
        return redacted
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        return [redact_data(item) for item in value]
    return value


def redact_text(value: str) -> str:
    """Remove common endpoint and credential forms from a bounded text value."""
    redacted = _URL_PATTERN.sub("**REDACTED_URL**", value)
    redacted = _SECRET_ASSIGNMENT_PATTERN.sub("**REDACTED_SECRET**", redacted)
    redacted = _MAC_PATTERN.sub("**REDACTED_MAC**", redacted)
    redacted = _BITCOIN_ADDRESS_PATTERN.sub("**REDACTED_WALLET**", redacted)
    return _IPV4_PATTERN.sub("**REDACTED_IP**", redacted)


def _is_sensitive_key(key: str) -> bool:
    """Recognize known and suspicious secret/network-bearing key names."""
    normalized = key.lower().replace("_", "")
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)
