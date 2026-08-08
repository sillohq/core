"""sillo.http.client — Robust async HTTP client built on httpx.

Provides a production-grade HTTP client with:
- Base URL support for cleaner relative URL usage
- Response caching via the sillo.cache subsystem (MemoryCache / RedisCache)
- Pydantic response validation and deserialization
- Configurable retry strategy with exponential backoff (via sillo.helpers.retry)
- Middleware pipeline for request/response transformation
- Connection pooling and granular timeout management
- Request statistics tracking

Quick start:
    ```python
    from pydantic import BaseModel
    from sillo.http.client import HTTPClient

    class User(BaseModel):
        id: int
        name: str
        email: str

    async with HTTPClient("https://jsonplaceholder.typicode.com") as client:
        user = await client.get("/users/1", response_model=User)
        print(user)
    ```

With caching:
    ```python
    from sillo.cache import MemoryCache
    from sillo.http.client import HTTPClient

    async with HTTPClient(
        base_url="https://api.example.com",
        cache_backend=MemoryCache(),
        cache_ttl=60,
    ) as client:
        data = await client.get("/slow-endpoint")
    ```
"""

from sillo.http.client.caching import CacheConfig, CachePolicy, HTTPCache
from sillo.http.client.client import HTTPClient
from sillo.http.client.config import HTTPClientConfig, HTTPClientStats
from sillo.http.client.errors import (
    HTTPCacheError,
    HTTPClientConfigError,
    HTTPClientError,
    HTTPConnectionError,
    HTTPDecodeError,
    HTTPRedirectError,
    HTTPRetryError,
    HTTPStatusError,
    HTTPTimeoutError,
    HTTPValidationError,
)
from sillo.http.client.middleware import (
    BaseURLMiddleware,
    HeaderInjectionMiddleware,
    HTTPMiddleware,
    LoggingMiddleware,
    MiddlewareChain,
)
from sillo.http.client.models import CachedResponse, ResponseValidator
from sillo.http.client.retry import RetryMode, RetryStrategy
from sillo.http.client.transport import ConnectionPoolConfig
from sillo.http.client.utils import (
    extract_response_summary,
    guess_content_type,
    merge_headers,
    sanitize_url_for_log,
)

__all__ = [
    "BaseURLMiddleware",
    "CacheConfig",
    "CachePolicy",
    "CachedResponse",
    "ConnectionPoolConfig",
    "HTTPCache",
    "HTTPCacheError",
    "HTTPClient",
    "HTTPClientConfig",
    "HTTPClientConfigError",
    "HTTPClientError",
    "HTTPClientStats",
    "HTTPConnectionError",
    "HTTPDecodeError",
    "HTTPMiddleware",
    "HTTPRedirectError",
    "HTTPRetryError",
    "HTTPStatusError",
    "HTTPTimeoutError",
    "HTTPValidationError",
    "HeaderInjectionMiddleware",
    "LoggingMiddleware",
    "MiddlewareChain",
    "ResponseValidator",
    "RetryMode",
    "RetryStrategy",
    "extract_response_summary",
    "guess_content_type",
    "merge_headers",
    "sanitize_url_for_log",
]
