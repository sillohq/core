"""
sillo.security.ratelimit.strategies — rate-limit algorithms.

Provides the three built-in strategies and the :func:`get_strategy` factory.
"""

from __future__ import annotations

import typing
from typing import Any, Union

from .base import RateLimitStrategy
from .fixed_window import FixedWindowStrategy
from .sliding_window import SlidingWindowStrategy
from .token_bucket import TokenBucketStrategy

__all__ = [
    "FixedWindowStrategy",
    "RateLimitStrategy",
    "SlidingWindowStrategy",
    "TokenBucketStrategy",
    "get_strategy",
]

_STRATEGY_MAP = {
    "fixed": FixedWindowStrategy,
    "fixed_window": FixedWindowStrategy,
    "sliding": SlidingWindowStrategy,
    "sliding_window": SlidingWindowStrategy,
    "token": TokenBucketStrategy,
    "token_bucket": TokenBucketStrategy,
}


def get_strategy(
    spec: str | RateLimitStrategy | None,
) -> RateLimitStrategy:
    """Resolve a strategy from a name, an instance, or ``None`` (token bucket)."""
    if spec is None:
        return TokenBucketStrategy()
    if isinstance(spec, RateLimitStrategy):
        return spec
    if isinstance(spec, str):
        key = spec.lower()
        if key in _STRATEGY_MAP:
            return _STRATEGY_MAP[key]()
        raise ValueError(f"Unknown rate-limit strategy: {spec!r}")
    raise TypeError(f"Invalid strategy spec: {spec!r}")
