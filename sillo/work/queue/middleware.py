"""
sillo.work.queue.middleware — Job middleware pipeline.

Middleware wraps job execution.  Each middleware is a callable that
receives the next handler and returns a new handler.  Inspired by
Laravel's job middleware.

Built-in:
* ``RetryMiddleware`` — automatic retry with configurable attempts & backoff
* ``RateLimitMiddleware`` — token-bucket rate limiting
* ``TimeoutMiddleware`` — enforce a per-job execution deadline
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Annotated, Any, Awaitable, Callable, List, Optional

from typing_extensions import Doc

logger = logging.getLogger("sillo.work.queue.middleware")

JobHandler = Callable[[], Awaitable[Any]]
JobMiddleware = Callable[[JobHandler], JobHandler]


class RetryMiddleware:
    """Automatically retry a job on failure with exponential backoff.

    Usage::

        class MyJob(Job):
            middleware = [RetryMiddleware(max_attempts=5, base_delay=2.0)]
    """

    def __init__(
        self,
        max_attempts: Annotated[int, Doc("Total attempts before giving up.")] = 3,
        base_delay: Annotated[float, Doc("Initial backoff seconds.")] = 1.0,
        max_delay: Annotated[float, Doc("Cap on backoff.")] = 60.0,
    ):
        """Init

        Args:
            max_attempts: [description]
            base_delay: [description]
            max_delay: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay

    def __call__(self, handler: JobHandler) -> JobHandler:
        """Call

        Args:
            handler: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        max_attempts = self.max_attempts
        base_delay = self.base_delay
        max_delay = self.max_delay

        async def wrapper() -> Any:
            """Wrapper

            Returns:
                [description]

            Raises:
                [description]
            """
            last_exc = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await handler()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    last_exc = exc
                    if attempt >= max_attempts:
                        raise
                    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    logger.warning(
                        "Retry %d/%d in %.1fs: %s", attempt, max_attempts, delay, exc
                    )
                    await asyncio.sleep(delay)
            raise last_exc or RuntimeError("RetryMiddleware: unreachable")

        return wrapper


class RateLimitMiddleware:
    """Token-bucket rate limiter — allows *max_jobs* per *per_seconds*.

    Usage::

        class MyJob(Job):
            middleware = [RateLimitMiddleware(max_jobs=10, per_seconds=60)]
    """

    def __init__(
        self,
        max_jobs: Annotated[int, Doc("Max jobs allowed in the window.")] = 10,
        per_seconds: Annotated[float, Doc("Time window in seconds.")] = 60.0,
        burst: Annotated[int, Doc("Initial burst capacity.")] = 1,
    ):
        """Init

        Args:
            max_jobs: [description]
            per_seconds: [description]
            burst: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        self.max_jobs = max_jobs
        self.per_seconds = per_seconds
        self.burst = burst
        self._tokens = float(burst)
        self._last_refill = time.monotonic()

    def __call__(self, handler: JobHandler) -> JobHandler:
        """Call

        Args:
            handler: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        rate = self.max_jobs / self.per_seconds

        async def wrapper() -> Any:
            """Wrapper

            Returns:
                [description]

            Raises:
                [description]
            """
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(self.burst, self._tokens + elapsed * rate)
            self._last_refill = now

            if self._tokens < 1:
                wait = (1 - self._tokens) / rate
                await asyncio.sleep(wait)
                self._tokens = 0
                self._last_refill = time.monotonic()
            else:
                self._tokens -= 1

            return await handler()

        return wrapper


class TimeoutMiddleware:
    """Enforce a hard deadline on job execution.

    Usage::

        class MyJob(Job):
            middleware = [TimeoutMiddleware(seconds=30)]
    """

    def __init__(self, seconds: Annotated[float, Doc("Max execution seconds.")] = 30.0):
        """Init

        Args:
            seconds: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        self.seconds = seconds

    def __call__(self, handler: JobHandler) -> JobHandler:
        """Call

        Args:
            handler: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        seconds = self.seconds

        async def wrapper() -> Any:
            """Wrapper

            Returns:
                [description]

            Raises:
                [description]
            """
            return await asyncio.wait_for(handler(), timeout=seconds)

        return wrapper
