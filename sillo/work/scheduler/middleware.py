"""
sillo.work.scheduler.middleware — Per-job middleware for scheduled tasks.

Middleware factories receive ``(handler, job)`` and return a new handler.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Annotated, Any, Awaitable, Callable

from typing_extensions import Doc

logger = logging.getLogger("sillo.work.scheduler.middleware")


async def timeout_middleware(
    handler: Callable[[], Awaitable[Any]],
    job: Any,
    *,
    seconds: Annotated[float, Doc("Max execution time in seconds.")] = 30.0,
) -> Callable[[], Awaitable[Any]]:
    """Enforce a hard deadline on the scheduled job."""

    async def wrapper():
        """Wrapper

            Returns:
                [description]

            Raises:
                [description]
        """
        return await asyncio.wait_for(handler(), timeout=seconds)

    return wrapper


async def rate_limit_middleware(
    handler: Callable[[], Awaitable[Any]],
    job: Any,
    *,
    max_per_second: Annotated[
        float, Doc("Max executions per second across all instances of this job.")
    ] = 10,
) -> Callable[[], Awaitable[Any]]:
    """Rate-limit execution using a token bucket shared across job instances."""
    tokens = float(max_per_second)
    last_refill = time.monotonic()

    async def wrapper():
        """Wrapper

            Returns:
                [description]

            Raises:
                [description]
        """
        nonlocal tokens, last_refill
        now = time.monotonic()
        elapsed = now - last_refill
        tokens = min(max_per_second, tokens + elapsed * max_per_second)
        last_refill = now
        if tokens < 1:
            wait = (1 - tokens) / max_per_second
            await asyncio.sleep(wait)
            tokens = 0
            last_refill = time.monotonic()
        else:
            tokens -= 1
        return await handler()

    return wrapper


async def retry_middleware(
    handler: Callable[[], Awaitable[Any]],
    job: Any,
    *,
    max_attempts: Annotated[int, Doc("Total attempts.")] = 3,
    base_delay: Annotated[float, Doc("Initial backoff seconds.")] = 1.0,
) -> Callable[[], Awaitable[Any]]:
    """Retry on failure with exponential backoff."""

    async def wrapper():
        """Wrapper

            Returns:
                [description]

            Raises:
                [description]
        """
        for attempt in range(1, max_attempts + 1):
            try:
                return await handler()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if attempt >= max_attempts:
                    raise
                delay = base_delay * (2 ** (attempt - 1))
                logger.warning(
                    "Scheduler retry %d/%d for %s in %.1fs: %s",
                    attempt,
                    max_attempts,
                    job.name,
                    delay,
                    exc,
                )
                await asyncio.sleep(delay)
        return None

    return wrapper
