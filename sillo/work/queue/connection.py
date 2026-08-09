"""
sillo.work.queue.connection — Multi-backend queue connection broker.

Manages named queue connections (sync, Redis, database) — inspired by
Laravel's queue connection system.  A single ``ConnectionManager``
brokers multiple backends, each identified by a name like ``"default"``,
``"redis"``, or ``"database"``.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from abc import ABC, abstractmethod
from typing import Annotated, Any

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
    ) -> tuple[str, str] | None:
        """Pop the next available job. Returns (job_id, payload) or None."""
        ...

    @abstractmethod
    async def size(self, queue_name: Annotated[str, Doc("Queue name.")]) -> int:
        """Number of pending jobs."""
        ...

    async def clear(self, queue_name: Annotated[str, Doc("Queue name.")]) -> None:
        """Remove all pending jobs from *queue_name*."""

    async def ack(
        self,
        queue_name: Annotated[str, Doc("Queue name.")],
        job_id: Annotated[str, Doc("Job ID to acknowledge.")],
    ) -> None:
        """Mark a job as successfully processed."""

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


class SyncConnection(QueueConnection):
    """In-process queue — backed by an ``asyncio.Queue`` with priority heap.

    Suitable for development and single-process deployments.  Not persistent.
    """

    def __init__(self):
        """Init"""
        self._queues: dict[str, asyncio.PriorityQueue] = {}
        self._delayed: dict[str, list[tuple[float, str, str]]] = {}
        self._pending: dict[str, dict[str, str]] = {}
        self._acks: dict[str, set[str]] = {}

    def _ensure(self, name: str) -> None:
        """Ensure"""
        if name not in self._queues:
            self._queues[name] = asyncio.PriorityQueue()
            self._delayed[name] = []
            self._pending[name] = {}
            self._acks[name] = set()

    async def push(self, queue_name: str, payload: str, *, delay: int = 0) -> str:
        """Push"""
        self._ensure(queue_name)
        job_id = uuid.uuid4().hex
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
    ) -> tuple[str, str] | None:
        """Pop"""
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
        """Size"""
        self._ensure(queue_name)
        return self._queues[queue_name].qsize() + len(self._delayed.get(queue_name, []))

    async def clear(self, queue_name: str) -> None:
        """Clear"""
        self._ensure(queue_name)
        while not self._queues[queue_name].empty():
            self._queues[queue_name].get_nowait()
        self._delayed[queue_name].clear()
        self._pending[queue_name].clear()

    def _release_delayed(self, name: str) -> None:
        """Release Delayed"""
        now = time.monotonic()
        remaining = []
        for when, jid, payload in self._delayed[name]:
            if when <= now:
                self._queues[name].put_nowait((0, jid, payload))
            else:
                remaining.append((when, jid, payload))
        self._delayed[name] = remaining


#: Move every job whose delay has elapsed onto the ready list, atomically.
#:
#: The read-then-write this replaces could not be made safe from the client:
#: two workers both saw the same due set and pushed it twice, and the delete
#: was ``ZREMRANGEBYSCORE(0, now)`` — a *range* — so a job that became due
#: between the read and the delete was erased without ever being pushed.
#: Removing each member by name, inside one script, closes both.
_MIGRATE_LUA = """
local due = redis.call('ZRANGEBYSCORE', KEYS[1], '-inf', ARGV[1])
for i = 1, #due do
    redis.call('LPUSH', KEYS[2], due[i])
    redis.call('ZREM', KEYS[1], due[i])
end
return #due
"""

#: Take one job from the ready list and claim it, atomically.
#:
#: The move and the claim have to happen together, or a crash between them
#: leaves an entry in ``processing`` that no deadline covers.
_CLAIM_LUA = """
local raw = redis.call('RPOP', KEYS[1])
if not raw then return false end
redis.call('LPUSH', KEYS[2], raw)
redis.call('ZADD', KEYS[3], ARGV[1], raw)
return raw
"""

#: Return timed-out claims to the ready list, and adopt orphans.
#:
#: Two jobs in one script. Any claim past its deadline goes back to the ready
#: list — that is the recovery path for a worker that died holding a job. And
#: anything sitting in ``processing`` with no claim at all is given one: that
#: is the entry a crash in the gap between ``BLMOVE`` and the claim would
#: otherwise strand forever, invisible to the deadline sweep.
_REAP_LUA = """
local expired = redis.call('ZRANGEBYSCORE', KEYS[2], '-inf', ARGV[1])
for i = 1, #expired do
    if redis.call('LREM', KEYS[1], 1, expired[i]) > 0 then
        redis.call('LPUSH', KEYS[3], expired[i])
    end
    redis.call('ZREM', KEYS[2], expired[i])
end
local held = redis.call('LRANGE', KEYS[1], 0, -1)
for i = 1, #held do
    if redis.call('ZSCORE', KEYS[2], held[i]) == false then
        redis.call('ZADD', KEYS[2], ARGV[2], held[i])
    end
end
return #expired
"""

#: Drop a finished job's claim.
#:
#: ``ack`` is handed a job id, not the raw entry, and the raw entry is what
#: the list holds. The in-flight list is bounded by the number of workers, so
#: scanning it is cheaper than maintaining a second index to avoid the scan.
_ACK_LUA = """
local held = redis.call('LRANGE', KEYS[1], 0, -1)
local prefix = ARGV[1] .. ':'
for i = 1, #held do
    if string.sub(held[i], 1, string.len(prefix)) == prefix then
        redis.call('LREM', KEYS[1], 1, held[i])
        redis.call('ZREM', KEYS[2], held[i])
        return 1
    end
end
return 0
"""


class RedisConnection(QueueConnection):
    """Redis-backed persistent queue connection.

    Delivery is **at-least-once**. A job is moved to an in-flight list when a
    worker takes it and only removed once that worker acknowledges it, so a
    worker that dies mid-job does not take the job with it — the job returns
    to the queue after ``visibility_timeout`` seconds and another worker runs
    it.

    The cost of that guarantee is that a job can run twice: once if it
    outlives its visibility timeout while still working, and once if a worker
    dies after finishing but before acknowledging. **Jobs must be
    idempotent.** There is no configuration that removes this; exactly-once
    delivery is not something a queue can offer.

    Attributes:
        visibility_timeout: Seconds a worker may hold a job before it is
            considered abandoned. Set it comfortably above the slowest job on
            the queue — too low and healthy jobs are re-run underneath
            themselves; too high and a crashed worker's job sits idle that
            long before anyone retries it.
    """

    def __init__(
        self,
        url: Annotated[str, Doc("Redis connection URL.")] = "redis://localhost:6379",
        *,
        prefix: Annotated[str, Doc("Key prefix.")] = "sillo:queue:",
        visibility_timeout: Annotated[
            float,
            Doc("Seconds before an unacknowledged job is handed to another worker."),
        ] = 300.0,
    ):
        """Init"""
        self.url = url
        self.prefix = prefix
        self.visibility_timeout = visibility_timeout
        self._redis: Any = None

    async def _r(self):
        """R"""
        if self._redis is not None:
            return self._redis
        self._redis = aioredis.from_url(self.url, decode_responses=True)
        return self._redis

    def _keys(self, queue_name: str) -> tuple[str, str, str, str]:
        """The four keys a queue occupies.

        Args:
            queue_name: Logical queue name.

        Returns:
            ``(ready, delayed, processing, claims)``. ``ready`` is the list
            workers take from, ``delayed`` the sorted set of not-yet-due jobs,
            ``processing`` the list of jobs currently held by a worker, and
            ``claims`` the sorted set of their deadlines.
        """
        key = f"{self.prefix}{queue_name}"
        return key, f"{key}:delayed", f"{key}:processing", f"{key}:claims"

    async def push(self, queue_name: str, payload: str, *, delay: int = 0) -> str:
        """Push"""
        r = await self._r()
        # `hash()` is seeded per process, so the same payload produced a
        # different id in every worker and ids collided within a microsecond.
        # An id nothing can correlate on is not an id.
        job_id = uuid.uuid4().hex
        key, delayed, _, _ = self._keys(queue_name)
        if delay > 0:
            await r.zadd(delayed, {f"{job_id}:{payload}": time.time() + delay})
        else:
            await r.lpush(key, f"{job_id}:{payload}")
        return job_id

    async def pop(
        self, queue_name: str, *, timeout: float = 0
    ) -> tuple[str, str] | None:
        """Pop"""
        r = await self._r()
        key, _delayed, processing, claims = self._keys(queue_name)

        await self._migrate_delayed(r, key)
        await self._reap_expired(r, queue_name)

        deadline = time.time() + self.visibility_timeout

        if timeout > 0:
            # BLMOVE is itself atomic, so the job is never in neither list.
            # The claim lands a moment later; an entry that misses it because
            # this process died in between is adopted by the next reap.
            raw = await r.blmove(key, processing, timeout, "RIGHT", "LEFT")
            if raw:
                await r.zadd(claims, {raw: deadline})
        else:
            raw = await r.eval(_CLAIM_LUA, 3, key, processing, claims, deadline)

        if not raw:
            return None
        jid, _, payload = raw.partition(":")
        return jid, payload

    async def size(self, queue_name: str) -> int:
        """Size"""
        r = await self._r()
        key, delayed, _, _ = self._keys(queue_name)
        return int(await r.llen(key)) + int(await r.zcard(delayed))

    async def clear(self, queue_name: str) -> None:
        """Clear"""
        r = await self._r()
        await r.delete(*self._keys(queue_name))

    async def ack(self, queue_name: str, job_id: str) -> None:
        """Drop a finished job's claim so it is never redelivered.

        Until this lands the job is still in flight as far as the queue is
        concerned, which is the whole point — a worker that dies before
        acknowledging has its job handed to someone else.

        Args:
            queue_name: Queue the job came from.
            job_id: Id returned by :meth:`push` and handed back by
                :meth:`pop`.
        """
        r = await self._r()
        _, _, processing, claims = self._keys(queue_name)
        await r.eval(_ACK_LUA, 2, processing, claims, job_id)

    async def fail(
        self, queue_name: str, job_id: str, payload: str, exception: str
    ) -> None:
        """Release a permanently failed job.

        The failure itself is recorded by the worker's failed-job repository;
        all this does is stop the queue holding the job in flight, so it is
        not redelivered once its visibility window closes.

        Args:
            queue_name: Queue the job came from.
            job_id: Id of the failed job.
            payload: Serialised payload, kept for the repository's benefit.
            exception: Exception message, likewise.
        """
        await self.ack(queue_name, job_id)

    async def in_flight(self, queue_name: str) -> int:
        """How many jobs are currently held by workers.

        Args:
            queue_name: Queue name.

        Returns:
            The number of jobs taken but not yet acknowledged. A number that
            keeps climbing means jobs are being taken and never acknowledged.
        """
        r = await self._r()
        _, _, processing, _ = self._keys(queue_name)
        return int(await r.llen(processing))

    async def _migrate_delayed(self, r, key: str) -> None:
        """Move every due delayed job onto the ready list.

        Args:
            r: Redis client.
            key: The ready-list key; the delayed set is derived from it.
        """
        await r.eval(_MIGRATE_LUA, 2, f"{key}:delayed", key, time.time())

    async def _reap_expired(self, r, queue_name: str) -> int:
        """Return abandoned jobs to the queue.

        Args:
            r: Redis client.
            queue_name: Queue name.

        Returns:
            How many jobs were reclaimed.
        """
        key, _, processing, claims = self._keys(queue_name)
        now = time.time()
        return int(
            await r.eval(
                _REAP_LUA,
                3,
                processing,
                claims,
                key,
                now,
                now + self.visibility_timeout,
            )
        )


class ConnectionManager:
    """Broker for multiple named queue connections.

    Usage::

        mgr = ConnectionManager()
        mgr.add("default", SyncConnection())
        mgr.add("redis", RedisConnection("redis://localhost:6379"))

        await mgr.connection("redis").push("emails", payload)
    """

    def __init__(self):
        """Init"""
        self._connections: dict[str, QueueConnection] = {}

    def add(
        self,
        name: Annotated[str, Doc("Connection name (e.g. 'default', 'redis').")],
        connection: Annotated[QueueConnection, Doc("Connection instance.")],
    ) -> ConnectionManager:
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
