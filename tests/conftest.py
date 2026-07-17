"""Shared test fixtures for Bitaxe Fleet."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading the integration from the local custom_components directory."""
