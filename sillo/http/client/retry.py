from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class RetryMode(str, Enum):
    """Available retry timing strategies."""

    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    CONSTANT = "constant"


@dataclass
class RetryStrategy:
    """Configuration for retry behaviour on transient HTTP failures.

    Attributes:
        max_attempts: Maximum number of retry attempts before giving up (default 3).
        base_delay: Initial delay in seconds between retries (default 1.0).
        max_delay: Maximum delay in seconds, capping exponential growth (default 60.0).
        backoff_factor: Multiplier for exponential backoff (default 2.0).
        mode: The timing strategy (EXPONENTIAL, LINEAR, or CONSTANT).
        jitter: When True, randomises each delay to prevent thundering herd.
        retryable_statuses: HTTP status codes that trigger a retry.
        retryable_exceptions: Exception classes that trigger a retry.
        max_retry_duration: Hard cap on total retry time across all attempts.
            When 0.0, no duration cap is enforced.
    """

    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0
    mode: RetryMode = RetryMode.EXPONENTIAL
    jitter: bool = True
    retryable_statuses: set[int] = field(
        default_factory=lambda: {408, 429, 500, 502, 503, 504}
    )
    retryable_exceptions: tuple[type[Exception], ...] = (
        ConnectionError,
        TimeoutError,
    )
    max_retry_duration: float = 0.0

    def compute_delay(self, attempt: int) -> float:
        """Compute the delay before the next retry attempt.

        Args:
            attempt: The zero-based index of the current retry attempt.

        Returns:
            The delay in seconds before the next retry.
        """
        import random

        if self.mode == RetryMode.CONSTANT:
            delay = self.base_delay
        elif self.mode == RetryMode.LINEAR:
            delay = min(self.base_delay * (attempt + 1), self.max_delay)
        else:
            delay = min(
                self.base_delay * (self.backoff_factor**attempt), self.max_delay
            )

        if self.jitter:
            delay = random.uniform(0, delay)
        return delay

    def should_retry_for_status(self, status_code: int) -> bool:
        return status_code in self.retryable_statuses

    def should_retry_for_exception(self, exc: Exception) -> bool:
        return isinstance(exc, self.retryable_exceptions)


__all__ = [
    "RetryMode",
    "RetryStrategy",
]
