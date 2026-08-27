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
from collections.abc import Iterable
from typing import Any

from .base import (
    _MISSING,
    BaseCache,
    CacheError,
    CacheStats,
    deserialize,
    serialize,
    tag_key,
)

try:
    import redis.asyncio as aioredis  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - exercised only without redis installed
    aioredis = None  # ty: ignore[invalid-assignment]


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

    This backend stores all data in an :class:`~collections.OrderedDict`
    protected by a reentrant lock, making it safe for concurrent async access
    within a single process. It requires no external dependencies and is the
    default backend when no other is configured.

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
        namespace: str | None = None,
        default_ttl: int | None = None,
        serializer: str = "json",
        max_size: int | None = None,
        stats: CacheStats | None = None,
    ) -> None:
        """Initialize the in-memory cache backend with storage configuration.

        Sets up the internal ordered dictionary for LRU tracking, the tag
        membership mapping, and delegates common configuration to the base
        class constructor. The max_size parameter enables automatic eviction
        of the least-recently-used entries when the store exceeds capacity.

        Args:
            namespace: Optional prefix for isolating cache keys into logical
                groups. Affects key generation and namespace-scoped clear.
            default_ttl: Default time-to-live in seconds applied to entries
                when no explicit TTL is provided at write time.
            serializer: Serialization format, either ``"json"`` or ``"pickle"``,
                controlling how values are encoded for storage.
            max_size: Maximum number of entries allowed in the store. When
                ``None``, the store grows without bound. When set, LRU
                eviction removes the oldest entry to stay within the limit.
            stats: Optional shared :class:`CacheStats` instance for tracking
                cache operation counters across multiple backend references.
        """
        super().__init__(
            namespace=namespace,
            default_ttl=default_ttl,
            serializer=serializer,
            stats=stats,
        )
        self.max_size = max_size
        # OrderedDict doubles as the LRU: most-recently-used at the end.
        # Quoted: _Entry is a nested class defined below this method, so the
        # annotation cannot be evaluated at runtime.
        self._store: collections.OrderedDict[str, MemoryCache._Entry] = (
            collections.OrderedDict()
        )
        self._tags: dict[str, set] = {}

    # ---- internal entry type ---------------------------------------

    class _Entry:
        """Internal cache entry storing a serialized payload and expiry metadata.

        Each entry tracks its raw byte payload, the TTL it was written with,
        whether it uses sliding expiration, and the absolute expiration time
        computed from the write timestamp. Uses ``__slots__`` for memory
        efficiency since many entries may exist simultaneously.

        Attributes:
            payload: The serialized byte representation of the cached value.
            expire_at: Absolute monotonic time when the entry expires, or
                ``None`` if the entry has no TTL and persists indefinitely.
            sliding: Whether this entry uses sliding TTL expiration mode.
            ttl: The TTL in seconds that was configured for this entry.
        """

        __slots__ = ("expire_at", "payload", "sliding", "ttl")

        def __init__(
            self,
            payload: bytes,
            ttl: int | None,
            sliding: bool,
            now: float,
        ) -> None:
            """Initialize a cache entry with payload and expiration metadata.

            Constructs a new entry by storing the serialized payload and
            computing the absolute expiration time from the current monotonic
            timestamp and the provided TTL value.

            Args:
                payload: The serialized byte data representing the cached value.
                ttl: Time-to-live in seconds, or ``None`` for no expiration.
                sliding: Whether this entry should use sliding TTL mode where
                    the expiration window refreshes on each read access.
                now: The current monotonic time used as the base for computing
                    the absolute expiration timestamp.
            """
            self.payload = payload
            self.ttl = ttl
            self.sliding = sliding
            self.expire_at = (now + ttl) if ttl is not None else None

        def is_expired(self, now: float) -> bool:
            """Check whether this cache entry has expired.

            Compares the provided current time against the entry's absolute
            expiration timestamp. Entries with no expiration (``expire_at``
            is ``None``) are never considered expired.

            Args:
                now: The current monotonic time to compare against the
                    entry's expiration deadline.

            Returns:
                ``True`` if the entry has an expiration time and the current
                time has reached or exceeded it, ``False`` otherwise.
            """
            return self.expire_at is not None and now >= self.expire_at

        def touch(self, ttl: int | None, now: float) -> None:
            """Refresh the entry's expiration time with a new TTL.

            Updates the entry's TTL if a new value is provided, then
            recomputes the absolute expiration timestamp from the given
            current time. This is used to implement sliding expiration
            where each access extends the entry's lifetime.

            Args:
                ttl: New TTL in seconds to apply. When ``None``, the
                    entry's existing TTL value is retained for the
                    expiration recomputation.
                now: The current monotonic time used as the base for
                    computing the new absolute expiration timestamp.
            """
            if ttl is not None:
                self.ttl = ttl
            if self.ttl is not None:
                self.expire_at = now + self.ttl

    # ---- get / set / delete ----------------------------------------

    async def get(self, key: str) -> Any:
        """Retrieve a cached value from the in-memory store.

        Looks up the key in the internal ordered dictionary, checks for
        expiration, and deserializes the stored payload on a hit. Expired
        entries are evicted as a side effect. On a successful read with
        sliding TTL enabled, the entry's expiration time is refreshed.
        The entry is moved to the end of the ordered dict to mark it as
        most-recently used for LRU eviction purposes.

        Args:
            key: The cache key to look up in the in-memory store.

        Returns:
            The deserialized cached value on a hit, or the :data:`_MISSING`
            sentinel object if the key is absent, expired, or corrupt.
        """
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._stats.misses += 1
                return _MISSING

            now = time.monotonic()
            if entry.is_expired(now):
                del self._store[key]
                self._stats.misses += 1
                return _MISSING

            self._store.move_to_end(key)

            if entry.sliding:
                entry.touch(None, now)

            self._stats.hits += 1
            return deserialize(entry.payload)

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
        *,
        tags: Iterable[str] | None = None,
        sliding: bool = False,
    ) -> None:
        """Store a value in the in-memory cache under the given key.

        Serializes the value, creates a new cache entry with the resolved
        TTL, and inserts it into the ordered dictionary. If tags are
        provided, the key is registered in each tag's membership set for
        later bulk invalidation. After insertion, the max-size constraint
        is enforced by evicting the least-recently-used entries if needed.

        Args:
            key: The cache key to store the value under.
            value: The Python object to serialize and cache in memory.
            ttl: Optional time-to-live in seconds. Falls back to the
                backend's ``default_ttl`` when ``None``.
            tags: Optional iterable of invalidation tag strings for
                group-based cache purging via :meth:`invalidate_tags`.
            sliding: When ``True``, the TTL window refreshes on every
                :meth:`get` call, implementing sliding expiration.

        Raises:
            SerializationError: If the value cannot be serialized by the
                configured serializer.
        """
        resolved_ttl = self._resolve_ttl(ttl)
        now = time.monotonic()
        payload = serialize(value, use_pickle=(self.serializer == "pickle"))
        entry = self._Entry(payload, resolved_ttl, sliding, now)

        with self._lock:
            self._store[key] = entry
            self._store.move_to_end(key)

            if tags:
                for tag in tags:
                    tkey = tag_key(self.namespace, tag)
                    if tkey not in self._tags:
                        self._tags[tkey] = set()
                    self._tags[tkey].add(key)

            self._stats.sets += 1
            self._enforce_size()

    async def delete(self, key: str) -> bool:
        """Delete a key from the in-memory cache store.

        Removes the entry associated with the given key from the internal
        ordered dictionary and increments the delete statistics counter.
        Note that tag membership sets are not cleaned up here; tag-based
        invalidation handles that separately.

        Args:
            key: The cache key to remove from the in-memory store.

        Returns:
            ``True`` if the key existed and was removed, ``False`` if
            the key was not found in the store.
        """
        with self._lock:
            if key in self._store:
                del self._store[key]
                self._stats.deletes += 1
                return True
            return False

    async def exists(self, key: str) -> bool:
        """Check if a key exists and is unexpired in the in-memory store.

        Performs a presence check without deserializing the stored value,
        making this a lightweight operation. Expired entries are evicted
        as a side effect and treated as absent.

        Args:
            key: The cache key to check for existence in the store.

        Returns:
            ``True`` if the key is present and has not expired, ``False``
            if the key is missing or its TTL has elapsed.
        """
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return False

            now = time.monotonic()
            if entry.is_expired(now):
                del self._store[key]
                return False

            self._store.move_to_end(key)
            return True

    async def touch(self, key: str, ttl: int | None = None) -> bool:
        """Refresh the TTL of an entry in the in-memory store.

        Extends the lifetime of a cached key by recomputing its expiration
        time. The entry is also moved to the end of the ordered dictionary
        to mark it as most-recently used for LRU eviction purposes.

        Args:
            key: The cache key whose TTL should be refreshed.
            ttl: Optional new TTL in seconds. When ``None``, the backend's
                ``default_ttl`` is used as the new expiration window.

        Returns:
            ``True`` if the key existed and was refreshed, ``False`` if
            the key was not found or had already expired.
        """
        resolved_ttl = self._resolve_ttl(ttl)
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return False

            now = time.monotonic()
            if entry.is_expired(now):
                del self._store[key]
                return False

            entry.touch(resolved_ttl, now)
            self._store.move_to_end(key)
            return True

    async def invalidate_tags(self, *tags: str) -> int:
        """Delete all in-memory entries associated with the given tags.

        Iterates over each provided tag, looks up its membership set, and
        removes every associated key from the internal store. The tag
        membership sets themselves are also removed. This provides efficient
        group-based cache purging without knowing individual key names.

        Args:
            *tags: One or more invalidation tag strings. Every in-memory
                key registered with any of these tags will be deleted.

        Returns:
            The total number of keys that were deleted as a result of
            this tag invalidation operation.
        """
        if not tags:
            return 0

        removed = 0
        with self._lock:
            for tag in tags:
                tkey = tag_key(self.namespace, tag)
                members = self._tags.pop(tkey, set())
                for member_key in members:
                    if member_key in self._store:
                        del self._store[member_key]
                        removed += 1
            if removed:
                self._stats.deletes += removed
        return removed

    async def clear(self) -> None:
        """Remove all keys from the in-memory cache, respecting namespace.

        When a namespace is configured, only keys and tags belonging to
        that namespace are removed from the internal store. When no
        namespace is set, the entire store and tag mapping are cleared
        unconditionally.

        Note:
            This operation does not reset statistics counters; use
            :meth:`reset_stats` for that purpose.
        """
        with self._lock:
            if self.namespace:
                prefix = f"{self.namespace}:"
                to_remove = [k for k in self._store if k.startswith(prefix)]
                for k in to_remove:
                    del self._store[k]
                tag_prefix = f"tag:{self.namespace}:"
                self._tags = {
                    k: v for k, v in self._tags.items() if not k.startswith(tag_prefix)
                }
            else:
                self._store.clear()
                self._tags.clear()

    async def close(self) -> None:
        """Release all in-memory cache resources.

        Clears the internal ordered dictionary and tag membership mapping,
        effectively discarding all cached data. After calling this method,
        the backend instance should not be used for further operations.
        """
        with self._lock:
            self._store.clear()
            self._tags.clear()

    # ---- size management -------------------------------------------

    def _enforce_size(self) -> None:
        """Enforce the maximum store size by evicting least-recently-used entries.

        Removes the oldest entries from the ordered dictionary (those at the
        front, i.e. least-recently used) until the store size is within the
        configured ``max_size`` limit. Each eviction increments the eviction
        statistics counter. Does nothing when ``max_size`` is ``None``.

        Note:
            This method is called automatically after every :meth:`set`
            operation and should not typically need to be called directly.
        """
        if self.max_size is None:
            return
        while len(self._store) > self.max_size:
            self._store.popitem(last=False)
            self._stats.evictions += 1

    def __len__(self) -> int:
        """Return the number of entries currently in the in-memory store.

        Includes both expired and unexpired entries since expiration is
        checked lazily on access. The count reflects the raw size of the
        internal ordered dictionary.

        Returns:
            The total number of entries in the store as an integer,
            including any that may have expired but not yet been evicted.
        """
        return len(self._store)

    def size(self) -> int:
        """Return the number of entries currently in the in-memory store.

        Provides an explicit method alternative to ``len(cache)`` for
        obtaining the current store size. Includes both expired and
        unexpired entries since expiration is checked lazily on access.

        Returns:
            The total number of entries in the store as an integer,
            including any that may have expired but not yet been evicted.
        """
        return len(self._store)


class RedisCache(BaseCache):
    """Async Redis cache backend.

    Requires the optional ``redis`` package (``uv add "sillo[cache]"``).
    The import is lazy so importing :mod:`sillo.cache` never fails without it.

    Redis mapping:
        * Keys are stored verbatim (already namespaced/versioned by
          :meth:`BaseCache.make_key`).
        * TTL is handled natively via ``SETEX`` / ``PEXPIRE``.
        * Tags map to Redis sets (``tag:<ns>:<tag>``) of member keys.
        * Sliding TTL is emulated by re-issuing ``EXPIRE`` on every read.

    The backend lazily establishes its Redis connection on the first
    operation, either from an explicit URL or from individual host/port/db
    parameters. An externally-managed client can also be injected via the
    ``client`` parameter, in which case the backend will not close it.

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
        url: str | None = None,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: str | None = None,
        namespace: str | None = None,
        default_ttl: int | None = None,
        serializer: str = "json",
        client: Any = None,
        stats: CacheStats | None = None,
    ) -> None:
        """Initialize the Redis cache backend with connection parameters.

        Configures the Redis connection settings and delegates common
        backend configuration to the base class. The connection is
        established lazily on the first cache operation. Either a full
        Redis URL or individual host/port/db parameters can be provided.
        An externally-managed client can also be injected directly.

        Args:
            url: Optional full Redis connection URL (e.g.
                ``redis://localhost:6379/0``). Takes precedence over
                individual host/port/db parameters when provided.
            host: Redis server hostname. Defaults to ``"localhost"``.
                Ignored when ``url`` is provided.
            port: Redis server port number. Defaults to ``6379``.
                Ignored when ``url`` is provided.
            db: Redis database index. Defaults to ``0``.
                Ignored when ``url`` is provided.
            password: Optional Redis authentication password. Ignored
                when ``url`` is provided and the URL contains no password.
            namespace: Optional prefix for isolating cache keys into
                logical groups within the Redis instance.
            default_ttl: Default time-to-live in seconds for entries
                when no explicit TTL is provided at write time.
            serializer: Serialization format, either ``"json"`` or
                ``"pickle"``, for encoding values before storage.
            client: Optional pre-existing async Redis client instance.
                When provided, the backend uses it directly and will
                not close it on :meth:`close`.
            stats: Optional shared :class:`CacheStats` instance for
                tracking cache operation counters.
        """
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

    async def _redis(self):
        """Return the async Redis client, ensuring the connection is active.

        This is the async entry point for obtaining the Redis client. It
        delegates to :meth:`_get_client` for lazy connection establishment
        and returns the client ready for command execution.

        Returns:
            The async Redis client instance for executing Redis commands.
        """
        if self._client is not None:
            return self._client
        if aioredis is None:
            raise CacheError(
                "The 'redis' package is required for RedisCache. "
                'Install it with: uv add "sillo[cache]"'
            )
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

    # ---- get / set / delete ----------------------------------------

    async def get(self, key: str) -> Any:
        """Retrieve a cached value from the Redis backend.

        Fetches the raw byte payload from Redis using the ``GET`` command,
        deserializes it, and returns the resulting Python object. When
        sliding TTL is in effect, the entry's expiration is refreshed by
        re-issuing the ``EXPIRE`` command with the backend's default TTL.

        Args:
            key: The cache key to look up in the Redis store.

        Returns:
            The deserialized cached value on a hit, or the :data:`_MISSING`
            sentinel object if the key is absent or the payload is corrupt.
        """
        redis = await self._redis()
        raw = await redis.get(key)
        if raw is None:
            self._stats.misses += 1
            return _MISSING

        value = deserialize(raw)
        now = time.monotonic()

        # Only a value written with sliding=True has its lifetime refreshed on
        # read, and only that value is wrapped.
        #
        # Refreshing unconditionally, as this used to, called touch(key, None)
        # for every ordinary read — and a None ttl resolves to default_ttl, so
        # reading a key written with an explicit `ttl=1` pushed its expiry out
        # to the backend default. An entry given one second lived sixty, and
        # nothing short-lived expired as asked as long as anything read it.
        #
        # Returning the wrapper was the other half: a sliding value came back
        # as {"_value": ..., "_sliding": True, ...} instead of what was stored.
        if isinstance(value, dict) and value.get("_sliding"):
            await self.touch(key, value.get("_ttl"), now)
            value = value.get("_value")

        self._stats.hits += 1
        return value

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
        *,
        tags: Iterable[str] | None = None,
        sliding: bool = False,
    ) -> None:
        """Store a value in the Redis cache under the given key.

        Serializes the value and writes it to Redis with an optional TTL
        using the ``SET`` command with the ``EX`` flag. When tags are
        provided, the key is added to each tag's Redis set via ``SADD``,
        and the tag set itself is given a 24-hour expiration to prevent
        orphaned sets from accumulating indefinitely.

        Args:
            key: The cache key to store the value under in Redis.
            value: The Python object to serialize and cache in Redis.
            ttl: Optional time-to-live in seconds. Falls back to the
                backend's ``default_ttl`` when ``None``.
            tags: Optional iterable of invalidation tag strings for
                group-based cache purging via :meth:`invalidate_tags`.
            sliding: When ``True``, the TTL window refreshes on every
                :meth:`get` call, implementing sliding expiration.

        Raises:
            SerializationError: If the value cannot be serialized by the
                configured serializer.
        """
        redis = await self._redis()
        resolved_ttl = self._resolve_ttl(ttl)
        payload = serialize(value, use_pickle=(self.serializer == "pickle"))

        # Handle sliding TTL by storing metadata
        if sliding:
            now = time.monotonic()
            redis_value = {
                "_value": value,
                "_sliding": True,
                "_ttl": resolved_ttl,
                "_expire_at": (now + resolved_ttl) if resolved_ttl else None,
            }
            payload = serialize(redis_value, use_pickle=(self.serializer == "pickle"))
        await redis.set(key, payload, ex=resolved_ttl)

        # Store tags
        if tags:
            self._stats.sets += 1
            for tag in tags:
                await redis.sadd(tag_key(self.namespace, tag), key)

        # Cleanup old tag sets (24 hour TTL)
        await redis.expire(tag_key(self.namespace, "__cleanup__"), 86400)

    async def delete(self, key: str) -> bool:
        """Delete a key from the Redis cache store.

        Issues a Redis ``DEL`` command for the given key and increments
        the delete statistics counter if the key was actually removed.

        Args:
            key: The cache key to remove from the Redis store.

        Returns:
            ``True`` if the key existed and was deleted, ``False`` if
            the key was not found in Redis.
        """
        redis = await self._redis()
        deleted = await redis.delete(key)
        if deleted:
            self._stats.deletes += 1
        return bool(deleted)

    async def exists(self, key: str) -> bool:
        """Check if a key exists in the Redis cache store.

        Issues a Redis ``EXISTS`` command to test for key presence. Note
        that Redis natively handles TTL expiration, so expired keys are
        automatically treated as absent by the server.

        Args:
            key: The cache key to check for existence in Redis.

        Returns:
            ``True`` if the key exists in Redis, ``False`` otherwise.
        """
        redis = await self._redis()
        return await redis.exists(key) > 0

    async def touch(
        self, key: str, ttl: int | None = None, now: float | None = None
    ) -> bool:
        """Refresh the TTL of a key in the Redis cache store.

        Issues a Redis ``EXPIRE`` command to reset the key's expiration
        time. Returns ``False`` immediately if no TTL can be resolved
        (neither explicit nor default).

        Args:
            key: The cache key whose TTL should be refreshed in Redis.
            ttl: Optional new TTL in seconds. When ``None``, the backend's
                ``default_ttl`` is used as the new expiration window.

        Returns:
            ``True`` if the key existed and its TTL was updated, ``False``
            if the key was not found or no TTL could be resolved.
        """
        if now is None:
            now = time.monotonic()

        resolved_ttl = self._resolve_ttl(ttl)
        if resolved_ttl:
            redis = await self._redis()
            return bool(await redis.expire(key, resolved_ttl))
        return False

    async def invalidate_tags(self, *tags: str) -> int:
        """Delete all Redis entries associated with the given tags.

        For each tag, retrieves the member keys from the tag's Redis set
        via ``SMEMBERS``, deletes all those keys in bulk, and then removes
        the tag set itself. This provides efficient group-based cache
        purging without knowing individual key names.

        Args:
            *tags: One or more invalidation tag strings. Every Redis key
                registered with any of these tags will be deleted.

        Returns:
            The total number of keys that were deleted as a result of
            this tag invalidation operation.
        """
        if not tags:
            return 0

        redis = await self._redis()
        deleted_total = 0
        for tag in tags:
            member_keys = await redis.smembers(tag_key(self.namespace, tag))
            if member_keys:
                await redis.delete(*member_keys)
                deleted_total += len(member_keys)
            # Cleanup the tag set
            await redis.delete(tag_key(self.namespace, tag))

        if deleted_total:
            self._stats.deletes += deleted_total
        return deleted_total

    async def clear(self) -> None:
        """Remove all keys from the Redis cache, respecting namespace.

        When a namespace is configured, uses ``SCAN`` with a pattern match
        to find and delete only keys belonging to that namespace, including
        tag sets. When no namespace is set, issues a ``FLUSHDB`` command
        to clear the entire Redis database.

        Warning:
            When no namespace is configured, this operation clears the
            entire Redis database, not just cache keys. Use namespaces
            to scope the impact of :meth:`clear`.
        """
        redis = await self._redis()
        if self.namespace:
            pattern = f"{self.namespace}:*"
            cursor = 0
            while True:
                cursor, keys = await redis.scan(cursor=cursor, match=pattern, count=100)
                if keys:
                    await redis.delete(*keys)
                if cursor == 0:
                    break
        else:
            await redis.flushdb()

    async def close(self) -> None:
        """Release the Redis connection if the backend owns the client.

        Closes the async Redis client connection only when the backend
        created it internally (i.e., no external client was injected).
        External clients are left open since their lifecycle is managed
        by the caller. Exceptions during close are silently caught to
        ensure graceful shutdown.
        """
        if self._owns_client and self._client:
            try:
                # aclose() since redis 5.0.1; close() still works but warns on
                # every shutdown.
                closer = getattr(self._client, "aclose", None) or self._client.close
                await closer()
            except Exception:
                pass


__all__ = ["MemoryCache", "RedisCache"]
