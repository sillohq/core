from __future__ import annotations

import typing

if typing.TYPE_CHECKING:
    import httpx


class ConnectionPoolConfig:
    """Configuration for the httpx connection pool.

    Attributes:
        max_connections: Maximum number of concurrent connections.
        max_keepalive_connections: Maximum idle connections kept alive.
        keepalive_expiry: Time in seconds before an idle connection is closed.
        uds: Path to a Unix domain socket for the connection.
    """

    def __init__(
        self,
        max_connections: int = 50,
        max_keepalive_connections: int = 20,
        keepalive_expiry: float = 30.0,
        uds: str | None = None,
    ) -> None:
        self.max_connections = max_connections
        self.max_keepalive_connections = max_keepalive_connections
        self.keepalive_expiry = keepalive_expiry
        self.uds = uds

    def build_limits(self) -> httpx.Limits:
        """Build an httpx.Limits instance from this configuration."""
        import httpx

        return httpx.Limits(
            max_connections=self.max_connections,
            max_keepalive_connections=self.max_keepalive_connections,
            keepalive_expiry=self.keepalive_expiry,
        )

    def build_transport(self, verify_ssl: bool = True) -> httpx.AsyncHTTPTransport:
        """Build an httpx.AsyncHTTPTransport from this configuration."""
        import httpx

        return httpx.AsyncHTTPTransport(
            limits=self.build_limits(),
            verify=verify_ssl,
            uds=self.uds,
        )


__all__ = [
    "ConnectionPoolConfig",
]
