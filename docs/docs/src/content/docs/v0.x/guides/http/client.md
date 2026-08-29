---
title: HTTP Client
description: "Calling other services from sillo: the httpx-based client with caching, retry, Pydantic validation and middleware, plus the failure modes of talking to a network you do not control."
head:
  - tag: meta
    attrs:
      property: og:title
      content: HTTP Client
  - tag: meta
    attrs:
      property: og:description
      content: "Calling other services from sillo: the httpx-based client with caching, retry, Pydantic validation and middleware, plus the failure modes of talking to a network you do not control."
---

#  HTTP Client (`sillo.http.client`)

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

##  Quick start

The client accepts a `base_url` so you can use relative paths for every request:

```python
from sillo.http.client import HTTPClient

async with HTTPClient("https://api.example.com") as client:
    data = await client.get("/users")
    result = await client.post("/users", json={"name": "Alice"})
    await client.put("/users/1", json={"name": "Bob"})
    await client.delete("/users/1")
```

All standard HTTP methods are available as async shorthands: `get`, `post`,
`put`, `patch`, `delete`, `head`, and `options`.

##  Configuration

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

##  Response validation with Pydantic

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

##  Caching

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

###  Cache policies

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

###  Cache management

```python
await client.invalidate_cache("https://api.example.com/slow-endpoint")
await client.invalidate_cache_tags("users", "profiles")
await client.clear_cache()
```

##  Retry with exponential backoff

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

##  Middleware

The middleware pipeline lets you intercept requests and responses for cross-cutting concerns.

###  Built-in middleware

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

###  Custom middleware

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

##  HTTP errors

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

##  Connection pooling

Configure the underlying httpx connection pool:

```python
from sillo.http.client import ConnectionPoolConfig

pool = ConnectionPoolConfig(
    max_connections=100,
    max_keepalive_connections=30,
    keepalive_expiry=60.0,
)
```

##  Statistics

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

##  Utilities

```python
from sillo.http.client import (
    extract_response_summary,   # human-readable summary of an httpx Response
    merge_headers,              # merge two header dicts (override wins)
    sanitize_url_for_log,       # strip sensitive query params (api_key, password)
    guess_content_type,         # guess Content-Type from a Python value
)
```

##  Full example

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
        "/repos/sillohq/core",
        response_model=Repo,
    )
    print(repos.full_name)
```

##  API reference

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


---

##  Calling a network you do not control

Everything above is API surface. This section is about the part that
actually causes incidents: the other service.

###  Every outbound call needs a timeout

An HTTP call without a timeout can hang forever. One hung call holds a
connection, a task, and (if it happens inside a request handler) a client
waiting on your endpoint. A dependency that stops responding without closing
connections will exhaust your worker pool in minutes, and your service goes
down without ever having an error.

`HTTPClientConfig` exposes granular timeouts because the phases fail
differently:

| Phase | Typical value | What a timeout here means |
|---|---|---|
| connect | 2: 5s | The host is unreachable or overloaded |
| read | 5: 30s | Connected, but the response is slow |
| write | 5: 10s | Your request body is uploading slowly |
| pool | 1: 5s | You are out of connections locally |

A pool timeout is the one that surprises people: it means *your* client
is saturated, not that the remote is slow. Seeing them is a signal to
raise `max_connections` or reduce concurrency, not to raise the read
timeout.

Set the total budget below your own endpoint's budget. If your API promises a
response in two seconds, an upstream call with a 30-second read timeout cannot
honour that. The timeout is a promise you are making to your own callers.

###  Retry only what is safe to repeat

Retrying is the default reflex and it is wrong for anything non-idempotent.
`GET`, `HEAD`, `PUT`, and `DELETE` are safe to repeat by definition. `POST` is
not. A retried payment is a double charge.

Retry these:

- Connection errors and timeouts where no response was received
- `429 Too Many Requests`, respecting `Retry-After`
- `502`, `503`, `504`: the upstream is failing, not you

Do not retry these:

- `400`, `422`: the request is wrong and will be wrong again
- `401`, `403`: refresh credentials instead
- `404`: it will still not exist
- `409`: resolve the conflict

For a `POST` you must retry, send an idempotency key the upstream
honours, so a duplicate request is deduplicated on their side rather than
executed twice.

###  Backoff needs jitter

Exponential backoff without jitter synchronises your clients. If fifty workers
all fail at the same moment and all retry after exactly two seconds, the
upstream receives fifty simultaneous requests at exactly the moment it is least
able to serve them, and the cycle repeats, louder, at four seconds.

Jitter breaks the synchronisation. The arithmetic and the tradeoffs
between full, equal, and decorrelated jitter are covered in the
[retry helpers guide](/v0.x/guides/helpers/retry/).

Cap total attempts and total elapsed time, not just the delay. Three
attempts over ten seconds is a policy; "retry with exponential backoff"
without a ceiling is an unbounded wait.

###  Stop calling a service that is down

Retrying a service that is comprehensively down converts one failure into
several, multiplies load on something already struggling, and turns a
fast failure into a slow one. A circuit breaker fixes this: after N
consecutive failures, fail immediately without making the call, and probe
occasionally to see whether it has recovered.

The user-visible difference is large. Without a breaker, an outage in a
dependency makes every one of your endpoints take thirty seconds to fail.
With one, they fail in a millisecond and you can serve a degraded
response instead.

Design the degraded response before you need it. A recommendations
service being down should mean a page without recommendations, not a 500.

###  Never log the URL directly

Query strings carry API keys, tokens, and signed parameters, and logs are
copied into places credentials should never reach.

```python
logger.info("calling %s", sanitize_url_for_log(url))
```

`sanitize_url_for_log` is exported for exactly this. Apply the same care to
headers, an `Authorization` header dumped into a debug log is a credential leak
with a timestamp on it.

###  Validate the response, do not trust it

`response_model=` runs the payload through Pydantic and raises
`HTTPValidationError` when the shape is wrong. That converts a silent
`KeyError` three layers away into an immediate, specific failure at the
boundary.

The cost is coupling: your model must accept every field the upstream
sends today and might send tomorrow. Model only the fields you use and
let Pydantic ignore the rest, so a new field upstream is not an outage
for you.

###  Cache reads, never writes

`cache_ttl` caches successful `GET` responses. That is a large win for data
that changes slowly (currency rates, feature flags, catalogue lookups) and
turns a network call into a dictionary lookup.

Two rules. Cache only idempotent methods; caching a `POST` response means a
later `POST` returns a stale result without doing anything. And key the cache
on everything that changes the response, including the `Authorization` header,
a cache keyed on URL alone will serve one user's data to another, which is the
worst bug in this entire guide.

##  What not to do

**Do not make an HTTP call without a timeout.** One hung dependency
exhausts your workers.

**Do not retry `POST` without an idempotency key.** You will duplicate
side effects.

**Do not retry 4xx.** The request will be just as wrong the second time.

**Do not use exponential backoff without jitter.** You synchronise your
own clients into a thundering herd.

**Do not log raw URLs.** Query strings carry credentials.

**Do not cache authenticated responses on the URL alone.** You will serve
one user another user's data.

**Do not let an upstream timeout exceed your own response budget.**

**Do not create a client per request.** You lose connection pooling and
pay a TLS handshake every time.

##  Performance notes

Connection reuse is the single biggest lever. A new TLS connection costs
one to three round trips before any bytes of your request move; a pooled
one costs zero. Create the client once at startup, store it in
`app.state`, and close it on shutdown.

```python title="one client for the process"
@app.on_startup
async def open_http_client():
    app.state["http"] = HTTPClient(base_url="https://api.example.com")


@app.on_shutdown
async def close_http_client():
    await app.state["http"].aclose()
```

`max_connections` caps total sockets and `max_keepalive_connections` caps
idle ones. Setting keepalive too low means reconnecting constantly;
setting total too high means you can overwhelm an upstream that has its
own limits.

Concurrent calls that do not depend on each other should be gathered rather
than awaited in sequence, three 100 ms calls take 300 ms sequentially and 100
ms concurrently. Use `asyncio.gather` with `return_exceptions=True` so one
failure does not cancel the others.

Statistics from `HTTPClientStats` are per-client and in memory. Export
them to your metrics system rather than reading them from an endpoint;
per-process counters are not a monitoring strategy.

##  Related

- [Retry helpers](/v0.x/guides/helpers/retry/): backoff, jitter, and retry policy in
  detail
- [Cache](/v0.x/guides/cache/): the backends the response cache uses
- [Network helpers](/v0.x/guides/helpers/network/): client IP handling and SSRF
  considerations
- [Concurrency](/v0.x/guides/concurrency/): gathering independent calls
- [Startup & Shutdown](/v0.x/guides/startups-and-shutdowns/): where to open and
  close the client
- [Error Handling](/v0.x/guides/error-handling/): turning upstream failures into
  your own status codes
