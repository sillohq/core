"""sillo.cache.backends — Concrete cache backends.

Provides:

* :class:`MemoryCache` — a dependency-free, in-process backend with absolute
  and sliding TTL, LRU eviction, max-size eviction, tag-based invalidation,
  and per-key versioning.
* :class:`RedisCache` — an async Redis backend (uses ``redis.asyncio``,
  imported lazily so the ``cache`` extra is optional). It mirrors the memory
  backend's feature set using Redis primitives (TTL, sets for tags, key
  prefixes for namespaces/versions).
"""

from __future__ import annotations

import collections
import time
import typing
from typing import Any, Dict, Iterable, List, Optional

from .base import (
    BaseCache,
    CacheError,
    CacheStats,
    SerializationError,
    _MISSING,
    deserialize,
    serialize,
    tag_key,
)

if typing.TYPE_CHECKING:
    pass


class MemoryCache(BaseCache):
    """In-process, thread-safe cache backend.

    Features:
        * **Absolute TTL** — ``ttl`` seconds from write time.
        * **Sliding TTL** — refreshed on every read within ``ttl`` window.
        * **LRU eviction** — least-recently-used entry dropped when full.
        * **Max-size eviction** — oldest/size overflow trimmed to ``max_size``.
        * **Tag invalidation** — ``invalidate_tags("users")`` drops all keys
          written with that tag.
        * **Versioning** — bump ``version`` to expire a whole namespace at once.

    Example:
        ```python
        cache = MemoryCache(namespace="users", default_ttl=300, max_size=1024)
        await cache.set("u:1", user, tags=["user:1"])
        user = await cache.get("u:1")
        await cache.invalidate_tags("user:1")
        ```
    """

    name = "memory"

    def __init__(
        self,
        *,
        namespace: Optional[str] = None,
        default_ttl: Optional[int] = None,
        serializer: str = "json",
        max_size: Optional[int] = None,
        stats: Optional[CacheStats] = None,
    ) -> None:
        super().__init__(
            namespace=namespace,
            default_ttl=default_ttl,
            serializer=serializer,
            stats=stats,
        )
        self.max_size = max_size
        # OrderedDict doubles as the LRU: most-recently-used at the end.
        self._store: "collections.OrderedDict[str, _Entry]" = collections.OrderedDict()
        self._tags: Dict[str, set] = {}

    # ---- internal entry type ---------------------------------------

    class _Entry:
        __slots__ = ("payload", "expire_at", "sliding", "ttl")

        def __init__(
            self,
            payload: bytes,
            ttl: Optional[int],
            sliding: bool,
            now: float,
        ) -> None:
            self.payload = payload
            self.ttl = ttl
            self.sliding = sliding
            self.expire_at = (now + ttl) if ttl is not None else None

        def is_expired(self, now: float) -> bool:
            return self.expire_at is not None and now >= self.expire_at

        def touch(self, ttl: Optional[int], now: float) -> None:
            if ttl is not None:
                self.ttl = ttl
            if self.ttl is not None:
                self.expire_at = now + self.ttl

    # ---- get / set / delete ----------------------------------------

    async def get(self, key: str) -> Any:
        with self._lock:
            entry = self._store.get(key)
            now = time.monotonic()
            if entry is None:
                self._stats.misses += 1
                return _MISSING
            if entry.is_expired(now):
                self._store.pop(key, None)
                self._stats.misses += 1
                return _MISSING
            # LRU: move to end (most-recently used).
            self._store.move_to_end(key)
            if entry.sliding and entry.ttl is not None:
                entry.expire_at = now + entry.ttl
            self._stats.hits += 1
            try:
                return deserialize(entry.payload)
            except SerializationError:
                # Corrupt entry: treat as miss and evict.
                self._store.pop(key, None)
                self._stats.misses += 1
                return _MISSING

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        *,
        tags: Optional[Iterable[str]] = None,
        sliding: bool = False,
    ) -> None:
        ttl = self._resolve_ttl(ttl)
        try:
            payload = serialize(value, self.serializer == "pickle")
        except SerializationError:
            raise
        with self._lock:
            now = time.monotonic()
            entry = self._Entry(payload, ttl, sliding, now)
            self._store[key] = entry
            self._store.move_to_end(key)
            self._stats.sets += 1
            if tags:
                for tag in tags:
                    tk = tag_key(self.namespace, tag)
                    self._tags.setdefault(tk, set()).add(key)
            self._enforce_size()

    async def delete(self, key: str) -> bool:
        with self._lock:
            entry = self._store.pop(key, None)
            if entry is None:
                return False
            self._stats.deletes += 1
            return True

    async def exists(self, key: str) -> bool:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return False
            if entry.is_expired(time.monotonic()):
                self._store.pop(key, None)
                return False
            return True

    async def touch(self, key: str, ttl: Optional[int] = None) -> bool:
        with self._lock:
            entry = self._store.get(key)
            if entry is None or entry.is_expired(time.monotonic()):
                return False
            entry.touch(ttl if ttl is not None else self.default_ttl, time.monotonic())
            self._store.move_to_end(key)
            return True

    async def invalidate_tags(self, *tags: str) -> int:
        if not tags:
            return 0
        removed = 0
        with self._lock:
            for tag in tags:
                tk = tag_key(self.namespace, tag)
                keys = self._tags.pop(tk, set())
                for k in keys:
                    if self._store.pop(k, None) is not None:
                        removed += 1
            if removed:
                self._stats.deletes += removed
        return removed

    async def clear(self) -> None:
        with self._lock:
            if self.namespace:
                # Only drop keys belonging to this namespace.
                for k in list(self._store.keys()):
                    if k.startswith(f"{self.namespace}:"):
                        self._store.pop(k, None)
                for tk in list(self._tags.keys()):
                    if tk.startswith(f"tag:{self.namespace}:"):
                        self._tags.pop(tk, None)
            else:
                self._store.clear()
                self._tags.clear()

    async def close(self) -> None:
        with self._lock:
            self._store.clear()
            self._tags.clear()

    # ---- size management -------------------------------------------

    def _enforce_size(self) -> None:
        if self.max_size is None:
            return
        while len(self._store) > self.max_size:
            # Pop the oldest (LRU) item.
            _, evicted = self._store.popitem(last=False)
            self._stats.evictions += 1

    # ---- size/len helpers ------------------------------------------

    def __len__(self) -> int:
        return len(self._store)

    def size(self) -> int:
        return len(self._store)


class RedisCache(BaseCache):
    """Async Redis cache backend.

    Requires the optional ``redis`` package (``pip install sillo[cache]``).
    The import is lazy so importing :mod:`sillo.cache` never fails without it.

    Redis mapping:
        * Keys are stored verbatim (already namespaced/versioned by
          :meth:`BaseCache.make_key`).
        * TTL is handled natively via ``SETEX`` / ``PEXPIRE``.
        * Tags map to Redis sets (``tag:<ns>:<tag>``) of member keys.
        * Sliding TTL is emulated by re-issuing ``EXPIRE`` on every read.

    Example:
        ```python
        cache = RedisCache(url="redis://localhost:6379/0", default_ttl=300)
        await cache.set("k", value, tags=["t1"])
        value = await cache.get("k")
        await cache.invalidate_tags("t1")
        ```
    """

    name = "redis"

    def __init__(
        self,
        *,
        url: Optional[str] = None,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        namespace: Optional[str] = None,
        default_ttl: Optional[int] = None,
        serializer: str = "json",
        client: Any = None,
        stats: Optional[CacheStats] = None,
    ) -> None:
        super().__init__(
            namespace=namespace,
            default_ttl=default_ttl,
            serializer=serializer,
            stats=stats,
        )
        self._url = url
        self._host = host
        self._port = port
        self._db = db
        self._password = password
        self._client = client
        self._owns_client = client is None

    # ---- lazy connection -------------------------------------------

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            import redis.asyncio as aioredis
        except ImportError as exc:  # pragma: no cover
            raise CacheError(
                "The 'redis' package is required for RedisCache. "
                "Install it with: pip install sillo[cache]"
            ) from exc
        if self._url:
            self._client = aioredis.from_url(
                self._url,
                db=self._db,
                password=self._password,
                decode_responses=False,
            )
        else:
            self._client = aioredis.Redis(
                host=self._host,
                port=self._port,
                db=self._db,
                password=self._password,
                decode_responses=False,
            )
        return self._client

    async def _redis(self):
        return self._get_client()

    # ---- get / set / delete ----------------------------------------

    async def get(self, key: str) -> Any:
        client = await self._redis()
        payload = await client.get(key)
        if payload is None:
            self._stats.misses += 1
            return _MISSING
        # Sliding TTL: refresh expiry on read.
        entry_ttl = await client.ttl(key)
        if entry_ttl is not None and entry_ttl > 0:
            ttl = self._resolve_ttl(self.default_ttl)
            if ttl is not None:
                await client.expire(key, ttl)
        try:
            value = deserialize(payload)
        except SerializationError:
            self._stats.misses += 1
            return _MISSING
        self._stats.hits += 1
        return value

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        *,
        tags: Optional[Iterable[str]] = None,
        sliding: bool = False,
    ) -> None:
        ttl = self._resolve_ttl(ttl)
        try:
            payload = serialize(value, self.serializer == "pickle")
        except SerializationError:
            raise
        client = await self._redis()
        if ttl is not None:
            await client.set(key, payload, ex=ttl)
        else:
            await client.set(key, payload)
        self._stats.sets += 1
        if tags:
            for tag in tags:
                tk = tag_key(self.namespace, tag)
                await client.sadd(tk, key)
                # Tags themselves expire with the longest reasonable window so
                # orphaned sets don't accumulate forever.
                await client.expire(tk, 60 * 60 * 24)

    async def delete(self, key: str) -> bool:
        client = await self._redis()
        removed = await client.delete(key)
        if removed:
            self._stats.deletes += 1
        return bool(removed)

    async def exists(self, key: str) -> bool:
        client = await self._redis()
        return bool(await client.exists(key))

    async def touch(self, key: str, ttl: Optional[int] = None) -> bool:
        client = await self._redis()
        ttl = ttl if ttl is not None else self.default_ttl
        if ttl is None:
            return False
        return bool(await client.expire(key, ttl))

    async def invalidate_tags(self, *tags: str) -> int:
        if not tags:
            return 0
        client = await self._redis()
        removed = 0
        for tag in tags:
            tk = tag_key(self.namespace, tag)
            keys = await client.smembers(tk)
            if keys:
                removed += await client.delete(*keys)
                await client.delete(tk)
        if removed:
            self._stats.deletes += removed
        return removed

    async def clear(self) -> None:
        client = await self._redis()
        if self.namespace:
            async for key in client.scan_iter(match=f"{self.namespace}:*"):
                await client.delete(key)
            async for key in client.scan_iter(match=f"tag:{self.namespace}:*"):
                await client.delete(key)
        else:
            await client.flushdb()

    async def close(self) -> None:
        if self._client is not None and self._owns_client:
            try:
                await self._client.aclose()
            except Exception:  # pragma: no cover
                pass


__all__ = ["MemoryCache", "RedisCache"]
