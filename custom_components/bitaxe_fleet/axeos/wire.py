"""Documented untrusted AxeOS JSON shapes."""

from __future__ import annotations

from typing import NotRequired, TypedDict


class ShareRejectionReasonWire(TypedDict):
    """One documented rejected-share reason in system-info."""

    count: int
    message: str


class SystemInfoWire(TypedDict):
    """Known fields returned by ``GET /api/system/info``.

    The parser still validates every value because network JSON is untrusted.
    """

    macAddr: str
    ASICModel: NotRequired[str]
    actualFrequency: NotRequired[float | int | str]
    apEnabled: NotRequired[bool | float | int | str]
    autofanspeed: NotRequired[bool | float | int | str]
    bestDiff: NotRequired[float | int | str]
    bestSessionDiff: NotRequired[float | int | str]
    blockFound: NotRequired[float | int | str]
    blockHeight: NotRequired[float | int | str]
    axeOSVersion: NotRequired[str]
    boardVersion: NotRequired[str]
    coreVoltage: NotRequired[float | int | str]
    coreVoltageActual: NotRequired[float | int | str]
    current: NotRequired[float | int | str]
    errorPercentage: NotRequired[float | int | str]
    expectedHashrate: NotRequired[float | int | str]
    fan2rpm: NotRequired[float | int | str]
    fanrpm: NotRequired[float | int | str]
    fanspeed: NotRequired[float | int | str]
    frequency: NotRequired[float | int | str]
    hashRate: NotRequired[float | int | str]
    hashRate_10m: NotRequired[float | int | str]
    hashRate_1h: NotRequired[float | int | str]
    hashRate_1m: NotRequired[float | int | str]
    hardware_fault: NotRequired[str]
    hostname: NotRequired[str]
    isUsingFallbackStratum: NotRequired[bool | float | int | str]
    manualFanSpeed: NotRequired[float | int | str]
    minFanSpeed: NotRequired[float | int | str]
    miningPaused: NotRequired[bool | float | int | str]
    networkDifficulty: NotRequired[float | int | str]
    overclockEnabled: NotRequired[bool | float | int | str]
    overheat_mode: NotRequired[float | int | str]
    power: NotRequired[float | int | str]
    power_fault: NotRequired[str]
    poolDifficulty: NotRequired[float | int | str]
    resetReason: NotRequired[str]
    responseTime: NotRequired[float | int | str]
    sharesAccepted: NotRequired[float | int | str]
    sharesRejected: NotRequired[float | int | str]
    sharesRejectedReasons: NotRequired[list[ShareRejectionReasonWire]]
    temp: NotRequired[float | int | str]
    temp2: NotRequired[float | int | str]
    temptarget: NotRequired[float | int | str]
    uptimeSeconds: NotRequired[float | int | str]
    version: NotRequired[str]
    voltage: NotRequired[float | int | str]
    vrTemp: NotRequired[float | int | str]
    wifiRSSI: NotRequired[float | int | str]
    wifiStatus: NotRequired[str]


class SystemAsicWire(TypedDict):
    """Known fields returned by ``GET /api/system/asic``."""

    ASICModel: str
    asicCount: NotRequired[float | int | str]
    defaultFrequency: NotRequired[float | int | str]
    defaultVoltage: NotRequired[float | int | str]
    deviceModel: NotRequired[str]
    frequencyOptions: NotRequired[list[float | int | str]]
    swarmColor: NotRequired[str]
    voltageOptions: NotRequired[list[float | int | str]]
