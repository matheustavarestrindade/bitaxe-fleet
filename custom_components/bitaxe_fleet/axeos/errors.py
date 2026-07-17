"""Safe, typed errors raised by the AxeOS boundary."""

from __future__ import annotations


class AxeOSError(Exception):
    """Base error for a failed AxeOS operation."""


class AxeOSConnectionError(AxeOSError):
    """The miner could not be reached."""

    def __init__(self, operation: str) -> None:
        """Initialize a connection failure without exposing the endpoint."""
        super().__init__(f"AxeOS {operation} connection failed")


class AxeOSHTTPError(AxeOSError):
    """AxeOS returned an unexpected HTTP response status."""

    def __init__(self, operation: str, status: int) -> None:
        """Initialize an HTTP failure without exposing the response body."""
        self.status = status
        super().__init__(f"AxeOS {operation} returned HTTP {status}")


class AxeOSInvalidEndpointError(AxeOSError):
    """A user-provided endpoint is outside the allowed local-network scope."""

    def __init__(self) -> None:
        """Initialize an invalid endpoint error."""
        super().__init__("AxeOS host must be a private IPv4 address")


class AxeOSInvalidResponseError(AxeOSError):
    """AxeOS returned a response that cannot safely be interpreted."""

    def __init__(self, operation: str, reason: str) -> None:
        """Initialize a response failure without retaining payload data."""
        super().__init__(f"AxeOS {operation} returned an invalid response: {reason}")


class AxeOSTimeoutError(AxeOSError):
    """An AxeOS operation exceeded its bounded timeout."""

    def __init__(self, operation: str) -> None:
        """Initialize a timeout failure without exposing the endpoint."""
        super().__init__(f"AxeOS {operation} timed out")
