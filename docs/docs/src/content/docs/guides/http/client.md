---
title: HTTP Client
description: Production-grade async HTTP client with caching, retry, Pydantic validation, and middleware — built on httpx.
---

# HTTP Client (`sillo.http.client`)

A robust async HTTP client built on top of httpx. Ships with base URL support, response caching (via the `sillo.cache` subsystem), Pydantic response validation, retry with exponential backoff (via `sillo.helpers.retry`), a middleware pipeline, connection pooling, and request statistics.

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

## Quick start

The client accepts a `base_url` so you can use relative paths for every request:

```python
from sillo.http.client import HTTPClient

async with HTTPClient("https://api.example.com") as client:
    data = await client.get("/users")
    result = await client.post("/users", json={"name": "Alice"})
    await client.put("/users/1", json={"name": "Bob"})
    await client.delete("/users/1")
```

All standard HTTP methods are available as async shorthands — `get`, `post`, `put`, `patch`, `delete`, `head`, and `options`.

## Configuration

Pass configuration either as keyword arguments to `HTTPClient` or via an `HTTPClientConfig` object:

```python
from sillo.http.client import HTTPClientConfig

config = HTTPClientConfig(
    base_url="https://api.example.com",
    default_timeout=15.0,
    connect_timeout=5.0,
    max_connections=100,
    user_agent="MyApp/1.0",
)

async with HTTPClient(config=config) as client:
    ...
```

| Parameter | Default | Description |
|---|---|---|
| `base_url` | `""` | Base URL prepended to all relative requests |
| `default_timeout` | `30.0` | Default timeout (connect, read, write, pool) |
| `connect_timeout` | `None` | Connection timeout override |
| `read_timeout` | `None` | Read timeout override |
| `write_timeout` | `None` | Write timeout override |
| `pool_timeout` | `None` | Pool timeout override |
| `max_connections` | `50` | Max concurrent connections |
| `max_keepalive_connections` | `20` | Max idle connections kept alive |
| `verify_ssl` | `True` | Verify SSL certificates |
| `follow_redirects` | `True` | Follow HTTP redirects automatically |
| `max_redirects` | `20` | Max number of redirects |
| `default_headers` | `None` | Headers sent with every request |
| `default_auth` | `None` | Basic auth tuple `(username, password)` |
| `user_agent` | `None` | Custom User-Agent header |
| `raise_for_status` | `False` | Raise `HTTPStatusError` on non-2xx |
| `retry_strategy` | `None` | `RetryStrategy` for automatic retries |
| `cache_backend` | `None` | `BaseCache` instance for response caching |
| `cache_ttl` | `300` | Default cache TTL in seconds |
| `cache_key_prefix` | `None` | Prefix for cache keys |
| `cache_tags` | `None` | Invalidation tags for cached responses |
| `middlewares` | `[]` | Ordered list of middleware instances |

## Response validation with Pydantic

Pass a Pydantic model to deserialise responses automatically:

```python
from pydantic import BaseModel
from sillo.http.client import HTTPClient

class Product(BaseModel):
    id: int
    name: str
    price: float

async with HTTPClient("https://api.example.com") as client:
    product = await client.get("/products/1", response_model=Product)
    assert isinstance(product, Product)
```

For endpoints that return a JSON array, pass `many=True`:

```python
products = await client.get("/products", response_model=Product, many=True)
assert isinstance(products, list)
assert isinstance(products[0], Product)
```

Enable strict mode for type-coercion-free validation:

```python
product = await client.get("/products/1", response_model=Product, strict=True)
```

When no `response_model` is given, JSON responses are parsed automatically and plain text responses are returned as strings:

```python
result = await client.get("/data")       # dict or list from JSON
text = await client.get("/text-page")    # raw string
```

## Caching

The HTTP client integrates with the `sillo.cache` subsystem. Pass any `BaseCache` backend (e.g. `MemoryCache` or `RedisCache`) and responses matching the configured cache policy are stored and served automatically:

```python
from sillo.cache import MemoryCache
from sillo.http.client import HTTPClient

async with HTTPClient(
    "https://api.example.com",
    cache_backend=MemoryCache(),
    cache_ttl=60,
    cache_tags=["users"],
) as client:
    user = await client.get("/users/1")   # read-through cache
    await client.invalidate_cache("https://api.example.com/users/1")
```

### Cache policies

| Policy | Behaviour |
|---|---|
| `CachePolicy.ENABLED` | Read and write cached responses |
| `CachePolicy.DISABLED` | No caching |
| `CachePolicy.READ_ONLY` | Read from cache, never write |
| `CachePolicy.WRITE_ONLY` | Write to cache, never read |

By default only `GET` requests with `200` responses are cached. Configure via `CacheConfig`:

```python
from sillo.http.client import CacheConfig, CachePolicy

config = CacheConfig(
    policy=CachePolicy.ENABLED,
    ttl=60,
    methods=frozenset({"GET", "HEAD"}),
    status_codes=frozenset({200, 301, 302}),
)
```

### Cache management

```python
await client.invalidate_cache("https://api.example.com/slow-endpoint")
await client.invalidate_cache_tags("users", "profiles")
await client.clear_cache()
```

## Retry with exponential backoff

Configure automatic retries by passing a `RetryStrategy`:

```python
from sillo.http.client import RetryStrategy

strategy = RetryStrategy(
    max_attempts=5,
    base_delay=1.0,
    backoff_factor=2.0,
    jitter=True,
)

async with HTTPClient("https://api.example.com", retry_strategy=strategy) as client:
    data = await client.get("/unreliable-endpoint")
```

| Parameter | Default | Description |
|---|---|---|
| `max_attempts` | 3 | Total attempts before giving up |
| `base_delay` | 1.0 | Initial delay in seconds |
| `max_delay` | 60.0 | Cap on delay |
| `backoff_factor` | 2.0 | Multiplier per attempt |
| `jitter` | True | Randomize delay to avoid thundering herd |
| `retryable_exceptions` | `Exception` | Tuple of exception types to retry on |
| `retryable_statuses` | `{429, 500, 502, 503, 504}` | Status codes that trigger a retry |

The retry mechanism uses `sillo.helpers.retry` under the hood.

## Middleware

The middleware pipeline lets you intercept requests and responses for cross-cutting concerns.

### Built-in middleware

```python
from sillo.http.client import (
    BaseURLMiddleware,
    HeaderInjectionMiddleware,
    LoggingMiddleware,
)

middlewares = [
    LoggingMiddleware(),
    HeaderInjectionMiddleware({"X-Client": "sillo-http"}),
    BaseURLMiddleware("https://api.example.com"),
]

async with HTTPClient(middlewares=middlewares) as client:
    ...
```

### Custom middleware

Implement `HTTPMiddleware` with a `handle` method that yields a response:

```python
from sillo.http.client import HTTPMiddleware
from httpx import Request

class TimingMiddleware(HTTPMiddleware):
    async def handle(self, request, next_call):
        import time
        start = time.monotonic()
        async for response in next_call(request):
            response.headers["X-Response-Time"] = str(time.monotonic() - start)
            yield response
```

## HTTP errors

All errors inherit from `HTTPClientError`:

```python
from sillo.http.client import (
    HTTPClientError, HTTPStatusError, HTTPTimeoutError,
    HTTPConnectionError, HTTPRetryError, HTTPCacheError,
    HTTPValidationError, HTTPRedirectError, HTTPDecodeError,
)
```

```python
from sillo.http.client import HTTPClientError

try:
    data = await client.get("/users")
except HTTPTimeoutError:
    print("Request timed out")
except HTTPConnectionError:
    print("Could not connect")
except HTTPStatusError as e:
    print(f"HTTP {e.status_code}: {e.response_body}")
```

## Connection pooling

Configure the underlying httpx connection pool:

```python
from sillo.http.client import ConnectionPoolConfig

pool = ConnectionPoolConfig(
    max_connections=100,
    max_keepalive_connections=30,
    keepalive_expiry=60.0,
)
```

## Statistics

Track request success rates, cache efficiency, and retry counts:

```python
async with HTTPClient("https://api.example.com") as client:
    await client.get("/users")

stats = client.stats
print(stats.requests_total)      # 1
print(stats.requests_success)    # 1
print(stats.requests_failed)     # 0
print(stats.cache_hits)          # 0
print(stats.cache_misses)        # 0
print(stats.success_rate)        # 1.0
print(stats.as_dict())

client.reset_stats()
```

## Utilities

```python
from sillo.http.client import (
    extract_response_summary,   # human-readable summary of an httpx Response
    merge_headers,              # merge two header dicts (override wins)
    sanitize_url_for_log,       # strip sensitive query params (api_key, password)
    guess_content_type,         # guess Content-Type from a Python value
)
```

## Full example

```python
from pydantic import BaseModel
from sillo.cache import MemoryCache
from sillo.http.client import (
    HTTPClient, RetryStrategy,
    LoggingMiddleware, HeaderInjectionMiddleware,
)

class Repo(BaseModel):
    id: int
    name: str
    full_name: str
    description: str | None = None

async with HTTPClient(
    "https://api.github.com",
    cache_backend=MemoryCache(),
    cache_ttl=120,
    retry_strategy=RetryStrategy(max_attempts=3),
    middlewares=[
        LoggingMiddleware(),
        HeaderInjectionMiddleware({"Accept": "application/vnd.github.v3+json"}),
    ],
    user_agent="MyApp/1.0",
) as client:
    repos = await client.get(
        "/repos/sillo-labs/sillo",
        response_model=Repo,
    )
    print(repos.full_name)
```

## API reference

| Symbol | Kind | Purpose |
|---|---|---|
| `HTTPClient` | class | Main async HTTP client |
| `HTTPClientConfig` | dataclass | Configuration for the client |
| `HTTPClientStats` | dataclass | Runtime request statistics |
| `HTTPCache` | class | Bridges `sillo.cache` backend to HTTP responses |
| `CacheConfig` | dataclass | Per-client cache configuration |
| `CachePolicy` | enum | ENABLED / DISABLED / READ_ONLY / WRITE_ONLY |
| `CachedResponse` | model | Serialisable cached HTTP response |
| `ResponseValidator` | class | Pydantic response validation logic |
| `RetryStrategy` | class | Retry parameters (wraps `sillo.helpers.retry`) |
| `RetryMode` | enum | CONSTANT / LINEAR / EXPONENTIAL |
| `HTTPMiddleware` | abstract class | Base class for middleware |
| `MiddlewareChain` | class | Orchestrates middleware execution |
| `LoggingMiddleware` | class | Request/response logging |
| `HeaderInjectionMiddleware` | class | Add headers to every request |
| `BaseURLMiddleware` | class | Prepend base URL to relative requests |
| `ConnectionPoolConfig` | dataclass | httpx connection pool settings |
| `HTTPClientError` | exception | Base for all HTTP client errors |
| `HTTPStatusError` | exception | Non-2xx response or HTTP error |
| `HTTPTimeoutError` | exception | Request timeout |
| `HTTPConnectionError` | exception | Connection failure |
| `HTTPRetryError` | exception | Retries exhausted |
| `HTTPCacheError` | exception | Cache operation failure |
| `HTTPValidationError` | exception | Pydantic validation failure |
| `HTTPRedirectError` | exception | Redirect loop or max redirects |
| `HTTPDecodeError` | exception | Response body decode failure |
