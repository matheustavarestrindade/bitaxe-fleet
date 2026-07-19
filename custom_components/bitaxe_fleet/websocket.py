"""Administrator-only WebSocket DTO boundary for the Bitaxe Fleet panel."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.components.websocket_api import async_register_command
from homeassistant.components.websocket_api.connection import ActiveConnection
from homeassistant.components.websocket_api.decorators import (
    async_response,
    require_admin,
    websocket_command,
)
from homeassistant.core import HomeAssistant

from .aggregates import FleetAggregates
from .axeos.errors import AxeOSError
from .axeos.models import EnrolledMiner, MinerId, RecoveryPolicy
from .axeos.parser import normalize_miner_id
from .const import DOMAIN
from .discovery.manager import DiscoveryError
from .history import (
    FleetTelemetryHistory,
    MinerTelemetryHistory,
    async_get_fleet_telemetry_history,
    async_get_miner_telemetry_history,
)
from .redaction import redact_text
from .runtime import BitaxeFleetRuntime, FleetActionError

_TYPE_FLEET_LIST = "bitaxe_fleet/fleet/list"
_TYPE_CANDIDATES_LIST = "bitaxe_fleet/discovery/list"
_TYPE_SCAN = "bitaxe_fleet/discovery/scan"
_TYPE_APPROVE = "bitaxe_fleet/discovery/approve"
_TYPE_REJECT = "bitaxe_fleet/discovery/reject"
_TYPE_ACTION = "bitaxe_fleet/miner/action"
_TYPE_PROFILE_CAPTURE = "bitaxe_fleet/profile/capture"
_TYPE_PROFILE_APPLY = "bitaxe_fleet/profile/apply"
_TYPE_POLICY_UPDATE = "bitaxe_fleet/policy/update"
_TYPE_LOGS_GET = "bitaxe_fleet/logs/get"
_TYPE_INCIDENTS_LIST = "bitaxe_fleet/incidents/list"
_TYPE_FLEET_HISTORY = "bitaxe_fleet/fleet/history"
_TYPE_MINER_HISTORY = "bitaxe_fleet/miner/history"


def async_register_websocket_commands(hass: HomeAssistant) -> None:
    """Register the fixed admin-only panel API exactly once per HA instance."""
    async_register_command(hass, websocket_fleet_list)
    async_register_command(hass, websocket_discovery_list)
    async_register_command(hass, websocket_discovery_scan)
    async_register_command(hass, websocket_discovery_approve)
    async_register_command(hass, websocket_discovery_reject)
    async_register_command(hass, websocket_miner_action)
    async_register_command(hass, websocket_profile_capture)
    async_register_command(hass, websocket_profile_apply)
    async_register_command(hass, websocket_policy_update)
    async_register_command(hass, websocket_logs_get)
    async_register_command(hass, websocket_incidents_list)
    async_register_command(hass, websocket_fleet_history)
    async_register_command(hass, websocket_miner_history)


@websocket_command({vol.Required("type"): _TYPE_FLEET_LIST})
@require_admin
@async_response
async def websocket_fleet_list(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return a versioned fleet DTO with validated, no-raw-payload data."""
    runtime = _runtime_or_error(hass, connection, msg)
    if runtime is None:
        return
    connection.send_result(
        msg["id"],
        {
            "aggregates": _fleet_aggregates_dto(runtime.fleet_aggregates),
            "schema_version": 1,
            "miners": [_miner_dto(runtime, miner) for miner in runtime.registry.miners],
            "scan": _scan_dto(runtime),
        },
    )


@websocket_command({vol.Required("type"): _TYPE_CANDIDATES_LIST})
@require_admin
@async_response
async def websocket_discovery_list(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return pending approval candidates and active-scan state."""
    runtime = _runtime_or_error(hass, connection, msg)
    if runtime is None:
        return
    connection.send_result(
        msg["id"],
        {
            "candidates": [
                _candidate_dto(candidate) for candidate in runtime.candidates
            ],
            "scan": _scan_dto(runtime),
        },
    )


@websocket_command({vol.Required("type"): _TYPE_SCAN, vol.Required("network"): str})
@require_admin
@async_response
async def websocket_discovery_scan(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Start a bounded explicit private-network scan without blocking the panel."""
    runtime = _runtime_or_error(hass, connection, msg)
    if runtime is None:
        return
    network = msg["network"]
    if not isinstance(network, str):
        connection.send_error(msg["id"], "invalid_network", "Network must be text")
        return
    try:
        runtime.async_start_scan(network)
    except AxeOSError, DiscoveryError, RuntimeError, ValueError:
        connection.send_error(
            msg["id"], "invalid_network", "Private-network scan could not start"
        )
        return
    connection.send_result(msg["id"], {"scan": _scan_dto(runtime)})


@websocket_command({vol.Required("type"): _TYPE_APPROVE, vol.Required("miner_id"): str})
@require_admin
@async_response
async def websocket_discovery_approve(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Revalidate and approve one candidate through the MAC-safe runtime boundary."""
    runtime = _runtime_or_error(hass, connection, msg)
    if runtime is None:
        return
    miner_id = _miner_id(msg, connection)
    if miner_id is None:
        return
    try:
        miner = await runtime.async_approve_candidate(miner_id)
    except DiscoveryError:
        connection.send_error(
            msg["id"], "candidate_unavailable", "Candidate could not be approved"
        )
        return
    connection.send_result(msg["id"], {"miner": _miner_dto(runtime, miner)})


@websocket_command({vol.Required("type"): _TYPE_REJECT, vol.Required("miner_id"): str})
@require_admin
@async_response
async def websocket_discovery_reject(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Persist an explicit rejection without exposing candidate data in errors."""
    runtime = _runtime_or_error(hass, connection, msg)
    if runtime is None:
        return
    miner_id = _miner_id(msg, connection)
    if miner_id is None:
        return
    try:
        await runtime.async_reject_candidate(miner_id)
    except DiscoveryError:
        connection.send_error(
            msg["id"], "candidate_unavailable", "Candidate is unavailable"
        )
        return
    connection.send_result(msg["id"], {})


@websocket_command(
    {
        vol.Required("type"): _TYPE_ACTION,
        vol.Required("miner_id"): str,
        vol.Required("action"): vol.In({"restart", "pause", "resume", "identify"}),
    }
)
@require_admin
@async_response
async def websocket_miner_action(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Run one explicit action after the panel's own confirmation step."""
    runtime = _runtime_or_error(hass, connection, msg)
    if runtime is None:
        return
    miner_id = _miner_id(msg, connection)
    if miner_id is None:
        return
    action = msg["action"]
    if not isinstance(action, str):
        connection.send_error(msg["id"], "invalid_action", "Action is invalid")
        return
    try:
        await runtime.async_run_action(miner_id, action)
    except FleetActionError as err:
        connection.send_error(msg["id"], "action_failed", str(err))
        return
    connection.send_result(msg["id"], {})


@websocket_command(
    {vol.Required("type"): _TYPE_PROFILE_CAPTURE, vol.Required("miner_id"): str}
)
@require_admin
@async_response
async def websocket_profile_capture(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Capture the exact six-field profile and return a safe DTO."""
    runtime = _runtime_or_error(hass, connection, msg)
    if runtime is None:
        return
    miner_id = _miner_id(msg, connection)
    if miner_id is None:
        return
    try:
        profile = await runtime.async_capture_profile(miner_id)
    except FleetActionError as err:
        connection.send_error(msg["id"], "profile_capture_failed", str(err))
        return
    connection.send_result(msg["id"], {"profile": _profile_dto(profile)})


@websocket_command(
    {vol.Required("type"): _TYPE_PROFILE_APPLY, vol.Required("miner_id"): str}
)
@require_admin
@async_response
async def websocket_profile_apply(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Apply and read-back verify an already saved profile."""
    runtime = _runtime_or_error(hass, connection, msg)
    if runtime is None:
        return
    miner_id = _miner_id(msg, connection)
    if miner_id is None:
        return
    try:
        await runtime.async_apply_profile(miner_id)
    except FleetActionError as err:
        connection.send_error(msg["id"], "profile_apply_failed", str(err))
        return
    connection.send_result(msg["id"], {})


@websocket_command(
    {
        vol.Required("type"): _TYPE_POLICY_UPDATE,
        vol.Required("miner_id"): str,
        vol.Required("policy"): dict,
    }
)
@require_admin
@async_response
async def websocket_policy_update(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Replace a policy only after strict server-side shape validation."""
    runtime = _runtime_or_error(hass, connection, msg)
    if runtime is None:
        return
    miner_id = _miner_id(msg, connection)
    if miner_id is None:
        return
    try:
        policy = _policy_from_message(msg["policy"])
        miner = await runtime.async_set_recovery_policy(miner_id, policy)
    except FleetActionError, ValueError:
        connection.send_error(msg["id"], "invalid_policy", "Recovery policy is invalid")
        return
    connection.send_result(msg["id"], {"policy": _policy_dto(miner.recovery_policy)})


@websocket_command(
    {vol.Required("type"): _TYPE_LOGS_GET, vol.Required("miner_id"): str}
)
@require_admin
@async_response
async def websocket_logs_get(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return bounded redacted firmware log text to an administrator panel."""
    runtime = _runtime_or_error(hass, connection, msg)
    if runtime is None:
        return
    miner_id = _miner_id(msg, connection)
    if miner_id is None:
        return
    try:
        logs = await runtime.async_get_logs(miner_id)
    except FleetActionError as err:
        connection.send_error(msg["id"], "logs_failed", str(err))
        return
    connection.send_result(msg["id"], {"text": redact_text(logs)})


@websocket_command({vol.Required("type"): _TYPE_INCIDENTS_LIST})
@require_admin
@async_response
async def websocket_incidents_list(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return bounded redacted incident summaries."""
    runtime = _runtime_or_error(hass, connection, msg)
    if runtime is None:
        return
    connection.send_result(
        msg["id"],
        {
            "incidents": [
                {
                    "cause": incident.cause,
                    "detail": redact_text(incident.detail),
                    "id": incident.incident_id,
                    "miner_id": str(incident.miner_id),
                    "occurred_at": incident.occurred_at.isoformat(),
                    "outcome": incident.outcome,
                }
                for incident in runtime.registry.incidents
            ]
        },
    )


@websocket_command(
    {vol.Required("type"): _TYPE_MINER_HISTORY, vol.Required("miner_id"): str}
)
@require_admin
@async_response
async def websocket_miner_history(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return a bounded Recorder-backed graph series for one approved miner."""
    runtime = _runtime_or_error(hass, connection, msg)
    if runtime is None:
        return
    miner_id = _miner_id(msg, connection)
    if miner_id is None:
        return
    if runtime.registry.get(miner_id) is None:
        connection.send_error(msg["id"], "unknown_miner", "Miner is not enrolled")
        return
    history = await async_get_miner_telemetry_history(hass, miner_id)
    connection.send_result(msg["id"], _history_dto(miner_id, history))


@websocket_command(
    {
        vol.Required("type"): _TYPE_FLEET_HISTORY,
        vol.Required("metric"): vol.In({"hashrate", "power", "efficiency"}),
    }
)
@require_admin
@async_response
async def websocket_fleet_history(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return one bounded Recorder-backed fleet aggregate graph series."""
    runtime = _runtime_or_error(hass, connection, msg)
    if runtime is None:
        return
    metric = msg["metric"]
    if not isinstance(metric, str):
        connection.send_error(msg["id"], "invalid_metric", "Metric is invalid")
        return
    try:
        history = await async_get_fleet_telemetry_history(
            hass, runtime.entry_id, metric
        )
    except ValueError:
        connection.send_error(msg["id"], "invalid_metric", "Metric is invalid")
        return
    connection.send_result(msg["id"], _fleet_history_dto(history))


def _runtime(hass: HomeAssistant) -> BitaxeFleetRuntime:
    """Find the singleton typed runtime without accepting caller-provided entries."""
    entries = hass.config_entries.async_entries(DOMAIN)
    if len(entries) != 1:
        raise RuntimeError("Bitaxe Fleet is not configured")
    runtime = entries[0].runtime_data
    if not isinstance(runtime, BitaxeFleetRuntime):
        raise RuntimeError("Bitaxe Fleet is not ready")
    return runtime


def _runtime_or_error(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> BitaxeFleetRuntime | None:
    """Return a loaded runtime or send a stable safe error before command work."""
    try:
        return _runtime(hass)
    except RuntimeError:
        connection.send_error(msg["id"], "not_ready", "Bitaxe Fleet is not ready")
        return None


def _miner_id(msg: Mapping[str, Any], connection: ActiveConnection) -> MinerId | None:
    """Normalize a MAC argument or send one safe invalid-input response."""
    try:
        return normalize_miner_id(msg.get("miner_id"))
    except AxeOSError:
        connection.send_error(msg["id"], "invalid_miner_id", "Miner ID is invalid")
        return None


def _miner_dto(runtime: BitaxeFleetRuntime, miner: EnrolledMiner) -> dict[str, object]:
    """Serialize one approved miner without raw payload fields."""
    coordinator = runtime.get_coordinator(miner.identity.miner_id)
    snapshot = coordinator.snapshot if coordinator is not None else None
    return {
        "enabled": miner.enabled,
        "endpoint": str(miner.endpoint.host),
        "firmware": miner.identity.firmware_version,
        "last_success_at": (
            coordinator.last_success_at.isoformat()
            if coordinator is not None and coordinator.last_success_at is not None
            else None
        ),
        "miner_id": str(miner.identity.miner_id),
        "model": miner.identity.asic_model,
        "name": miner.display_name or miner.identity.display_name,
        "online": coordinator is not None and coordinator.last_update_success,
        "policy": _policy_dto(miner.recovery_policy),
        "profile": _profile_dto(miner.recovery_profile),
        "telemetry": (
            {
                "best_difficulty": snapshot.telemetry.best_difficulty,
                "best_session_difficulty": snapshot.telemetry.best_session_difficulty,
                "hashrate_gh_s": snapshot.telemetry.hashrate_gh_s,
                "power_w": snapshot.telemetry.power_w,
                "temperature_c": snapshot.telemetry.temperature_c,
            }
            if snapshot is not None
            else None
        ),
        "health": (
            {
                "mining_paused": snapshot.health.mining_paused,
                "overheat_mode": snapshot.health.overheat_mode,
                "power_fault": snapshot.health.power_fault is not None,
                "hardware_fault": snapshot.health.hardware_fault is not None,
            }
            if snapshot is not None
            else None
        ),
    }


def _fleet_aggregates_dto(aggregates: FleetAggregates) -> dict[str, object]:
    """Serialize current fleet totals and coverage without per-miner raw data."""
    return {
        "best_difficulty": aggregates.best_difficulty,
        "best_difficulty_coverage": aggregates.best_difficulty_coverage,
        "best_session_difficulty": aggregates.best_session_difficulty,
        "best_session_difficulty_coverage": (
            aggregates.best_session_difficulty_coverage
        ),
        "efficiency_j_th": aggregates.efficiency_j_th,
        "enabled_miners": aggregates.enabled_miners,
        "hashrate_coverage": aggregates.hashrate_coverage,
        "online_miners": aggregates.online_miners,
        "overheat_coverage": aggregates.overheat_coverage,
        "overheating_miners": aggregates.overheating_miners,
        "power_coverage": aggregates.power_coverage,
        "total_hashrate_gh_s": aggregates.total_hashrate_gh_s,
        "total_hashrate_th_s": aggregates.total_hashrate_th_s,
        "total_power_w": aggregates.total_power_w,
        "total_uptime_seconds": aggregates.total_uptime_seconds,
        "unhealthy_coverage": aggregates.unhealthy_coverage,
        "unhealthy_miners": aggregates.unhealthy_miners,
        "uptime_coverage": aggregates.uptime_coverage,
    }


def _candidate_dto(candidate: object) -> dict[str, object]:
    """Serialize one pending candidate only after its HTTP identity validation."""
    from .discovery.models import DiscoveryCandidate

    if not isinstance(candidate, DiscoveryCandidate):
        raise TypeError("invalid candidate")
    return {
        "endpoint": str(candidate.endpoint.host),
        "firmware": candidate.identity.firmware_version,
        "last_seen_at": candidate.last_seen_at.isoformat(),
        "miner_id": str(candidate.identity.miner_id),
        "model": candidate.identity.asic_model,
        "name": candidate.identity.display_name,
        "source": candidate.source.value,
    }


def _history_dto(
    miner_id: MinerId, history: MinerTelemetryHistory
) -> dict[str, object]:
    """Serialize only bounded numeric recorder points for the panel graph."""
    return {
        "available": history.recorder_available,
        "end_at": history.end_at.isoformat(),
        "miner_id": str(miner_id),
        "schema_version": 1,
        "series": {
            "hashrate_gh_s": [
                {"at": point.observed_at.isoformat(), "value": point.value}
                for point in history.hashrate_gh_s
            ],
            "power_w": [
                {"at": point.observed_at.isoformat(), "value": point.value}
                for point in history.power_w
            ],
            "temperature_c": [
                {"at": point.observed_at.isoformat(), "value": point.value}
                for point in history.temperature_c
            ],
        },
        "start_at": history.start_at.isoformat(),
    }


def _fleet_history_dto(history: FleetTelemetryHistory) -> dict[str, object]:
    """Serialize a selected fleet series without entity or entry identifiers."""
    return {
        "available": history.recorder_available,
        "end_at": history.end_at.isoformat(),
        "metric": history.metric,
        "schema_version": 1,
        "series": [
            {"at": point.observed_at.isoformat(), "value": point.value}
            for point in history.points
        ],
        "start_at": history.start_at.isoformat(),
    }


def _scan_dto(runtime: BitaxeFleetRuntime) -> dict[str, object]:
    """Serialize bounded scan progress without individual failure details."""
    status = runtime.scan_status
    return {
        "completed_at": status.completed_at.isoformat()
        if status.completed_at is not None
        else None,
        "completed_hosts": status.completed_hosts,
        "discovered_candidates": status.discovered_candidates,
        "error": status.error,
        "network": status.network,
        "running": status.running,
        "started_at": status.started_at.isoformat() if status.started_at else None,
        "total_hosts": status.total_hosts,
    }


def _profile_dto(profile: object) -> dict[str, object] | None:
    """Serialize only the explicitly allowed six recovery settings."""
    from .axeos.models import RecoveryProfile

    if profile is None:
        return None
    if not isinstance(profile, RecoveryProfile):
        raise TypeError("invalid profile")
    return {
        "automatic_fan_speed": profile.automatic_fan_speed,
        "core_voltage_mv": profile.core_voltage_mv,
        "frequency_mhz": profile.frequency_mhz,
        "minimum_fan_speed_percent": profile.minimum_fan_speed_percent,
        "overclock_enabled": profile.overclock_enabled,
        "target_temperature_c": profile.target_temperature_c,
    }


def _policy_dto(policy: RecoveryPolicy) -> dict[str, object]:
    """Serialize a full policy so the panel never invents implicit defaults."""
    return {
        "automatic_profile_restore_enabled": policy.automatic_profile_restore_enabled,
        "automatic_recovery_enabled": policy.automatic_recovery_enabled,
        "consecutive_unhealthy_required": policy.consecutive_unhealthy_required,
        "cooldown_seconds": policy.cooldown_seconds,
        "max_attempts": policy.max_attempts,
        "overheat_policy": policy.overheat_policy.value,
        "post_restart_timeout_seconds": policy.post_restart_timeout_seconds,
        "rolling_window_seconds": policy.rolling_window_seconds,
        "startup_grace_seconds": policy.startup_grace_seconds,
        "verification_timeout_seconds": policy.verification_timeout_seconds,
    }


def _policy_from_message(value: object) -> RecoveryPolicy:
    """Reject unknown/malformed policy keys before they reach persistent state."""
    if not isinstance(value, dict):
        raise ValueError("invalid policy")
    policy: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValueError("invalid policy")
        policy[key] = item
    expected = {
        "automatic_profile_restore_enabled",
        "automatic_recovery_enabled",
        "consecutive_unhealthy_required",
        "cooldown_seconds",
        "max_attempts",
        "overheat_policy",
        "post_restart_timeout_seconds",
        "rolling_window_seconds",
        "startup_grace_seconds",
        "verification_timeout_seconds",
    }
    if set(policy) != expected:
        raise ValueError("invalid policy")
    from .axeos.models import OverheatPolicy

    overheat = policy["overheat_policy"]
    if not isinstance(overheat, str):
        raise ValueError("invalid policy")
    return RecoveryPolicy(
        automatic_profile_restore_enabled=_required_bool(
            policy, "automatic_profile_restore_enabled"
        ),
        automatic_recovery_enabled=_required_bool(policy, "automatic_recovery_enabled"),
        consecutive_unhealthy_required=_required_int(
            policy, "consecutive_unhealthy_required"
        ),
        cooldown_seconds=_required_int(policy, "cooldown_seconds"),
        max_attempts=_required_int(policy, "max_attempts"),
        overheat_policy=OverheatPolicy(overheat),
        post_restart_timeout_seconds=_required_int(
            policy, "post_restart_timeout_seconds"
        ),
        rolling_window_seconds=_required_int(policy, "rolling_window_seconds"),
        startup_grace_seconds=_required_int(policy, "startup_grace_seconds"),
        verification_timeout_seconds=_required_int(
            policy, "verification_timeout_seconds"
        ),
    )


def _required_bool(policy: dict[str, object], key: str) -> bool:
    """Read one strict JSON boolean from a panel policy DTO."""
    value = policy[key]
    if not isinstance(value, bool):
        raise ValueError("invalid policy")
    return value


def _required_int(policy: dict[str, object], key: str) -> int:
    """Read one strict integer from a panel policy DTO."""
    value = policy[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("invalid policy")
    return value
