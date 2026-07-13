from __future__ import annotations

import asyncio
import functools
import random
import time
from typing import Any, Callable, List, Optional, Tuple, Type, TypeVar, Union

F = TypeVar("F", bound=Callable[..., Any])


class RetryError(Exception):
    def __init__(self, message: str, last_exception: Optional[Exception] = None):
        super().__init__(message)
        self.last_exception = last_exception


def _compute_delay(attempt: int, base: float, factor: float, cap: float, jitter: bool) -> float:
    delay = min(base * (factor ** attempt), cap)
    if jitter:
        delay = random.uniform(0, delay)
    return delay


def retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: Union[Type[Exception], Tuple[Type[Exception], ...]] = Exception,
):
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exc = e
                    if attempt == max_attempts - 1:
                        raise RetryError(
                            f"Retry failed after {max_attempts} attempts", last_exc
                        )
                    delay = _compute_delay(attempt, base_delay, backoff_factor, max_delay, jitter)
                    time.sleep(delay)
            raise RetryError("Unexpected retry exit", last_exc)

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc = None
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exc = e
                    if attempt == max_attempts - 1:
                        raise RetryError(
                            f"Retry failed after {max_attempts} attempts", last_exc
                        )
                    delay = _compute_delay(attempt, base_delay, backoff_factor, max_delay, jitter)
                    await asyncio.sleep(delay)
            raise RetryError("Unexpected retry exit", last_exc)

        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper  # type: ignore[return-value]
        return wrapper  # type: ignore[return-value]

    return decorator


async def async_retry(
    coro: Callable[..., Any],
    *args: Any,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: Union[Type[Exception], Tuple[Type[Exception], ...]] = Exception,
    **kwargs: Any,
) -> Any:
    last_exc = None
    for attempt in range(max_attempts):
        try:
            return await coro(*args, **kwargs)
        except retryable_exceptions as e:
            last_exc = e
            if attempt == max_attempts - 1:
                raise RetryError(
                    f"Retry failed after {max_attempts} attempts", last_exc
                )
            delay = _compute_delay(attempt, base_delay, backoff_factor, max_delay, jitter)
            await asyncio.sleep(delay)
    raise RetryError("Unexpected retry exit", last_exc)


def sync_retry(
    func: Callable[..., Any],
    *args: Any,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: Union[Type[Exception], Tuple[Type[Exception], ...]] = Exception,
    **kwargs: Any,
) -> Any:
    last_exc = None
    for attempt in range(max_attempts):
        try:
            return func(*args, **kwargs)
        except retryable_exceptions as e:
            last_exc = e
            if attempt == max_attempts - 1:
                raise RetryError(
                    f"Retry failed after {max_attempts} attempts", last_exc
                )
            delay = _compute_delay(attempt, base_delay, backoff_factor, max_delay, jitter)
            time.sleep(delay)
    raise RetryError("Unexpected retry exit", last_exc)
