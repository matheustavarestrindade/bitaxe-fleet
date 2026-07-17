"""Documented untrusted AxeOS JSON shapes."""

from __future__ import annotations

from typing import NotRequired, TypedDict


class SystemInfoWire(TypedDict):
    """Known fields returned by ``GET /api/system/info``.

    The parser still validates every value because network JSON is untrusted.
    """

    macAddr: str
    ASICModel: NotRequired[str]
    axeOSVersion: NotRequired[str]
    boardVersion: NotRequired[str]
    hashRate: NotRequired[float | int | str]
    hostname: NotRequired[str]
    power: NotRequired[float | int | str]
    temp: NotRequired[float | int | str]
    version: NotRequired[str]
