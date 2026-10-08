"""Owner-safe lease locks built on Sillo cache backends."""

from __future__ import annotations

import asyncio
import secrets
import time
from typing import TYPE_CHECKING

from typing_extensions import Self

if TYPE_CHECKING:
    from .base import BaseCache


class LockNotAcquiredError(RuntimeError):
    """Raised when entering a lock context without acquiring its lease."""


class Lock:
    """A lease-based lock whose release and renewal are tied to one owner.

    ``MemoryCache`` coordinates coroutines in one process. ``RedisCache`` uses
    Redis ``SET NX PX`` and is safe across processes sharing the same Redis
    database. A lease is required: a crashed owner cannot block work forever.
    """

    def __init__(
        self,
        cache: BaseCache,
        name: str,
        *,
        lease: float = 30,
        blocking_timeout: float | None = None,
        retry_interval: float = 0.1,
    ) -> None:
        if not isinstance(name, str) or not name:
            raise ValueError("lock name must be a non-empty string")
        if lease <= 0:
            raise ValueError("lease must be greater than zero")
        if blocking_timeout is not None and blocking_timeout < 0:
            raise ValueError("blocking_timeout must be non-negative")
        if retry_interval <= 0:
            raise ValueError("retry_interval must be greater than zero")
        self._cache = cache
        self.name = name
        self.lease = lease
        self.blocking_timeout = blocking_timeout
        self.retry_interval = retry_interval
        self._token = secrets.token_urlsafe(24)
        self._acquired = False

    @property
    def acquired(self) -> bool:
        """Whether this instance currently owns the lease."""
        return self._acquired

    async def acquire(self) -> bool:
        """Try to acquire the lock, optionally polling until the deadline."""
        deadline = (
            None
            if self.blocking_timeout is None
            else time.monotonic() + self.blocking_timeout
        )
        while True:
            if await self._cache._acquire_lock(self.name, self._token, self.lease):
                self._acquired = True
                return True
            if deadline is None or time.monotonic() >= deadline:
                return False
            await asyncio.sleep(
                min(self.retry_interval, max(0, deadline - time.monotonic()))
            )

    async def extend(self, lease: float | None = None) -> bool:
        """Renew this owner's lease; return ``False`` if ownership was lost."""
        if not self._acquired:
            return False
        duration = self.lease if lease is None else lease
        if duration <= 0:
            raise ValueError("lease must be greater than zero")
        renewed = await self._cache._extend_lock(self.name, self._token, duration)
        self._acquired = bool(renewed)
        return self._acquired

    async def release(self) -> bool:
        """Release only if this object still owns the lock."""
        if not self._acquired:
            return False
        released = await self._cache._release_lock(self.name, self._token)
        self._acquired = False
        return bool(released)

    async def __aenter__(self) -> Self:
        if not await self.acquire():
            raise LockNotAcquiredError(f"could not acquire lock {self.name!r}")
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.release()
