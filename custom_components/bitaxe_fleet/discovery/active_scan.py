"""Bounded administrator-initiated private IPv4 scanning."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from ipaddress import IPv4Address, IPv4Network

from ..axeos.errors import AxeOSInvalidEndpointError
from ..axeos.models import MinerEndpoint
from ..const import ACTIVE_SCAN_CONCURRENCY, DEFAULT_HTTP_PORT, MAX_ACTIVE_SCAN_HOSTS

_PRIVATE_NETWORKS: tuple[IPv4Network, ...] = (
    IPv4Network("10.0.0.0/8"),
    IPv4Network("172.16.0.0/12"),
    IPv4Network("192.168.0.0/16"),
)

type Probe = Callable[[MinerEndpoint], Awaitable[bool]]
type Progress = Callable[[int, int], None]


def parse_private_network(value: object) -> IPv4Network:
    """Validate a bounded RFC 1918 IPv4 network before any probes are created."""
    if not isinstance(value, str):
        raise AxeOSInvalidEndpointError
    try:
        network = IPv4Network(value.strip(), strict=False)
    except ValueError:
        raise AxeOSInvalidEndpointError from None
    if not any(network.subnet_of(private) for private in _PRIVATE_NETWORKS):
        raise AxeOSInvalidEndpointError

    host_count = _host_count(network)
    if host_count > MAX_ACTIVE_SCAN_HOSTS:
        raise AxeOSInvalidEndpointError
    return network


def scan_host_count(network: IPv4Network) -> int:
    """Return the finite number of addresses an approved scan will probe."""
    return _host_count(network)


async def async_scan_network(
    network: IPv4Network, probe: Probe, progress: Progress
) -> int:
    """Probe a bounded network with fixed concurrency and clean cancellation."""
    hosts = tuple(network.hosts())
    total = len(hosts)
    if total == 0:
        return 0

    next_index = 0
    completed = 0
    discovered = 0
    index_lock = asyncio.Lock()

    async def _next_host() -> IPv4Address | None:
        nonlocal next_index
        async with index_lock:
            if next_index == total:
                return None
            host = hosts[next_index]
            next_index += 1
            return host

    async def _worker() -> int:
        nonlocal completed
        worker_discovered = 0
        while (host := await _next_host()) is not None:
            try:
                if await probe(MinerEndpoint(host=host, port=DEFAULT_HTTP_PORT)):
                    worker_discovered += 1
            finally:
                async with index_lock:
                    completed += 1
                    progress(completed, total)
        return worker_discovered

    workers = min(ACTIVE_SCAN_CONCURRENCY, total)
    results = await asyncio.gather(*(_worker() for _ in range(workers)))
    discovered = sum(results)
    return discovered


def _host_count(network: IPv4Network) -> int:
    """Count addresses that ``IPv4Network.hosts`` will produce without iteration."""
    if network.prefixlen == 32:
        return 1
    if network.prefixlen == 31:
        return 2
    return network.num_addresses - 2
