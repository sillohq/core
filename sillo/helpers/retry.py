from __future__ import annotations

import asyncio
import functools
import inspect
import random
import time
from typing import Any, Callable, List, Optional, Tuple, Type, TypeVar, Union

F = TypeVar("F", bound=Callable[..., Any])


class RetryError(Exception):
    """Exception raised when a retryable operation exhausts all retry attempts.

    This exception wraps the last exception encountered during the retry loop,
    providing context about the underlying failure that caused all retries to fail.

    Args:
        message: A human-readable description of the retry failure.
        last_exception: The final exception that was raised during the last
            retry attempt, or None if no exception was captured.

    Attributes:
        last_exception: The last exception caught before retries were exhausted.
    """

    def __init__(self, message: str, last_exception: Optional[Exception] = None):
        """Initialize a RetryError with a message and optional wrapped exception.

        Args:
            message: A human-readable description of the retry failure.
            last_exception: The final exception from the last retry attempt,
                or None if no exception was captured.
        """
        super().__init__(message)
        self.last_exception = last_exception


def _compute_delay(
    attempt: int, base: float, factor: float, cap: float, jitter: bool
) -> float:
    """Compute the delay before the next retry attempt using exponential backoff.

    Calculates the wait time by raising the base delay to the power of the
    attempt number multiplied by the backoff factor, capped at a maximum value.
    Optionally applies random jitter to spread out concurrent retries.

    Args:
        attempt: The zero-based index of the current retry attempt.
        base: The base delay in seconds used as the starting point.
        factor: The multiplier applied exponentially per attempt.
        cap: The maximum delay in seconds; computed delay will not exceed this.
        jitter: If True, randomizes the delay uniformly between 0 and the
            computed value to prevent thundering herd problems.

    Returns:
        The computed delay in seconds before the next retry should occur.
    """
    delay = min(base * (factor**attempt), cap)
    if jitter:
        delay = random.uniform(0, delay)
    return delay


def retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: Union[
        Type[Exception], Tuple[Type[Exception], ...]
    ] = Exception,
):
    """Decorator that retries a function on failure with exponential backoff.

    Wraps both synchronous and asynchronous functions, automatically detecting
    the function type and applying the appropriate retry strategy. Supports
    configurable backoff, jitter, and exception filtering.

    Args:
        max_attempts: Maximum number of times to call the function before
            giving up and raising a RetryError.
        base_delay: Initial delay in seconds before the first retry.
        max_delay: Upper bound in seconds on the computed delay between retries.
        backoff_factor: Multiplier applied to the base delay for each successive
            attempt, creating exponential growth.
        jitter: If True, applies random jitter to each delay to distribute
            retries across time and avoid thundering herd issues.
        retryable_exceptions: A single exception type or tuple of exception types
            that should trigger a retry. Other exceptions propagate immediately.

    Returns:
        A decorator function that wraps the target function with retry logic.
            The wrapper preserves the original function's metadata via functools.wraps.

    Raises:
        RetryError: Raised when all retry attempts have been exhausted without
            the function succeeding.
    """

    def decorator(func: F) -> F:
        """Create a retry-wrapped version of the given function.

        Args:
            func: The callable to wrap with retry logic.

        Returns:
            The wrapped function with retry behavior applied.
        """

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            """Execute the wrapped synchronous function with retry logic.

            Args:
                *args: Positional arguments forwarded to the wrapped function.
                **kwargs: Keyword arguments forwarded to the wrapped function.

            Returns:
                The return value of the wrapped function on success.

            Raises:
                RetryError: If all retry attempts are exhausted.
            """
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
                    delay = _compute_delay(
                        attempt, base_delay, backoff_factor, max_delay, jitter
                    )
                    time.sleep(delay)
            raise RetryError("Unexpected retry exit", last_exc)

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            """Execute the wrapped asynchronous function with retry logic.

            Args:
                *args: Positional arguments forwarded to the wrapped function.
                **kwargs: Keyword arguments forwarded to the wrapped function.

            Returns:
                The return value of the awaited function on success.

            Raises:
                RetryError: If all retry attempts are exhausted.
            """
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
                    delay = _compute_delay(
                        attempt, base_delay, backoff_factor, max_delay, jitter
                    )
                    await asyncio.sleep(delay)
            raise RetryError("Unexpected retry exit", last_exc)

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
    retryable_exceptions: Union[
        Type[Exception], Tuple[Type[Exception], ...]
    ] = Exception,
    **kwargs: Any,
) -> Any:
    """Retry an async callable with exponential backoff and optional jitter.

    Invokes the given coroutine function repeatedly until it succeeds or the
    maximum number of attempts is reached. Uses asyncio.sleep for non-blocking
    delays between attempts.

    Args:
        coro: An async callable to invoke and retry on failure.
        *args: Positional arguments to pass through to the coroutine.
        max_attempts: Maximum number of invocation attempts before giving up.
        base_delay: Initial delay in seconds before the first retry.
        max_delay: Upper bound in seconds on the computed delay between retries.
        backoff_factor: Multiplier applied to the base delay for each successive
            attempt, creating exponential growth.
        jitter: If True, applies random jitter to each delay to distribute
            retries across time and avoid thundering herd issues.
        retryable_exceptions: A single exception type or tuple of exception types
            that should trigger a retry. Other exceptions propagate immediately.
        **kwargs: Keyword arguments to pass through to the coroutine.

    Returns:
        The return value of the coroutine on successful execution.

    Raises:
        RetryError: If all retry attempts are exhausted without success.
    """
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
            delay = _compute_delay(
                attempt, base_delay, backoff_factor, max_delay, jitter
            )
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
    retryable_exceptions: Union[
        Type[Exception], Tuple[Type[Exception], ...]
    ] = Exception,
    **kwargs: Any,
) -> Any:
    """Retry a synchronous callable with exponential backoff and optional jitter.

    Invokes the given function repeatedly until it succeeds or the maximum
    number of attempts is reached. Uses time.sleep for blocking delays
    between attempts.

    Args:
        func: A synchronous callable to invoke and retry on failure.
        *args: Positional arguments to pass through to the function.
        max_attempts: Maximum number of invocation attempts before giving up.
        base_delay: Initial delay in seconds before the first retry.
        max_delay: Upper bound in seconds on the computed delay between retries.
        backoff_factor: Multiplier applied to the base delay for each successive
            attempt, creating exponential growth.
        jitter: If True, applies random jitter to each delay to distribute
            retries across time and avoid thundering herd issues.
        retryable_exceptions: A single exception type or tuple of exception types
            that should trigger a retry. Other exceptions propagate immediately.
        **kwargs: Keyword arguments to pass through to the function.

    Returns:
        The return value of the function on successful execution.

    Raises:
        RetryError: If all retry attempts are exhausted without success.
    """
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
            delay = _compute_delay(
                attempt, base_delay, backoff_factor, max_delay, jitter
            )
            time.sleep(delay)
    raise RetryError("Unexpected retry exit", last_exc)
