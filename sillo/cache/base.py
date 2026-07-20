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

if typing.TYPE_CHECKING:
    from typing import Any, Dict, Iterable, Optional

# Sentinel for "no value / cache miss".
_MISSING = object()


class CacheError(Exception):
    """Base class for cache-related errors."""


class SerializationError(CacheError):
    """Raised when a value cannot be serialized or deserialized."""


@dataclass
class CacheStats:
    """Per-backend cache statistics.

    ``hits`` and ``misses`` count resolved ``get`` calls. ``sets`` and
    ``deletes`` count writes/evictions. ``evictions`` is the number of entries
    removed due to size/LRU pressure (not explicit deletes).
    """

    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    evictions: int = 0

    @property
    def total(self) -> int:
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.hits / self.total

    def as_dict(self) -> Dict[str, int]:
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
    namespace: Optional[str] = None,
    version: Optional[str] = None,
) -> str:
    """Build a deterministic cache key from ordered parts.

    Args:
        *parts: Ordered key components (function name, args, kwargs, ...).
        namespace: Optional prefix isolating a group of keys.
        version: Optional version string; bumping it invalidates every key
            under the same namespace at once.

    The key is stable across processes: equal inputs always produce the same
    string, so a Redis backend and a Memory backend compute identical keys.
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

    Handles the common JSON-safe types, sets/frozensets (sorted), bytes
    (hashed), and falls back to repr for arbitrary objects so that equal
    logical inputs still hash the same way within a process.
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


def tag_key(namespace: Optional[str], tag: str) -> str:
    """Return the storage key for a tag's membership set."""
    ns = namespace or "_"
    return f"tag:{ns}:{tag}"


def serialize(value: Any, use_pickle: bool) -> bytes:
    """Serialize a value to bytes.

    JSON is preferred (safe, cross-language) but only handles JSON-safe data.
    Pickle handles arbitrary Python objects at the cost of being Python-only
    and unsafe for untrusted input.
    """
    try:
        if use_pickle:
            return b"p:" + pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)
        encoded = json.dumps(value, default=_json_default).encode("utf-8")
        return b"j:" + encoded
    except (TypeError, ValueError, pickle.PickleError) as exc:
        raise SerializationError(str(exc)) from exc


def deserialize(payload: bytes) -> Any:
    """Deserialize bytes produced by :func:`serialize`."""
    try:
        if payload.startswith(b"p:"):
            return pickle.loads(payload[2:])
        if payload.startswith(b"j:"):
            return json.loads(payload[2:].decode("utf-8"))
        return json.loads(payload.decode("utf-8"))
    except (ValueError, pickle.PickleError) as exc:
        raise SerializationError(str(exc)) from exc


def _json_default(obj: Any) -> Any:
    """Best-effort JSON converter for dataclasses, sets, and common types."""
    if isinstance(obj, (set, frozenset)):
        return sorted(obj)
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return str(obj)


class BaseCache(abc.ABC):
    """Abstract cache backend.

    Every backend (in-memory, Redis, ...) implements this contract. The
    interface is async-first: backends may perform I/O, and the in-memory
    backend provides synchronous implementations that are safe to ``await``.
    """

    #: Human-readable backend name.
    name: str = "base"

    def __init__(
        self,
        *,
        namespace: Optional[str] = None,
        default_ttl: Optional[int] = None,
        serializer: str = "json",
        stats: Optional[CacheStats] = None,
    ) -> None:
        if serializer not in ("json", "pickle"):
            raise ValueError("serializer must be 'json' or 'pickle'")
        self.namespace = namespace
        self.default_ttl = default_ttl
        self.serializer = serializer
        self._stats = stats or CacheStats()
        self._lock = threading.RLock()

    # ---- statistics -------------------------------------------------

    def stats(self) -> CacheStats:
        return self._stats

    def reset_stats(self) -> None:
        self._stats = CacheStats()

    # ---- key helpers -------------------------------------------------

    def make_key(
        self,
        *parts: Any,
        namespace: Optional[str] = None,
        version: Optional[str] = None,
    ) -> str:
        return build_key(
            *parts,
            namespace=namespace or self.namespace,
            version=version,
        )

    # ---- abstract API ----------------------------------------------

    @abc.abstractmethod
    async def get(self, key: str) -> Any:
        """Return the cached value or :data:`_MISSING` on miss/expiry."""

    @abc.abstractmethod
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        *,
        tags: Optional[Iterable[str]] = None,
        sliding: bool = False,
    ) -> None:
        """Store ``value`` under ``key`` with an optional TTL (seconds)."""

    @abc.abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete ``key``. Return ``True`` if it existed."""

    @abc.abstractmethod
    async def exists(self, key: str) -> bool:
        """Return ``True`` if ``key`` is present and unexpired."""

    @abc.abstractmethod
    async def touch(self, key: str, ttl: Optional[int] = None) -> bool:
        """Reset/expire ``key``. With sliding TTL this extends its lifetime."""

    @abc.abstractmethod
    async def invalidate_tags(self, *tags: str) -> int:
        """Delete every key associated with any of ``tags``. Return count."""

    @abc.abstractmethod
    async def clear(self) -> None:
        """Remove all keys owned by this backend (respecting namespace)."""

    @abc.abstractmethod
    async def close(self) -> None:
        """Release backend resources (connections, timers)."""

    # ---- context manager -------------------------------------------

    async def __aenter__(self) -> "BaseCache":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    # ---- helpers ----------------------------------------------------

    def _resolve_ttl(self, ttl: Optional[int]) -> Optional[int]:
        return ttl if ttl is not None else self.default_ttl


__all__ = [
    "BaseCache",
    "CacheError",
    "SerializationError",
    "CacheStats",
    "build_key",
    "tag_key",
    "serialize",
    "deserialize",
    "_MISSING",
]
