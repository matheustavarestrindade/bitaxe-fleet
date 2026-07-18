"""mDNS observations, bounded scans, and explicit candidate approval."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from homeassistant.components import zeroconf as ha_zeroconf
from homeassistant.core import HomeAssistant
from zeroconf import ServiceStateChange, Zeroconf
from zeroconf.asyncio import AsyncServiceBrowser, AsyncServiceInfo

from ..axeos.client import AxeOSClient
from ..axeos.errors import AxeOSError
from ..axeos.models import EnrolledMiner, MinerEndpoint, MinerId, MinerSnapshot
from ..axeos.parser import parse_private_ipv4
from ..const import AXEOS_ZEROCONF_SERVICE_TYPE, DEFAULT_HTTP_PORT
from ..storage import MinerRegistry
from .active_scan import async_scan_network, parse_private_network, scan_host_count
from .models import (
    DiscoveryCandidate,
    DiscoveryScanStatus,
    DiscoverySource,
)

_LOGGER = logging.getLogger(__name__)

type SnapshotCallback = Callable[[MinerSnapshot, EnrolledMiner], Awaitable[None]]
type ApprovalCallback = Callable[[EnrolledMiner], Awaitable[None]]


class DiscoveryError(Exception):
    """Base error for safe discovery operations."""


class CandidateNotFoundError(DiscoveryError):
    """Raised when an approval references a candidate no longer pending."""


class CandidateChangedError(DiscoveryError):
    """Raised when final approval finds a different MAC at the candidate endpoint."""


class ScanInProgressError(DiscoveryError):
    """Raised when an administrator starts a scan while one is already running."""


class DiscoveryManager:
    """Own safe candidate state for one loaded fleet runtime."""

    def __init__(
        self,
        hass: HomeAssistant,
        registry: MinerRegistry,
        make_client: Callable[[MinerEndpoint], AxeOSClient],
        on_known_snapshot: SnapshotCallback,
        on_approved: ApprovalCallback,
    ) -> None:
        """Initialize a manager with read-only probing and explicit callbacks."""
        self._hass = hass
        self._registry = registry
        self._make_client = make_client
        self._on_known_snapshot = on_known_snapshot
        self._on_approved = on_approved
        self._browser: AsyncServiceBrowser | None = None
        self._candidates: dict[MinerId, DiscoveryCandidate] = {}
        self._candidate_lock = asyncio.Lock()
        self._closed = False
        self._scan_status = DiscoveryScanStatus.idle()
        self._scan_task: asyncio.Task[None] | None = None
        self._tasks: set[asyncio.Task[object]] = set()

    @property
    def candidates(self) -> tuple[DiscoveryCandidate, ...]:
        """Return pending candidates sorted by their stable permanent identity."""
        return tuple(
            sorted(
                self._candidates.values(),
                key=lambda candidate: candidate.identity.miner_id,
            )
        )

    @property
    def scan_status(self) -> DiscoveryScanStatus:
        """Return a snapshot of active or completed scan progress."""
        return self._scan_status

    async def async_start(self) -> None:
        """Start the AxeOS mDNS browser without auto-enrolling candidates."""
        if self._closed:
            return
        async_zeroconf = await ha_zeroconf.async_get_async_instance(self._hass)
        self._browser = AsyncServiceBrowser(
            async_zeroconf.zeroconf,
            AXEOS_ZEROCONF_SERVICE_TYPE,
            handlers=[self._async_on_service_state_change],
        )

    async def async_stop(self) -> None:
        """Cancel scans, probes, and mDNS callbacks during config-entry unload."""
        if self._closed:
            return
        self._closed = True
        if self._browser is not None:
            await self._browser.async_cancel()
            self._browser = None
        if self._scan_task is not None:
            self._scan_task.cancel()
            await asyncio.gather(self._scan_task, return_exceptions=True)
            self._scan_task = None
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    async def async_observe_manual_endpoint(self, endpoint: MinerEndpoint) -> bool:
        """Probe one caller-approved endpoint as a discovery observation."""
        return await self._async_probe_endpoint(endpoint, DiscoverySource.MANUAL)

    def async_start_scan(self, network_text: str) -> DiscoveryScanStatus:
        """Start one explicit bounded scan and return its initial status immediately."""
        if self._closed:
            raise DiscoveryError("discovery is not running")
        if self._scan_task is not None and not self._scan_task.done():
            raise ScanInProgressError
        network = parse_private_network(network_text)
        self._scan_status = DiscoveryScanStatus(
            network=str(network),
            running=True,
            total_hosts=scan_host_count(network),
            completed_hosts=0,
            discovered_candidates=0,
            started_at=datetime.now(UTC),
            completed_at=None,
            error=None,
        )
        self._scan_task = self._hass.async_create_background_task(
            self._async_run_scan(network),
            f"{self._registry.__class__.__name__} active scan",
        )
        return self._scan_status

    async def async_approve_candidate(self, miner_id: MinerId) -> EnrolledMiner:
        """Revalidate and explicitly approve one pending candidate MAC."""
        async with self._candidate_lock:
            candidate = self._candidates.get(miner_id)
        if candidate is None:
            raise CandidateNotFoundError

        try:
            snapshot = await self._make_client(
                candidate.endpoint
            ).async_get_system_info()
        except AxeOSError as err:
            raise DiscoveryError("candidate could not be revalidated") from err
        if snapshot.identity.miner_id != miner_id:
            async with self._candidate_lock:
                self._candidates.pop(miner_id, None)
            raise CandidateChangedError

        miner = await self._registry.async_enroll(snapshot)
        async with self._candidate_lock:
            self._candidates.pop(miner_id, None)
        await self._on_approved(miner)
        return miner

    async def async_reject_candidate(self, miner_id: MinerId) -> None:
        """Persist an administrator rejection and remove the pending candidate."""
        await self._registry.async_reject_candidate(miner_id)
        async with self._candidate_lock:
            self._candidates.pop(miner_id, None)

    def _async_on_service_state_change(
        self,
        zeroconf: Zeroconf,
        service_type: str,
        name: str,
        state_change: ServiceStateChange,
    ) -> None:
        """Schedule a read-only validation for new or updated mDNS observations."""
        if self._closed or state_change not in {
            ServiceStateChange.Added,
            ServiceStateChange.Updated,
        }:
            return
        task = self._hass.async_create_background_task(
            self._async_probe_service(zeroconf, service_type, name),
            "Bitaxe Fleet mDNS probe",
        )
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _async_probe_service(
        self, zeroconf: Zeroconf, service_type: str, name: str
    ) -> None:
        """Resolve mDNS data only as a hint, then validate through AxeOS HTTP."""
        info = AsyncServiceInfo(service_type, name)
        if not await info.async_request(zeroconf, 3000):
            return
        if info.port != DEFAULT_HTTP_PORT:
            return
        for address in info.parsed_addresses():
            try:
                host = parse_private_ipv4(address)
            except AxeOSError:
                continue
            await self._async_probe_endpoint(
                MinerEndpoint(host=host, port=DEFAULT_HTTP_PORT), DiscoverySource.MDNS
            )

    async def _async_run_scan(self, network: object) -> None:
        """Execute one bounded scan and retain a safe completion summary."""
        try:
            from ipaddress import IPv4Network

            if not isinstance(network, IPv4Network):
                raise TypeError("invalid scan network")
            candidates = await async_scan_network(
                network,
                self._async_probe_active_scan_endpoint,
                self._async_update_scan_progress,
            )
        except asyncio.CancelledError:
            raise
        except DiscoveryError as err:
            self._finish_scan(error=str(err))
        except Exception:
            _LOGGER.exception("Unexpected error during Bitaxe Fleet active scan")
            self._finish_scan(error="scan failed")
        else:
            self._finish_scan(discovered_candidates=candidates)

    async def _async_probe_active_scan_endpoint(self, endpoint: MinerEndpoint) -> bool:
        """Probe one scan host without surfacing expected closed-port failures."""
        return await self._async_probe_endpoint(endpoint, DiscoverySource.ACTIVE_SCAN)

    def _async_update_scan_progress(self, completed: int, total: int) -> None:
        """Publish bounded progress without adding a task per scanned host."""
        status = self._scan_status
        self._scan_status = DiscoveryScanStatus(
            network=status.network,
            running=True,
            total_hosts=total,
            completed_hosts=completed,
            discovered_candidates=status.discovered_candidates,
            started_at=status.started_at,
            completed_at=None,
            error=None,
        )

    def _finish_scan(
        self, *, discovered_candidates: int | None = None, error: str | None = None
    ) -> None:
        """Mark an active scan complete with no endpoint data in its status."""
        status = self._scan_status
        self._scan_status = DiscoveryScanStatus(
            network=status.network,
            running=False,
            total_hosts=status.total_hosts,
            completed_hosts=status.completed_hosts,
            discovered_candidates=(
                status.discovered_candidates
                if discovered_candidates is None
                else discovered_candidates
            ),
            started_at=status.started_at,
            completed_at=datetime.now(UTC),
            error=error,
        )

    async def _async_probe_endpoint(
        self, endpoint: MinerEndpoint, source: DiscoverySource
    ) -> bool:
        """Validate one candidate read-only and route it by permanent MAC identity."""
        if self._closed:
            return False
        try:
            snapshot = await self._make_client(endpoint).async_get_system_info()
        except AxeOSError:
            return False

        miner_id = snapshot.identity.miner_id
        enrolled = self._registry.get(miner_id)
        if enrolled is not None:
            updated = await self._registry.async_update_from_snapshot(snapshot)
            if updated is not None:
                await self._on_known_snapshot(snapshot, updated)
            return False
        if miner_id in self._registry.rejected_candidates:
            return False

        candidate = DiscoveryCandidate.from_snapshot(snapshot, source)
        async with self._candidate_lock:
            previous = self._candidates.get(miner_id)
            self._candidates[miner_id] = (
                candidate if previous is None else previous.updated(snapshot, source)
            )
        return True
