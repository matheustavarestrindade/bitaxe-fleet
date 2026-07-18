"""Shared test fixtures for Bitaxe Fleet."""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: None, socket_enabled: None
) -> None:
    """Enable loading the integration from the local custom_components directory."""
    del socket_enabled


@pytest.fixture(autouse=True)
def mock_global_runtime_resources() -> Iterator[None]:
    """Keep entry setup tests independent from HTTP assets and multicast sockets."""
    with (
        patch(
            "custom_components.bitaxe_fleet.async_register_panel",
            new=AsyncMock(),
        ),
        patch(
            "custom_components.bitaxe_fleet.discovery.manager.DiscoveryManager.async_start",
            new=AsyncMock(),
        ),
    ):
        yield
