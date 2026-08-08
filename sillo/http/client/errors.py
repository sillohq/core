from __future__ import annotations

import typing

if typing.TYPE_CHECKING:
    from typing import Any


class HTTPClientError(Exception):
    """Base exception for all HTTP client errors."""


class HTTPClientConfigError(HTTPClientError):
    """Raised when client configuration is invalid."""


class HTTPConnectionError(HTTPClientError):
    """Raised when a connection cannot be established to the remote server."""


class HTTPTimeoutError(HTTPClientError):
    """Raised when a request exceeds the configured timeout."""

    def __init__(self, message: str, timeout_type: str | None = None) -> None:
        super().__init__(message)
        self.timeout_type = timeout_type


class HTTPStatusError(HTTPClientError):
    """Raised when a response has a non-success status code and
    ``raise_for_status`` is enabled."""

    def __init__(
        self,
        message: str,
        status_code: int,
        response_body: str | None = None,
        request_url: str | None = None,
        request_method: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body
        self.request_url = request_url
        self.request_method = request_method


class HTTPRetryError(HTTPClientError):
    """Raised after all retry attempts have been exhausted."""

    def __init__(
        self,
        message: str,
        last_exception: Exception | None = None,
        attempts: int = 0,
        total_delay: float = 0.0,
    ) -> None:
        super().__init__(message)
        self.last_exception = last_exception
        self.attempts = attempts
        self.total_delay = total_delay


class HTTPCacheError(HTTPClientError):
    """Raised when cache operations within the HTTP client fail."""


class HTTPValidationError(HTTPClientError):
    """Raised when response validation against a Pydantic model fails."""

    def __init__(
        self,
        message: str,
        validation_errors: list[dict[str, Any]],
        response_body: str | None = None,
    ) -> None:
        super().__init__(message)
        self.validation_errors = validation_errors
        self.response_body = response_body


class HTTPRedirectError(HTTPClientError):
    """Raised when a redirect loop or unexpected redirect occurs."""


class HTTPDecodeError(HTTPClientError):
    """Raised when response content cannot be decoded as JSON."""


__all__ = [
    "HTTPCacheError",
    "HTTPClientConfigError",
    "HTTPClientError",
    "HTTPConnectionError",
    "HTTPDecodeError",
    "HTTPRedirectError",
    "HTTPRetryError",
    "HTTPStatusError",
    "HTTPTimeoutError",
    "HTTPValidationError",
]
