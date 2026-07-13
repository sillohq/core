"""
sillo.work.backends — Persistence backends for queues.

Backends abstract where tasks live between enqueue and execution.

MemoryBackend
    Single-process, non-persistent.  Uses a lock-protected min-heap.
    Perfect for development and testing.  Tasks survive as long as the
    process does.

RedisBackend
    Persistent, multi-process.  Uses a Redis sorted set (ZSET) scored by
    priority and creation timestamp.  Workers block on BZPOPMAX for
    efficient polling.  Requires a task registry mapping names → callables
    so that workers in different processes can reconstruct Task objects.
"""

from __future__ import annotations

import asyncio
import heapq
import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from .task import Task
from .types import (
    BackendUnavailable,
    QueueFull,
    QueueStats,
    TaskPriority,
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

    def __init__(self, max_size: Optional[int] = None):
        self._queues: Dict[str, List[Tuple[float, Task]]] = {}
        self._results: Dict[str, TaskResult] = {}
        self._dedup: Dict[str, set] = {}
        self._events: Dict[str, asyncio.Event] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._completed_counts: Dict[str, int] = {}
        self._failed_counts: Dict[str, int] = {}
        self._created_timestamps: Dict[str, List[float]] = {}
        self.max_size = max_size

    def _ensure(self, name: str) -> None:
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
        self, queue_name: str, timeout: Optional[float] = None
    ) -> Optional[Task]:
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
            if remaining is not None and remaining <= 0:
                return None

            try:
                await asyncio.wait_for(
                    self._events[queue_name].wait(), timeout=remaining
                )
            except asyncio.TimeoutError:
                return None

    # ── result storage ──────────────────────────────────────────────────

    async def store_result(self, result: TaskResult) -> None:
        self._results[result.task_id] = result
        if result.queue_name not in self._completed_counts:
            self._ensure(result.queue_name)
        if result.ok:
            self._completed_counts[result.queue_name] += 1
        else:
            self._failed_counts[result.queue_name] += 1

    async def get_result(self, task_id: str) -> Optional[TaskResult]:
        return self._results.get(task_id)

    # ── dedup ───────────────────────────────────────────────────────────

    async def is_duplicate(self, queue_name: str, dedup_key: str) -> bool:
        self._ensure(queue_name)
        if queue_name not in self._dedup:
            self._dedup[queue_name] = set()
        s = self._dedup[queue_name]
        if dedup_key in s:
            return True
        s.add(dedup_key)
        return False

    async def clear_dedup(self, queue_name: str, dedup_key: str) -> None:
        if queue_name in self._dedup:
            self._dedup[queue_name].discard(dedup_key)

    # ── stats ───────────────────────────────────────────────────────────

    async def queue_size(self, name: str) -> int:
        self._ensure(name)
        return len(self._queues[name])

    async def queue_stats(self, name: str) -> QueueStats:
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
        task_registry: Optional[Dict[str, Any]] = None,
    ):
        self.url = url
        self.prefix = prefix
        self._registry = task_registry or {}
        self._redis: Any = None

    def register(self, name: str, func) -> None:
        self._registry[name] = func

    async def _r(self):
        if self._redis is not None:
            return self._redis
        try:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(
                self.url,
                decode_responses=True,
                socket_timeout=DEFAULT_REDIS_TIMEOUT,
            )
            await self._redis.ping()
        except ImportError:
            raise ImportError("redis is required. Install: pip install redis")
        except Exception as e:
            raise BackendUnavailable(f"Redis unavailable: {e}")
        return self._redis

    # ── enqueue / dequeue ───────────────────────────────────────────────

    async def enqueue(self, task: Task) -> None:
        r = await self._r()
        key = f"{self.prefix}q:{task.queue_name}"
        score = -task.priority.value * 1e12 + task.created_at
        payload = task.serialize()
        await r.zadd(key, {payload: score})

    async def dequeue(
        self, queue_name: str, timeout: Optional[float] = None
    ) -> Optional[Task]:
        r = await self._r()
        key = f"{self.prefix}q:{queue_name}"
        effective_timeout = timeout or 0
        try:
            result = await asyncio.wait_for(
                r.bzpopmax(key, timeout=effective_timeout),
                timeout=effective_timeout + 1,
            )
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            logger.error(f"Redis dequeue error: {e}")
            raise BackendUnavailable(f"Redis error: {e}")

        if result is None:
            return None

        _, payload = result
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
        r = await self._r()
        key = f"{self.prefix}result:{result.task_id}"
        await r.set(key, result.to_json(), ex=REDIS_RESULT_TTL)

    async def get_result(self, task_id: str) -> Optional[TaskResult]:
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
        r = await self._r()
        key = f"{self.prefix}dedup:{queue_name}:{dedup_key}"
        return bool(await r.exists(key))

    async def clear_dedup(self, queue_name: str, dedup_key: str) -> None:
        r = await self._r()
        await r.delete(f"{self.prefix}dedup:{queue_name}:{dedup_key}")

    # ── stats ───────────────────────────────────────────────────────────

    async def queue_size(self, name: str) -> int:
        r = await self._r()
        return await r.zcard(f"{self.prefix}q:{name}")

    async def queue_stats(self, name: str) -> QueueStats:
        r = await self._r()
        size = await r.zcard(f"{self.prefix}q:{name}")
        completed = int(await r.get(f"{self.prefix}stats:{name}:completed") or 0)
        failed = int(await r.get(f"{self.prefix}stats:{name}:failed") or 0)
        return QueueStats(name=name, size=size, completed=completed, failed=failed)

    # ── misc ────────────────────────────────────────────────────────────

    async def flush(self, queue_name: str) -> None:
        r = await self._r()
        await r.delete(f"{self.prefix}q:{queue_name}")

    async def ping(self) -> bool:
        try:
            r = await self._r()
            return await r.ping()
        except Exception:
            return False
