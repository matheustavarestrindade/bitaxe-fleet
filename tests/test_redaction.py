"""Tests for diagnostics, logs, and incident free-text redaction."""

from __future__ import annotations

from custom_components.bitaxe_fleet.redaction import redact_data, redact_text


def test_redact_text_removes_network_identifiers_and_credentials() -> None:
    """Free text cannot reveal local endpoints, credentials, MACs, or wallet data."""
    raw = (
        "pool=stratum+tcp://alice:secret@192.168.10.25:3333 "
        "password=hunter2 ssid=Workshop wifi_mac=02-12-34-56-78-9a "
        "mac=02123456789a wallet=bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh"
    )

    redacted = redact_text(raw)

    for secret in (
        "192.168.10.25",
        "alice",
        "hunter2",
        "Workshop",
        "02-12-34-56-78-9a",
        "02123456789a",
        "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh",
    ):
        assert secret not in redacted


def test_redact_data_recurses_through_sensitive_keys_and_text() -> None:
    """Structured diagnostics redact key-based data as well as nested text values."""
    redacted = redact_data(
        {
            "hostname": "bitaxe-lab",
            "nested": ["http://192.168.10.25/logs", {"note": "token=abc"}],
        }
    )

    assert redacted == {
        "hostname": "**REDACTED**",
        "nested": ["**REDACTED_URL**", {"note": "**REDACTED_SECRET**"}],
    }
