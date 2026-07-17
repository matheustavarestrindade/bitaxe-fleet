"""Runtime data owned by a Bitaxe Fleet config entry."""

from __future__ import annotations

from dataclasses import dataclass, field

from homeassistant.config_entries import ConfigEntry


@dataclass(slots=True)
class BitaxeFleetRuntime:
    """Own resources that exist only while the fleet entry is loaded."""

    entry_id: str
    _closed: bool = field(default=False, init=False, repr=False)

    @property
    def is_closed(self) -> bool:
        """Return whether runtime resources have been released."""
        return self._closed

    async def async_close(self) -> None:
        """Release runtime resources exactly once."""
        if self._closed:
            return

        self._closed = True


type BitaxeFleetConfigEntry = ConfigEntry[BitaxeFleetRuntime]
