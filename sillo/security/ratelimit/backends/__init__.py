"""
sillo.security.ratelimit.backends — rate-limit storage backends.

Provides :class:`InMemoryBackend`, :class:`RedisBackend`,
:class:`RecordBackend`, and the :func:`get_backend` factory used by the
middleware configuration.
"""

from __future__ import annotations

import typing
from typing import Any, Union

from sillo._internals.lazy import deferred

from .base import RateLimitBackend, RateLimitResult
from .memory import InMemoryBackend

# RecordBackend defines a Tortoise model, so importing it here would make
# `import sillo` require the `record` extra — the rate limiter is reached from
# the middleware package, which the application imports unconditionally. It is
# loaded on first use instead, by __getattr__ below and by get_backend.

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
        from .redis import RedisBackend

        return RedisBackend()
    if spec == "record":
        from .record import RecordBackend

        return RecordBackend()
    if isinstance(spec, RateLimitBackend):
        return spec
    raise ValueError(f"Unknown rate-limit backend: {spec!r}")


#: Backends that pull in an optional dependency when first touched.
__getattr__ = deferred(__name__, {"RecordBackend": ".record", "RedisBackend": ".redis"})
