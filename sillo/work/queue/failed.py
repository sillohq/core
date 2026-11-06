"""
sillo.work.queue.failed — Failed job persistence and inspection.

When a job exhausts all retry attempts, it is logged to a failed-job
repository.  Implementations can store failures in memory (development)
or in a database (production).
"""

from __future__ import annotations

import dataclasses
import json
import time
import uuid
from abc import ABC, abstractmethod
from typing import Annotated, Any

from typing_extensions import Doc


@dataclasses.dataclass
class FailedJob:
    """Record of a permanently failed job."""

    id: str
    queue: str
    job_class: str
    payload: str
    exception: str
    failed_at: float = dataclasses.field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """To Dict"""
        return dataclasses.asdict(self)


class FailedJobRepository(ABC):
    """Abstract interface for persisting failed jobs."""

    @abstractmethod
    async def log(
        self,
        queue: Annotated[str, Doc("Queue name.")],
        job_id: Annotated[str, Doc("Job ID that failed.")],
        job_class: Annotated[str, Doc("Job class name.")],
        payload: Annotated[str, Doc("Serialised job payload.")],
        exception: Annotated[str, Doc("Traceback string.")],
    ) -> None:
        """Persist a failed job record."""
        ...  # pragma: no cover - abstract method

    @abstractmethod
    async def all(
        self,
        limit: Annotated[int, Doc("Max records to return.")] = 50,
        offset: Annotated[int, Doc("Skip this many.")] = 0,
    ) -> list[FailedJob]:
        """List all failed jobs, newest first."""
        ...  # pragma: no cover - abstract method

    @abstractmethod
    async def find(
        self, job_id: Annotated[str, Doc("Job ID to look up.")]
    ) -> FailedJob | None:
        """Find a specific failed job by ID."""
        ...  # pragma: no cover - abstract method

    @abstractmethod
    async def forget(self, job_id: Annotated[str, Doc("Job ID to remove.")]) -> bool:
        """Remove a failed job record. Returns True if found."""
        ...  # pragma: no cover - abstract method

    @abstractmethod
    async def flush(self) -> None:
        """Remove all failed job records."""
        ...  # pragma: no cover - abstract method


class MemoryFailedRepository(FailedJobRepository):
    """In-memory failed job repository — for development."""

    def __init__(
        self,
        max_failures: Annotated[int, Doc("Maximum failed jobs to retain.")] = 1000,
    ):
        """Init"""
        if max_failures < 1:
            raise ValueError("max_failures must be at least 1")
        self.max_failures = max_failures
        self._failed: list[FailedJob] = []

    async def log(
        self, queue: str, job_id: str, job_class: str, payload: str, exception: str
    ) -> None:
        """Log"""
        self._failed.append(
            FailedJob(
                id=job_id,
                queue=queue,
                job_class=job_class,
                payload=payload,
                exception=exception,
            )
        )
        if len(self._failed) > self.max_failures:
            self._failed.pop(0)

    async def all(self, limit: int = 50, offset: int = 0) -> list[FailedJob]:
        """All"""
        return list(reversed(self._failed))[offset : offset + limit]

    async def find(self, job_id: str) -> FailedJob | None:
        """Find"""
        for fj in self._failed:
            if fj.id == job_id:
                return fj
        return None

    async def forget(self, job_id: str) -> bool:
        """Forget"""
        before = len(self._failed)
        self._failed = [fj for fj in self._failed if fj.id != job_id]
        return len(self._failed) < before

    async def flush(self) -> None:
        """Flush"""
        self._failed.clear()


class RedisFailedRepository(FailedJobRepository):
    """Failed jobs stored alongside a Redis queue, shared across processes."""

    def __init__(
        self,
        url: str = "redis://localhost:6379",
        *,
        prefix: str = "sillo:queue:",
        connection: Any = None,
    ):
        from .connection import RedisConnection

        self.connection = connection or RedisConnection(url=url, prefix=prefix)
        self.records = f"{self.connection.prefix}failed:records"
        self.index = f"{self.connection.prefix}failed:index"

    async def log(
        self, queue: str, job_id: str, job_class: str, payload: str, exception: str
    ) -> None:
        job = FailedJob(job_id, queue, job_class, payload, exception)
        r = await self.connection._r()
        async with r.pipeline(transaction=True) as pipe:
            pipe.hset(self.records, job_id, json.dumps(job.to_dict()))
            pipe.zadd(self.index, {job_id: job.failed_at})
            await pipe.execute()

    async def all(self, limit: int = 50, offset: int = 0) -> list[FailedJob]:
        if limit <= 0:
            return []
        r = await self.connection._r()
        ids = await r.zrevrange(self.index, offset, offset + limit - 1)
        values = await r.hmget(self.records, ids) if ids else []
        return [FailedJob(**json.loads(value)) for value in values if value is not None]

    async def find(self, job_id: str) -> FailedJob | None:
        r = await self.connection._r()
        value = await r.hget(self.records, job_id)
        return FailedJob(**json.loads(value)) if value is not None else None

    async def forget(self, job_id: str) -> bool:
        r = await self.connection._r()
        async with r.pipeline(transaction=True) as pipe:
            pipe.hdel(self.records, job_id)
            pipe.zrem(self.index, job_id)
            result = await pipe.execute()
        return bool(result[0])

    async def flush(self) -> None:
        r = await self.connection._r()
        await r.delete(self.records, self.index)

    async def fail_claim(
        self,
        conn: Any,
        queue: str,
        job_id: str,
        job_class: str,
        payload: str,
        exception: str,
    ) -> bool:
        """Atomically persist a failure and settle its Redis claim."""
        job = FailedJob(job_id, queue, job_class, payload, exception)
        _, _, processing, claims = conn._keys(queue)
        r = await conn._r()
        return bool(
            await r.eval(
                _FAIL_CLAIM,
                4,
                processing,
                claims,
                self.records,
                self.index,
                job_id,
                json.dumps(job.to_dict()),
                job.failed_at,
            )
        )

    async def retry(self, job_id: str) -> str | None:
        """Atomically requeue a failure once, resetting its attempt count."""
        r = await self.connection._r()
        raw = await r.hget(self.records, job_id)
        if raw is None:
            return None
        job = FailedJob(**json.loads(raw))
        payload = json.loads(job.payload)
        payload.pop("attempts", None)
        payload.pop("_job_id", None)
        new_id = uuid.uuid4().hex
        ready = self.connection._keys(job.queue)[0]
        result = await r.eval(
            _RETRY,
            3,
            self.records,
            self.index,
            ready,
            job_id,
            raw,
            f"{new_id}:{json.dumps(payload)}",
        )
        return new_id if result else None


_FAIL_CLAIM = """
local held = redis.call('LRANGE', KEYS[1], 0, -1)
local prefix = ARGV[1] .. ':'
for _, raw in ipairs(held) do
    if string.sub(raw, 1, string.len(prefix)) == prefix then
        -- Check destination types before writing: Redis scripts do not roll back.
        local ht = redis.call('TYPE', KEYS[3]).ok
        local zt = redis.call('TYPE', KEYS[4]).ok
        local ct = redis.call('TYPE', KEYS[2]).ok
        if (ht ~= 'none' and ht ~= 'hash') or (zt ~= 'none' and zt ~= 'zset') or (ct ~= 'none' and ct ~= 'zset') then
            return redis.error_reply('invalid failed job storage type')
        end
        redis.call('HSET', KEYS[3], ARGV[1], ARGV[2])
        redis.call('ZADD', KEYS[4], ARGV[3], ARGV[1])
        redis.call('LREM', KEYS[1], 1, raw)
        redis.call('ZREM', KEYS[2], raw)
        return 1
    end
end
return 0
"""

_RETRY = """
if redis.call('HGET', KEYS[1], ARGV[1]) ~= ARGV[2] then return 0 end
local zt = redis.call('TYPE', KEYS[2]).ok
local lt = redis.call('TYPE', KEYS[3]).ok
if (zt ~= 'none' and zt ~= 'zset') or (lt ~= 'none' and lt ~= 'list') then
    return redis.error_reply('invalid queue or failed job storage type')
end
redis.call('LPUSH', KEYS[3], ARGV[3])
redis.call('HDEL', KEYS[1], ARGV[1])
redis.call('ZREM', KEYS[2], ARGV[1])
return 1
"""
