"""Tests for administrator panel static registration."""

from __future__ import annotations

from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, patch

from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from custom_components.bitaxe_fleet.panel import async_register_panel


class _FakeHttp:
    """Capture static paths without starting Home Assistant's HTTP server."""

    def __init__(self) -> None:
        """Initialize the static-path calls captured by the test double."""
        self.static_paths: list[StaticPathConfig] = []

    async def async_register_static_paths(self, paths: list[StaticPathConfig]) -> None:
        """Retain registered static paths for route assertions."""
        self.static_paths.extend(paths)


class _FakeHass:
    """Supply only the Home Assistant surface needed by panel registration."""

    def __init__(self) -> None:
        """Initialize data storage and an HTTP path registrar."""
        self.data: dict[str, object] = {}
        self.http = _FakeHttp()


async def test_panel_registers_one_admin_only_static_module(tmp_path: Path) -> None:
    """The shipped panel is served once and exposed only to administrators."""
    bundle = tmp_path / "bitaxe-fleet-panel.js"
    bundle.write_text("export {};\n", encoding="utf-8")
    hass = _FakeHass()
    register_panel = AsyncMock()

    with (
        patch("custom_components.bitaxe_fleet.panel._bundle_path", return_value=bundle),
        patch(
            "custom_components.bitaxe_fleet.panel.panel_custom.async_register_panel",
            new=register_panel,
        ),
    ):
        await async_register_panel(cast(HomeAssistant, hass))
        await async_register_panel(cast(HomeAssistant, hass))

    assert len(hass.http.static_paths) == 1
    static_path = hass.http.static_paths[0]
    assert static_path.url_path == "/bitaxe_fleet_panel/bitaxe-fleet-panel.js"
    register_panel.assert_awaited_once()
    await_args = register_panel.await_args
    assert await_args is not None
    assert await_args.kwargs["require_admin"] is True
