"""Redacted diagnostics for Bitaxe Fleet support investigations."""

from __future__ import annotations

from typing import cast

from homeassistant.core import HomeAssistant

from .const import STORAGE_SCHEMA_VERSION
from .redaction import redact_data
from .runtime import BitaxeFleetConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: BitaxeFleetConfigEntry
) -> dict[str, object]:
    """Return useful runtime evidence without household identifiers or raw payloads."""
    del hass
    runtime = entry.runtime_data
    miners: list[dict[str, object]] = []
    for miner in runtime.registry.miners:
        coordinator = runtime.get_coordinator(miner.identity.miner_id)
        snapshot = coordinator.snapshot if coordinator is not None else None
        miners.append(
            {
                "capabilities_loaded": (
                    coordinator is not None and coordinator.capabilities is not None
                ),
                "enabled": miner.enabled,
                "firmware_version": miner.identity.firmware_version,
                "has_profile": miner.recovery_profile is not None,
                "last_update_success": (
                    coordinator.last_update_success
                    if coordinator is not None
                    else False
                ),
                "model": miner.identity.asic_model,
                "snapshot_fields": (
                    {
                        "hashrate": snapshot.telemetry.hashrate_gh_s is not None,
                        "power": snapshot.telemetry.power_w is not None,
                        "temperature": snapshot.telemetry.temperature_c is not None,
                    }
                    if snapshot is not None
                    else {}
                ),
            }
        )
    diagnostics: dict[str, object] = {
        "candidate_count": len(runtime.candidates),
        "incident_count": len(runtime.registry.incidents),
        "miners": miners,
        "scan_running": runtime.scan_status.running,
        "storage_schema_version": STORAGE_SCHEMA_VERSION,
    }
    return cast(dict[str, object], redact_data(diagnostics))
