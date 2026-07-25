"""
sillo.work.queue.connection — Multi-backend queue connection broker.

Manages named queue connections (sync, Redis, database) — inspired by
Laravel's queue connection system.  A single ``ConnectionManager``
brokers multiple backends, each identified by a name like ``"default"``,
``"redis"``, or ``"database"``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Annotated, Any, Dict, List, Optional, Set

from typing_extensions import Doc

logger = logging.getLogger("sillo.work.queue.connection")

try:
    import redis.asyncio as aioredis  # type: ignore[import-untyped]
except ImportError:
    aioredis = None  # ty: ignore[invalid-assignment]


class QueueConnection(ABC):
    """Abstract queue connection — push / pop / size / clear."""

    @abstractmethod
    async def push(
        self,
        queue_name: Annotated[str, Doc("Target queue name.")],
        payload: Annotated[str, Doc("Serialised job payload.")],
        *,
        delay: Annotated[int, Doc("Seconds to delay before the job is available.")] = 0,
    ) -> str:
        """Push a job onto the queue. Returns a job ID."""
        ...

    @abstractmethod
    async def pop(
        self,
        queue_name: Annotated[str, Doc("Queue to pop from.")],
        *,
        timeout: Annotated[float, Doc("Seconds to block waiting for a job.")] = 0,
    ) -> Optional[tuple[str, str]]:
        """Pop the next available job. Returns (job_id, payload) or None."""
        ...

    @abstractmethod
    async def size(self, queue_name: Annotated[str, Doc("Queue name.")]) -> int:
        """Number of pending jobs."""
        ...

    async def clear(self, queue_name: Annotated[str, Doc("Queue name.")]) -> None:
        """Remove all pending jobs from *queue_name*."""
        ...

    async def ack(
        self,
        queue_name: Annotated[str, Doc("Queue name.")],
        job_id: Annotated[str, Doc("Job ID to acknowledge.")],
    ) -> None:
        """Mark a job as successfully processed."""
        ...

    async def fail(
        self,
        queue_name: Annotated[str, Doc("Queue name.")],
        job_id: Annotated[str, Doc("Job ID that failed.")],
        payload: Annotated[
            str, Doc("Serialised job payload for the failed repository.")
        ],
        exception: Annotated[str, Doc("Exception message.")],
    ) -> None:
        """Record a permanently failed job."""
        ...


class SyncConnection(QueueConnection):
    """In-process queue — backed by an ``asyncio.Queue`` with priority heap.

    Suitable for development and single-process deployments.  Not persistent.
    """

    def __init__(self):
        """Init

        Returns:
            [description]

        Raises:
            [description]
        """
        self._queues: Dict[str, asyncio.PriorityQueue] = {}
        self._delayed: Dict[str, List[tuple[float, str, str]]] = {}
        self._pending: Dict[str, Dict[str, str]] = {}
        self._acks: Dict[str, Set[str]] = {}

    def _ensure(self, name: str) -> None:
        """Ensure

        Args:
            name: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        if name not in self._queues:
            self._queues[name] = asyncio.PriorityQueue()
            self._delayed[name] = []
            self._pending[name] = {}
            self._acks[name] = set()

    async def push(self, queue_name: str, payload: str, *, delay: int = 0) -> str:
        """Push

        Args:
            queue_name: [description]
            payload: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        self._ensure(queue_name)
        job_id = f"{int(time.time() * 1e6)}-{id(payload)}"
        if delay > 0:
            self._delayed[queue_name].append(
                (time.monotonic() + delay, job_id, payload)
            )
        else:
            await self._queues[queue_name].put((0, job_id, payload))
        self._pending[queue_name][job_id] = payload
        return job_id

    async def pop(
        self, queue_name: str, *, timeout: float = 0
    ) -> Optional[tuple[str, str]]:
        """Pop

        Args:
            queue_name: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        self._ensure(queue_name)

        self._release_delayed(queue_name)

        try:
            _, job_id, payload = await asyncio.wait_for(
                self._queues[queue_name].get(), timeout=timeout or None
            )
            return job_id, payload
        except asyncio.TimeoutError:
            return None

    async def size(self, queue_name: str) -> int:
        """Size

        Args:
            queue_name: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        self._ensure(queue_name)
        return self._queues[queue_name].qsize() + len(self._delayed.get(queue_name, []))

    async def clear(self, queue_name: str) -> None:
        """Clear

        Args:
            queue_name: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        self._ensure(queue_name)
        while not self._queues[queue_name].empty():
            self._queues[queue_name].get_nowait()
        self._delayed[queue_name].clear()
        self._pending[queue_name].clear()

    def _release_delayed(self, name: str) -> None:
        """Release Delayed

        Args:
            name: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        now = time.monotonic()
        remaining = []
        for when, jid, payload in self._delayed[name]:
            if when <= now:
                self._queues[name].put_nowait((0, jid, payload))
            else:
                remaining.append((when, jid, payload))
        self._delayed[name] = remaining


class RedisConnection(QueueConnection):
    """Redis-backed persistent queue connection.

    Uses sorted sets for pending/delayed jobs and lists for active work.
    """

    def __init__(
        self,
        url: Annotated[str, Doc("Redis connection URL.")] = "redis://localhost:6379",
        *,
        prefix: Annotated[str, Doc("Key prefix.")] = "sillo:queue:",
    ):
        """Init

        Args:
            url: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        self.url = url
        self.prefix = prefix
        self._redis: Any = None

    async def _r(self):
        """R

        Returns:
            [description]

        Raises:
            [description]
        """
        if self._redis is not None:
            return self._redis
        self._redis = aioredis.from_url(self.url, decode_responses=True)
        return self._redis

    async def push(self, queue_name: str, payload: str, *, delay: int = 0) -> str:
        """Push

        Args:
            queue_name: [description]
            payload: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        r = await self._r()
        job_id = f"{int(time.time() * 1e6)}-{hash(payload)}"
        key = f"{self.prefix}{queue_name}"
        if delay > 0:
            score = time.time() + delay
            await r.zadd(f"{key}:delayed", {f"{job_id}:{payload}": score})
        else:
            await r.lpush(key, f"{job_id}:{payload}")
        return job_id

    async def pop(
        self, queue_name: str, *, timeout: float = 0
    ) -> Optional[tuple[str, str]]:
        """Pop

        Args:
            queue_name: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        r = await self._r()
        key = f"{self.prefix}{queue_name}"
        await self._migrate_delayed(r, key)

        if timeout > 0:
            result = await r.brpop(key, timeout=int(timeout))
        else:
            result = await r.rpop(key)

        if result:
            raw = result if isinstance(result, str) else result[1]
            jid, _, payload = raw.partition(":")
            return jid, payload
        return None

    async def size(self, queue_name: str) -> int:
        """Size

        Args:
            queue_name: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        r = await self._r()
        key = f"{self.prefix}{queue_name}"
        return await r.llen(key)

    async def clear(self, queue_name: str) -> None:
        """Clear

        Args:
            queue_name: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        r = await self._r()
        await r.delete(f"{self.prefix}{queue_name}")

    async def _migrate_delayed(self, r, key: str) -> None:
        """Migrate Delayed

        Args:
            r: [description]
            key: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        now = time.time()
        delayed_key = f"{key}:delayed"
        items = await r.zrangebyscore(delayed_key, 0, now)
        if items:
            for item in items:
                await r.lpush(key, item)
            await r.zremrangebyscore(delayed_key, 0, now)


class ConnectionManager:
    """Broker for multiple named queue connections.

    Usage::

        mgr = ConnectionManager()
        mgr.add("default", SyncConnection())
        mgr.add("redis", RedisConnection("redis://localhost:6379"))

        await mgr.connection("redis").push("emails", payload)
    """

    def __init__(self):
        """Init

        Returns:
            [description]

        Raises:
            [description]
        """
        self._connections: Dict[str, QueueConnection] = {}

    def add(
        self,
        name: Annotated[str, Doc("Connection name (e.g. 'default', 'redis').")],
        connection: Annotated[QueueConnection, Doc("Connection instance.")],
    ) -> "ConnectionManager":
        """Register a named connection. Returns self for chaining."""
        self._connections[name] = connection
        return self

    def connection(
        self, name: Annotated[str, Doc("Connection name.")] = "default"
    ) -> QueueConnection:
        """Retrieve a connection by name. Raises KeyError if not found."""
        if name not in self._connections:
            raise KeyError(
                f"Queue connection '{name}' not registered. Use manager.add('{name}', ...)"
            )
        return self._connections[name]
