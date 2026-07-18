"""
sillo.security.ratelimit.backends — rate-limit storage backends.

Provides :class:`InMemoryBackend`, :class:`RedisBackend`,
:class:`RecordBackend`, and the :func:`get_backend` factory used by the
middleware configuration.
"""

from __future__ import annotations

import typing
from typing import Any, Union

from .base import RateLimitBackend, RateLimitResult
from .memory import InMemoryBackend
from .record import RecordBackend
from .redis import RedisBackend

__all__ = [
    "RateLimitBackend",
    "RateLimitResult",
    "InMemoryBackend",
    "RedisBackend",
    "RecordBackend",
    "get_backend",
]


def get_backend(spec: Union[str, RateLimitBackend, None]) -> RateLimitBackend:
    """Resolve a backend from a string name, an instance, or ``None``.

    Args:
        spec: One of ``"memory"``, ``"redis"``, ``"record"``, an existing
            :class:`RateLimitBackend` instance, or ``None`` (defaults to memory).
    """
    if spec is None or spec == "memory":
        return InMemoryBackend()
    if spec == "redis":
        return RedisBackend()
    if spec == "record":
        return RecordBackend()
    if isinstance(spec, RateLimitBackend):
        return spec
    raise ValueError(f"Unknown rate-limit backend: {spec!r}")
