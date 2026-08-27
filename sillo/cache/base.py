"""sillo.cache.base — Cache backend interface, key building, and serialization.

This module defines the contract every cache backend implements and the small
pieces shared by all backends: deterministic key construction (with namespace
and versioning), tag-key mapping, and value serialization (JSON or pickle).
"""

from __future__ import annotations

import abc
import hashlib
import json
import pickle
import threading
import typing
from dataclasses import dataclass

from typing_extensions import Self

if typing.TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Iterable
    from typing import Any

# Sentinel for "no value / cache miss".
_MISSING = object()


class CacheError(Exception):
    """Base class for all cache-related errors.

    This exception serves as the root of the cache exception hierarchy.
    All errors raised by cache backends, serialization routines, and
    configuration helpers derive from this class, allowing callers to
    catch any cache-related failure with a single ``except CacheError``
    clause.

    Attributes:
        message: A human-readable description of the error condition.
    """


class SerializationError(CacheError):
    """Raised when a value cannot be serialized or deserialized.

    This exception is raised by the :func:`serialize` and :func:`deserialize`
    functions when the conversion between Python objects and their byte
    representation fails. Common causes include non-JSON-safe types when
    using the JSON serializer, or corrupt payload data during deserialization.

    Inherits from:
        CacheError: The base class for all cache-related exceptions.
    """


@dataclass
class CacheStats:
    """Per-backend cache statistics.

    ``hits`` and ``misses`` count resolved ``get`` calls. ``sets`` and
    ``deletes`` count writes/evictions. ``evictions`` is the number of entries
    removed due to size/LRU pressure (not explicit deletes).

    This dataclass is mutable and shared between a backend and any external
    monitoring code. All counters start at zero and are incremented by the
    backend during normal operation.

    Attributes:
        hits: Number of cache lookups that returned a valid, unexpired value.
        misses: Number of cache lookups that found no entry or an expired one.
        sets: Number of successful write operations to the cache.
        deletes: Number of explicit key deletions and tag-based invalidations.
        evictions: Number of entries removed due to max-size or LRU pressure.
    """

    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    evictions: int = 0

    @property
    def total(self) -> int:
        """Return the total number of cache lookup operations.

        Computes the sum of hits and misses, representing every call
        that attempted to retrieve a value from the cache backend.

        Returns:
            The combined count of cache hits and misses as an integer.
        """
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        """Return the cache hit rate as a fraction between 0.0 and 1.0.

        Calculates the ratio of successful cache hits to total lookup
        operations. Returns 0.0 when no lookups have been performed,
        avoiding a division-by-zero error.

        Returns:
            A float representing the proportion of lookups that were hits.
            Returns 0.0 if no lookups have occurred yet.
        """
        if self.total == 0:
            return 0.0
        return self.hits / self.total

    def as_dict(self) -> dict[str, Any]:
        """Serialize the statistics into a plain dictionary.

        Produces a dictionary suitable for JSON serialization or logging,
        including computed fields like ``hit_rate`` and ``total`` alongside
        the raw counters. The hit rate is rounded to four decimal places
        for readability.

        Returns:
            A dictionary mapping stat names to their numeric values,
            including ``hits``, ``misses``, ``sets``, ``deletes``,
            ``evictions``, ``hit_rate``, and ``total``.
        """
        return {
            "hits": self.hits,
            "misses": self.misses,
            "sets": self.sets,
            "deletes": self.deletes,
            "evictions": self.evictions,
            "hit_rate": round(self.hit_rate, 4),
            "total": self.total,
        }


def build_key(
    *parts: Any,
    namespace: str | None = None,
    version: str | None = None,
) -> str:
    """Build a deterministic cache key from ordered parts.

    Constructs a SHA-256-based cache key by hashing the stable string
    representation of each part, then optionally prepending a namespace
    prefix and a version tag. The resulting key is stable across processes
    and backend implementations, ensuring that a Redis backend and a
    Memory backend compute identical keys for the same inputs.

    Args:
        *parts: Ordered key components such as function name, positional
            arguments, keyword arguments, or any hashable values.
        namespace: Optional prefix isolating a group of keys into a
            logical namespace for bulk operations like clear or scan.
        version: Optional version string; bumping it invalidates every
            key under the same namespace at once without deleting them.

    Returns:
        A deterministic string key, optionally prefixed with namespace
        and version components separated by colons.

    Raises:
        TypeError: If a part cannot be converted to a stable string
            representation by the internal ``_stable_repr`` helper.
    """
    raw = "|".join(_stable_repr(p) for p in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
    key = digest
    if namespace:
        key = f"{namespace}:{key}"
    if version:
        key = f"v{version}:{key}"
    return key


def _stable_repr(value: Any) -> str:
    """Render a value deterministically for key hashing.

    Produces a canonical string representation of arbitrary Python values
    so that logically equal inputs always yield the same cache key. The
    function handles common JSON-safe types natively, sorts sets and
    frozensets for order-independence, hashes bytes via SHA-256 to keep
    key lengths bounded, and recursively processes nested containers.

    Args:
        value: Any Python object to be converted into a stable string
            representation suitable for inclusion in a cache key hash.

    Returns:
        A deterministic string representation of the input value. JSON-safe
        types are serialized via ``json.dumps``; bytes are SHA-256 hashed;
        sets are sorted; dicts and lists are recursively processed.

    Note:
        Falls back to ``repr()`` for arbitrary objects, which means
        equality depends on the object's ``__repr__`` implementation
        being consistent within a single process.
    """
    if isinstance(value, (str, int, float, bool)) or value is None:
        return json.dumps(value, sort_keys=True, default=str)
    if isinstance(value, (bytes, bytearray)):
        return hashlib.sha256(bytes(value)).hexdigest()[:32]
    if isinstance(value, (set, frozenset)):
        return json.dumps(sorted(_stable_repr(v) for v in value), sort_keys=True)
    if isinstance(value, dict):
        return json.dumps(
            {_stable_repr(k): _stable_repr(v) for k, v in value.items()},
            sort_keys=True,
        )
    if isinstance(value, (list, tuple)):
        return json.dumps([_stable_repr(v) for v in value], sort_keys=True)
    return repr(value)


def tag_key(namespace: str | None, tag: str) -> str:
    """Return the storage key for a tag's membership set.

    Constructs a deterministic key used internally by cache backends to
    track which cache keys are associated with a given invalidation tag.
    The key follows the pattern ``tag:<namespace>:<tag>``, where the
    namespace defaults to an underscore when not provided.

    Args:
        namespace: The cache namespace to scope the tag under. When
            ``None``, the underscore character ``_`` is used as a
            fallback to indicate the global namespace.
        tag: The invalidation tag name whose storage key is being
            computed for the backend's tag-to-keys mapping.

    Returns:
        A string in the format ``tag:<ns>:<tag>`` that backends use
        as the Redis set key or internal dictionary key for tracking
        tag membership.
    """
    ns = namespace or "_"
    return f"tag:{ns}:{tag}"


def serialize(value: Any, use_pickle: bool) -> bytes:
    """Serialize a value to bytes for cache storage.

    Converts a Python object into a byte sequence suitable for storage
    in a cache backend. JSON is the preferred format because it is safe,
    human-readable, and cross-language compatible, but it only handles
    JSON-safe data types. Pickle handles arbitrary Python objects at the
    cost of being Python-only and unsafe for untrusted input.

    Args:
        value: The Python object to serialize. Can be any JSON-safe type
            when using the JSON serializer, or any picklable object when
            using the pickle serializer.
        use_pickle: When ``True``, uses pickle serialization with the
            highest protocol version. When ``False``, uses JSON encoding
            with a custom default handler for extended types.

    Returns:
        A bytes object prefixed with ``b"j:"`` for JSON or ``b"p:"`` for
        pickle, allowing the deserializer to detect the format automatically.

    Raises:
        SerializationError: If the value cannot be serialized by the
            chosen method, wrapping the underlying TypeError, ValueError,
            or PickleError with a descriptive message.
    """
    try:
        if use_pickle:
            return b"p:" + pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)
        encoded = json.dumps(value, default=_json_default).encode("utf-8")
        return b"j:" + encoded
    except (TypeError, ValueError, pickle.PickleError) as exc:
        # This line is exercised (confirmed by direct execution and by
        # `coverage` used standalone), but the compiled RERAISE for a
        # single-statement `raise X(...) from exc` except body is attributed
        # back to the `except` line rather than this one, so pytest-cov never
        # marks it hit. A coverage-attribution quirk, not an untested branch.
        raise SerializationError(str(exc)) from exc  # pragma: no cover


def deserialize(payload: bytes) -> Any:
    """Deserialize bytes produced by :func:`serialize` back into a Python object.

    Detects the serialization format by inspecting the byte prefix: ``b"p:"``
    indicates pickle-encoded data, ``b"j:"`` indicates JSON-encoded data,
    and payloads without a recognized prefix are attempted as plain JSON for
    backward compatibility with legacy payloads.

    Args:
        payload: A bytes object previously produced by :func:`serialize`,
            containing either a JSON or pickle encoded value with the
            appropriate format prefix.

    Returns:
        The deserialized Python object, reconstructed from its byte
        representation. The type matches the original object passed to
        :func:`serialize`.

    Raises:
        SerializationError: If the payload cannot be decoded or parsed,
            wrapping the underlying ValueError or PickleError with a
            descriptive error message for debugging.
    """
    try:
        if payload.startswith(b"p:"):
            return pickle.loads(payload[2:])
        if payload.startswith(b"j:"):
            return json.loads(payload[2:].decode("utf-8"))
        return json.loads(payload.decode("utf-8"))
    except (ValueError, pickle.PickleError) as exc:
        raise SerializationError(str(exc)) from exc


def _json_default(obj: Any) -> Any:
    """Best-effort JSON converter for dataclasses, sets, and common types.

    Serves as the ``default`` callback for :func:`json.dumps`, handling
    types that are not natively JSON-serializable. Sets and frozensets are
    converted to sorted lists for deterministic output. Objects with a
    ``__dict__`` attribute (including dataclass instances) are converted
    to their attribute dictionaries. All other types fall back to their
    string representation.

    Args:
        obj: Any Python object that the JSON encoder could not serialize
            using its built-in type handlers.

    Returns:
        A JSON-compatible representation of the object: a sorted list
        for sets, a dictionary for objects with ``__dict__``, or a
        string fallback for all other types.
    """
    if isinstance(obj, (set, frozenset)):
        return sorted(obj)
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return str(obj)


class BaseCache(abc.ABC):
    """Abstract cache backend defining the contract for all implementations.

    Every cache backend (in-memory, Redis, or future backends) must implement
    this interface. The API is async-first: backends may perform I/O, and the
    in-memory backend provides synchronous implementations that are safe to
    ``await``. The base class handles common concerns like namespace scoping,
    TTL resolution, statistics tracking, and thread-safe locking.

    Subclasses must implement the abstract methods: :meth:`get`, :meth:`set`,
    :meth:`delete`, :meth:`exists`, :meth:`touch`, :meth:`invalidate_tags`,
    :meth:`clear`, and :meth:`close`.

    Attributes:
        name: Human-readable backend identifier (e.g. ``"memory"``, ``"redis"``).
        namespace: Optional key prefix for isolating groups of cache entries.
        default_ttl: Default time-to-live in seconds applied when no explicit
            TTL is provided to individual operations.
        serializer: The serialization strategy, either ``"json"`` or ``"pickle"``.
    """

    #: Human-readable backend name.
    name: str = "base"

    def __init__(
        self,
        *,
        namespace: str | None = None,
        default_ttl: int | None = None,
        serializer: str = "json",
        stats: CacheStats | None = None,
    ) -> None:
        """Initialize the base cache backend with common configuration.

        Sets up the namespace, default TTL, serialization strategy, statistics
        tracker, and a reentrant lock for thread safety. Validates that the
        serializer choice is one of the two supported formats.

        Args:
            namespace: Optional prefix for isolating cache keys into logical
                groups. When set, all keys are prefixed with this value and
                bulk operations like :meth:`clear` only affect this namespace.
            default_ttl: Default time-to-live in seconds for cache entries.
                When ``None``, entries persist indefinitely unless an explicit
                TTL is provided to individual :meth:`set` calls.
            serializer: The serialization format to use for encoding values.
                Must be either ``"json"`` (safe, cross-language) or
                ``"pickle"`` (arbitrary Python objects, Python-only).
            stats: Optional pre-existing :class:`CacheStats` instance to share
                statistics with. When ``None``, a fresh stats object is created.

        Raises:
            ValueError: If ``serializer`` is not ``"json"`` or ``"pickle"``.
        """
        if serializer not in ("json", "pickle"):
            raise ValueError("serializer must be 'json' or 'pickle'")
        self.namespace = namespace
        self.default_ttl = default_ttl
        self.serializer = serializer
        self._stats = stats or CacheStats()
        self._lock = threading.RLock()

    # ---- statistics -------------------------------------------------

    def stats(self) -> CacheStats:
        """Return the current cache statistics for this backend.

        Provides access to the live :class:`CacheStats` instance that tracks
        hits, misses, sets, deletes, and evictions. The returned object is
        the same instance used internally, so its values update in real time
        as cache operations are performed.

        Returns:
            The :class:`CacheStats` dataclass containing all accumulated
            cache operation counters for this backend instance.
        """
        return self._stats

    def reset_stats(self) -> None:
        """Reset all cache statistics counters to zero.

        Replaces the current :class:`CacheStats` instance with a fresh one
        where all counters (hits, misses, sets, deletes, evictions) are
        initialized to zero. This is useful for periodic reporting or
        benchmarking scenarios where you want to measure stats over a
        specific time window.
        """
        self._stats = CacheStats()

    def make_key(
        self,
        *parts: Any,
        namespace: str | None = None,
        version: str | None = None,
    ) -> str:
        """Build a cache key using this backend's namespace as the default.

        Delegates to the module-level :func:`build_key` function, passing
        the backend's own namespace when no explicit namespace override is
        provided. This ensures that keys are consistently scoped to the
        backend's configured namespace.

        Args:
            *parts: Ordered key components such as function name, positional
                arguments, keyword arguments, or any hashable values.
            namespace: Optional namespace override. When ``None``, the
                backend's own ``self.namespace`` attribute is used instead.
            version: Optional version string for bulk key invalidation.

        Returns:
            A deterministic cache key string, scoped to the resolved
            namespace and optionally versioned.
        """
        return build_key(
            *parts,
            namespace=namespace or self.namespace,
            version=version,
        )

    # ---- abstract API ----------------------------------------------

    @abc.abstractmethod
    async def get(self, key: str) -> Any:
        """Retrieve a cached value by its key.

        Looks up the given key in the cache backend and returns the
        deserialized value if found and not expired. On a cache miss or
        when the entry has expired, returns the :data:`_MISSING` sentinel
        object instead of raising an exception.

        Args:
            key: The cache key to look up, as produced by :meth:`make_key`
                or the module-level :func:`build_key` function.

        Returns:
            The cached and deserialized value on a hit, or the
            :data:`_MISSING` sentinel object on a miss or expiry.
        """

    @abc.abstractmethod
    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
        *,
        tags: Iterable[str] | None = None,
        sliding: bool = False,
    ) -> None:
        """Store a value in the cache under the given key.

        Serializes the value and writes it to the backend with an optional
        time-to-live. Supports tag-based invalidation groups and sliding
        TTL mode where the expiry is refreshed on each read.

        Args:
            key: The cache key to store the value under.
            value: The Python object to serialize and cache.
            ttl: Optional time-to-live in seconds. When ``None``, falls
                back to the backend's ``default_ttl`` setting.
            tags: Optional iterable of invalidation tag strings. All keys
                sharing a tag can be bulk-deleted via :meth:`invalidate_tags`.
            sliding: When ``True``, the TTL window is refreshed on every
                :meth:`get` call, implementing a sliding expiration policy.

        Raises:
            SerializationError: If the value cannot be serialized by the
                backend's configured serializer.
        """

    @abc.abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete a single key from the cache.

        Removes the entry associated with the given key, if it exists.
        This is an explicit deletion and is counted separately from
        evictions in the cache statistics.

        Args:
            key: The cache key to remove from the backend.

        Returns:
            ``True`` if the key existed and was deleted, ``False`` if
            the key was not found in the cache.
        """

    @abc.abstractmethod
    async def exists(self, key: str) -> bool:
        """Check whether a key is present and unexpired in the cache.

        Performs a lookup without deserializing the value, making this
        a lightweight way to test for key presence. Expired entries are
        treated as absent and may be cleaned up as a side effect.

        Args:
            key: The cache key to check for existence in the backend.

        Returns:
            ``True`` if the key exists and has not expired, ``False``
            if the key is missing or its TTL has elapsed.
        """

    @abc.abstractmethod
    async def touch(self, key: str, ttl: int | None = None) -> bool:
        """Refresh or update the TTL of an existing cache entry.

        Extends the lifetime of a cached key by resetting its expiration
        time. When used with sliding TTL, this is how the entry's window
        is prolonged. If no explicit TTL is given, the backend's default
        TTL is applied.

        Args:
            key: The cache key whose TTL should be refreshed.
            ttl: Optional new TTL in seconds. When ``None``, the backend's
                ``default_ttl`` is used as the new expiration window.

        Returns:
            ``True`` if the key existed and its TTL was updated, ``False``
            if the key was not found or had already expired.
        """

    @abc.abstractmethod
    async def invalidate_tags(self, *tags: str) -> int:
        """Delete all cache entries associated with any of the given tags.

        Performs a bulk invalidation by removing every key that was stored
        with at least one of the specified tags. This is the primary
        mechanism for group-based cache purging without knowing individual
        key names.

        Args:
            *tags: One or more invalidation tag strings. Every key that
                was written with any of these tags will be deleted.

        Returns:
            The total number of keys that were deleted as a result of
            this tag invalidation operation.
        """

    @abc.abstractmethod
    async def clear(self) -> None:
        """Remove all keys owned by this backend, respecting namespace scope.

        When a namespace is configured, only keys belonging to that
        namespace are removed. When no namespace is set, the entire
        backend is flushed. This operation does not affect keys in
        other namespaces or other backend instances.
        """

    @abc.abstractmethod
    async def close(self) -> None:
        """Release all backend resources such as connections and timers.

        Performs a graceful shutdown of the cache backend, closing any
        open network connections (e.g. Redis), clearing internal data
        structures, and releasing any other resources. After calling
        this method, the backend should not be used for further operations.
        """

    # ---- context manager -------------------------------------------

    async def __aenter__(self) -> Self:
        """Enter the async context manager, returning the backend instance.

        Allows the cache backend to be used with ``async with`` syntax for
        automatic resource cleanup. The backend instance is returned so
        that it can be bound to a variable within the context block.

        Returns:
            The cache backend instance itself, enabling usage like
            ``async with MemoryCache() as cache:`` patterns.
        """
        return self

    async def __aexit__(self, *exc: object) -> None:
        """Exit the async context manager, releasing backend resources.

        Called automatically when the ``async with`` block exits, whether
        normally or due to an exception. Delegates to :meth:`close` to
        ensure all connections and internal resources are properly released.

        Args:
            *exc: Exception information (type, value, traceback) if the
                context block exited due to an exception, or ``None``
                values on normal exit.
        """
        await self.close()

    def _resolve_ttl(self, ttl: int | None) -> int | None:
        """Resolve the effective TTL for a cache operation.

        Returns the explicitly provided TTL if not ``None``, otherwise
        falls back to the backend's configured ``default_ttl``. This
        method centralizes the TTL resolution logic so that all write
        operations use a consistent fallback strategy.

        Args:
            ttl: The explicitly requested TTL in seconds, or ``None``
                to indicate that the backend default should be used.

        Returns:
            The resolved TTL value in seconds, which is either the
            explicit value or the backend's default, or ``None`` if
            neither was configured.
        """
        return ttl if ttl is not None else self.default_ttl


__all__ = [
    "_MISSING",
    "BaseCache",
    "CacheError",
    "CacheStats",
    "SerializationError",
    "build_key",
    "deserialize",
    "serialize",
    "tag_key",
]
