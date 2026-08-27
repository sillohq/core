"""
sillo.work.backends — Persistence backends for queues.

Backends abstract where tasks live between enqueue and execution.

MemoryBackend
    Single-process, non-persistent.  Uses a lock-protected min-heap.
    Perfect for development and testing.  Tasks survive as long as the
    process does.

RedisBackend
    Persistent, multi-process.  Uses a Redis sorted set (ZSET) scored by
    priority and creation timestamp — lower score first, so higher priority
    sorts earlier.  Workers block on BZPOPMIN for efficient polling.
    Requires a task registry mapping names → callables so that workers in
    different processes can reconstruct Task objects.
"""

from __future__ import annotations

import asyncio
import heapq
import json
import logging
import time
from typing import Any

try:
    import redis.asyncio as aioredis  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - exercised only without redis installed
    aioredis = None  # ty: ignore[invalid-assignment]

from .task import Task
from .types import (
    BackendUnavailable,
    QueueFull,
    QueueStats,
    TaskResult,
    TaskStatus,
)

logger = logging.getLogger("sillo.work.backends")

DEFAULT_REDIS_TIMEOUT = 5.0
REDIS_RESULT_TTL = 86400  # 24 hours


class MemoryBackend:
    """In-process queue backend — lock-protected min-heap.

    Thread-safe only within a single event loop.  Not suitable for
    multi-process deployments (use :class:`RedisBackend` instead).

    Parameters
    ----------
    max_size:
        Maximum number of tasks per queue.  ``None`` = unlimited.
    """

    def __init__(self, max_size: int | None = None):
        """Init"""
        self._queues: dict[str, list[tuple[float, Task]]] = {}
        self._results: dict[str, TaskResult] = {}
        self._dedup: dict[str, set] = {}
        self._events: dict[str, asyncio.Event] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._completed_counts: dict[str, int] = {}
        self._failed_counts: dict[str, int] = {}
        self._created_timestamps: dict[str, list[float]] = {}
        self.max_size = max_size

    def _ensure(self, name: str) -> None:
        """Ensure"""
        if name in self._queues:
            return
        self._queues[name] = []
        self._events[name] = asyncio.Event()
        self._locks[name] = asyncio.Lock()
        self._completed_counts[name] = 0
        self._failed_counts[name] = 0
        self._created_timestamps[name] = []

    # ── enqueue / dequeue ───────────────────────────────────────────────

    async def enqueue(self, task: Task) -> None:
        """Enqueue"""
        self._ensure(task.queue_name)

        if self.max_size is not None:
            async with self._locks[task.queue_name]:
                if len(self._queues[task.queue_name]) >= self.max_size:
                    raise QueueFull(
                        f"Queue '{task.queue_name}' is full ({self.max_size})",
                        queue_name=task.queue_name,
                    )

        async with self._locks[task.queue_name]:
            score = -task.priority.value * 1e12 + task.created_at
            heapq.heappush(self._queues[task.queue_name], (score, task))
            self._created_timestamps[task.queue_name].append(task.created_at)
            self._events[task.queue_name].set()

    async def dequeue(
        self, queue_name: str, timeout: float | None = None
    ) -> Task | None:
        """Dequeue"""
        self._ensure(queue_name)
        deadline = time.monotonic() + timeout if timeout else None

        while True:
            async with self._locks[queue_name]:
                if self._queues[queue_name]:
                    _, task = heapq.heappop(self._queues[queue_name])
                    return task
                self._events[queue_name].clear()

            if deadline is not None and time.monotonic() >= deadline:
                return None
            remaining = None if deadline is None else deadline - time.monotonic()
            if remaining is not None and remaining <= 0:  # pragma: no cover
                # The `deadline is not None and time.monotonic() >= deadline`
                # check just above already covers a deadline reached by this
                # point; reaching here instead requires the deadline to pass
                # in the instant between these two time.monotonic() calls.
                return None

            try:
                await asyncio.wait_for(
                    self._events[queue_name].wait(), timeout=remaining
                )
            except asyncio.TimeoutError:
                return None

    # ── result storage ──────────────────────────────────────────────────

    async def store_result(self, result: TaskResult) -> None:
        """Store Result"""
        self._results[result.task_id] = result
        if result.queue_name not in self._completed_counts:
            self._ensure(result.queue_name)
        if result.ok:
            self._completed_counts[result.queue_name] += 1
        else:
            self._failed_counts[result.queue_name] += 1

    async def get_result(self, task_id: str) -> TaskResult | None:
        """Get Result"""
        return self._results.get(task_id)

    # ── dedup ───────────────────────────────────────────────────────────

    async def is_duplicate(self, queue_name: str, dedup_key: str) -> bool:
        """Is Duplicate"""
        self._ensure(queue_name)
        if queue_name not in self._dedup:
            self._dedup[queue_name] = set()
        s = self._dedup[queue_name]
        if dedup_key in s:
            return True
        s.add(dedup_key)
        return False

    async def clear_dedup(self, queue_name: str, dedup_key: str) -> None:
        """Clear Dedup"""
        if queue_name in self._dedup:
            self._dedup[queue_name].discard(dedup_key)

    # ── stats ───────────────────────────────────────────────────────────

    async def queue_size(self, name: str) -> int:
        """Queue Size"""
        self._ensure(name)
        return len(self._queues[name])

    async def queue_stats(self, name: str) -> QueueStats:
        """Queue Stats"""
        self._ensure(name)
        now = time.time()
        oldest = 0
        if self._created_timestamps[name]:
            oldest = int((now - min(self._created_timestamps[name])) * 1000)
        return QueueStats(
            name=name,
            size=len(self._queues[name]),
            completed=self._completed_counts[name],
            failed=self._failed_counts[name],
            oldest_age_ms=oldest,
        )


class RedisBackend:
    """Redis-backed persistent queue.

    Uses a sorted set per queue.  Tasks are scored so that higher priority
    and earlier creation dequeue first.  Workers block on ``BZPOPMAX``
    rather than polling.

    Parameters
    ----------
    url:
        Redis connection URL (e.g. ``redis://localhost:6379/0``).
    prefix:
        Key prefix to namespace all Sillo work keys.
    task_registry:
        ``{name: callable}`` mapping so that workers can reconstruct
        ``Task`` objects from serialised payloads.  Without this, tasks
        dequeued by remote workers cannot be executed.
    """

    def __init__(
        self,
        url: str = "redis://localhost:6379",
        *,
        prefix: str = "sillo:work:",
        task_registry: dict[str, Any] | None = None,
    ):
        """Init"""
        self.url = url
        self.prefix = prefix
        self._registry = task_registry or {}
        self._redis: Any = None

    def register(self, name: str, func) -> None:
        """Register"""
        self._registry[name] = func

    async def _r(self):
        """R"""
        if self._redis is not None:
            return self._redis
        if aioredis is None:
            raise ImportError("redis is required. Install: pip install redis")
        try:
            self._redis = aioredis.from_url(
                self.url,
                decode_responses=True,
                socket_timeout=DEFAULT_REDIS_TIMEOUT,
            )
            await self._redis.ping()
        except Exception as e:
            raise BackendUnavailable(f"Redis unavailable: {e}")
        return self._redis

    # ── enqueue / dequeue ───────────────────────────────────────────────

    async def enqueue(self, task: Task) -> None:
        """Enqueue"""
        r = await self._r()
        key = f"{self.prefix}q:{task.queue_name}"
        score = -task.priority.value * 1e12 + task.created_at
        payload = task.serialize()
        await r.zadd(key, {payload: score})

    async def dequeue(
        self, queue_name: str, timeout: float | None = None
    ) -> Task | None:
        """Dequeue"""
        r = await self._r()
        key = f"{self.prefix}q:{queue_name}"
        effective_timeout = timeout or 0
        try:
            # BZPOPMIN, not MAX: enqueue scores a task -priority * 1e12 +
            # created_at, so a *higher* priority is a *lower* score — which is
            # what lets the memory backend pop from a min-heap. Popping the max
            # here served the lowest-priority task first, exactly inverting the
            # ordering this backend exists to provide.
            result = await asyncio.wait_for(
                r.bzpopmin(key, timeout=effective_timeout),
                timeout=effective_timeout + 1,
            )
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            logger.error(f"Redis dequeue error: {e}")
            raise BackendUnavailable(f"Redis error: {e}")

        if result is None:
            return None

        # BZPOPMIN replies with (key, member, score) — unpacking two names off
        # it raised ValueError on every single dequeue.
        _, payload, _score = result
        try:
            d = json.loads(payload)
        except json.JSONDecodeError:
            logger.warning("Corrupt task payload — dropped")
            return None

        func = self._registry.get(d["name"])
        if func is None:
            logger.warning(f"Task '{d['name']}' not in registry — dropping")
            return None

        task = Task(
            func,
            name=d["name"],
            max_attempts=d.get("max_attempts", 1),
            queue_name=d.get("queue_name", queue_name),
            metadata=d.get("metadata", {}),
        )
        task.id = d.get("id", task.id)
        return task

    # ── result storage ──────────────────────────────────────────────────

    async def store_result(self, result: TaskResult) -> None:
        """Store Result"""
        r = await self._r()
        key = f"{self.prefix}result:{result.task_id}"
        await r.set(key, result.to_json(), ex=REDIS_RESULT_TTL)

    async def get_result(self, task_id: str) -> TaskResult | None:
        """Get Result"""
        r = await self._r()
        data = await r.get(f"{self.prefix}result:{task_id}")
        if not data:
            return None
        d = json.loads(data)
        return TaskResult(
            task_id=d["task_id"],
            name=d["name"],
            status=TaskStatus(d.get("status", "completed")),
        )

    # ── dedup ───────────────────────────────────────────────────────────

    async def is_duplicate(self, queue_name: str, dedup_key: str) -> bool:
        """Report whether this key has been seen, and record it if not.

        Check-and-set, matching :meth:`MemoryBackend.is_duplicate`: the first
        call for a key returns ``False`` and claims it, and every call after
        that returns ``True``. This only checked, never claimed, so it returned
        ``False`` forever and nothing was ever deduplicated.

        ``SET NX`` does both halves in one round trip, so two workers racing on
        the same key cannot both be told they are the first.

        Args:
            queue_name: Queue the key is scoped to.
            dedup_key: The caller's idempotency key.

        Returns:
            ``True`` if the key was already claimed.
        """
        r = await self._r()
        key = f"{self.prefix}dedup:{queue_name}:{dedup_key}"
        claimed = await r.set(key, "1", nx=True)
        return not claimed

    async def clear_dedup(self, queue_name: str, dedup_key: str) -> None:
        """Clear Dedup"""
        r = await self._r()
        await r.delete(f"{self.prefix}dedup:{queue_name}:{dedup_key}")

    # ── stats ───────────────────────────────────────────────────────────

    async def queue_size(self, name: str) -> int:
        """Queue Size"""
        r = await self._r()
        return await r.zcard(f"{self.prefix}q:{name}")

    async def queue_stats(self, name: str) -> QueueStats:
        """Queue Stats"""
        r = await self._r()
        size = await r.zcard(f"{self.prefix}q:{name}")
        completed = int(await r.get(f"{self.prefix}stats:{name}:completed") or 0)
        failed = int(await r.get(f"{self.prefix}stats:{name}:failed") or 0)
        return QueueStats(name=name, size=size, completed=completed, failed=failed)

    # ── misc ────────────────────────────────────────────────────────────

    async def flush(self, queue_name: str) -> None:
        """Flush"""
        r = await self._r()
        await r.delete(f"{self.prefix}q:{queue_name}")

    async def ping(self) -> bool:
        """Ping"""
        try:
            r = await self._r()
            return await r.ping()
        except Exception:
            return False
