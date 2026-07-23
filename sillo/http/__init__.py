"""sillo.http — HTTP sub-packages.

- ``sillo.http.client``: Production-grade async HTTP client (httpx-based).
"""

from sillo.http.client import (
    BaseURLMiddleware,
    CacheConfig,
    CachePolicy,
    CachedResponse,
    ConnectionPoolConfig,
    HTTPCache,
    HTTPClient,
    HTTPClientConfig,
    HTTPClientError,
    HTTPClientStats,
    HTTPMiddleware,
    HeaderInjectionMiddleware,
    LoggingMiddleware,
    MiddlewareChain,
    ResponseValidator,
    RetryMode,
    RetryStrategy,
    extract_response_summary,
    guess_content_type,
    merge_headers,
    sanitize_url_for_log,
)

__all__ = [
    "HTTPClient",
    "HTTPClientConfig",
    "HTTPClientStats",
    "HTTPCache",
    "CacheConfig",
    "CachePolicy",
    "CachedResponse",
    "ResponseValidator",
    "RetryStrategy",
    "RetryMode",
    "HTTPMiddleware",
    "MiddlewareChain",
    "LoggingMiddleware",
    "HeaderInjectionMiddleware",
    "BaseURLMiddleware",
    "ConnectionPoolConfig",
    "HTTPClientError",
    "extract_response_summary",
    "merge_headers",
    "sanitize_url_for_log",
    "guess_content_type",
]
