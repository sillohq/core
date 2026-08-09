---
title: Rate Limiting
description: Protect your sillo application with pluggable, distributed-ready rate limiting.
---

#  Rate Limiting

`sillo.security.ratelimit` provides first-party request rate limiting with
**pluggable algorithms** and **pluggable backends**. Use it to protect against
abuse, brute-force login attempts, and accidental client loops, and to enforce
fair usage quotas across your API.

##  Quick Start

```python
from sillo import SilloApp
from sillo.security import RateLimit

app = SilloApp()

# 100 requests per 60 seconds, per client IP, using the token-bucket strategy.
app.use(RateLimit(limit=100, window=60))
```

That's it. Clients exceeding the limit receive `429 Too Many Requests` with a
`Retry-After` header and `X-RateLimit-*` headers describing their quota.

##  Algorithms (Strategies)

| Strategy | Name | Behavior |
|---|---|---|
| Token bucket (default) | `"token"` | `limit` tokens refilled steadily over `window`; allows short bursts, smooth throttling |
| Fixed window | `"fixed"` | Counts requests per fixed `window`; resets completely each window (cheap, allows boundary bursts) |
| Sliding window | `"sliding"` | Counts only timestamps within the trailing `window`; no boundary double-count |

```python
app.use(RateLimit(limit=100, window=60, strategy="sliding"))
```

##  Backends

| Backend | Name | Use case |
|---|---|---|
| In-memory | `"memory"` (default) | Single instance / tests. Process-local, not shared across workers |
| Redis | `"redis"` | Multi-instance production. Shared state, atomic updates via Lua |
| Record | `"record"` | Persist to your database via `sillo.record` (no external cache needed) |

```python
# Shared across all app instances
app.use(RateLimit(limit=100, window=60, backend="redis"))
```

For the Record backend, register the model module with your Record setup:

```python
from sillo import SilloApp
from sillo.record import setup_record, DatabaseConfig
from sillo.security import RateLimit

app = SilloApp()
setup_record(
    app,
    DatabaseConfig.sqlite("app.db"),
    model_modules=["sillo.security.ratelimit.models"],
)
app.use(RateLimit(limit=100, window=60, backend="record"))
```

##  Configuration

`RateLimitConfig` (or the `RateLimit(...)` kwargs) accepts:

- **`limit`** (`int`) — max requests per `window` (default `60`)
- **`window`** (`int`) — time window in seconds (default `60`)
- **`strategy`** — `"token"` (default), `"fixed"`, `"sliding"`, or a strategy instance
- **`backend`** — `"memory"` (default), `"redis"`, `"record"`, or a backend instance
- **`key_func`** — `Callable[[Request], Optional[str]]` mapping a request to an
  identity. Return `None` to skip limiting. **Default: client IP**
  (falls back to `X-Forwarded-For`).
- **`namespace`** (`str`) — key prefix to avoid collisions (default `"sillo_rl"`)
- **`cost`** (`int`) — tokens consumed per request (default `1`; raise for heavy routes)
- **`include_headers`** (`bool`) — emit `X-RateLimit-*` headers (default `True`)
- **`fail_open`** (`bool`) — if the backend errors, allow the request
  (default `True`). Set `False` to fail closed (deny on backend failure).
- **`on_exceed`** — `"deny"` (default, returns `429`) or a callable
  `fn(request, response, result)` returning a custom response.

###  Custom identity (per API key, per user)

```python
def key_by_api_key(request):
    return request.headers.get("x-api-key")

app.use(RateLimit(limit=1000, window=60, key_func=key_by_api_key))
```

###  Custom deny response

```python
def custom_deny(request, response, result):
    return response.json(
        {"error": "slow_down", "retry_after": result.retry_after},
        status_code=429,
    )

app.use(RateLimit(limit=10, window=60, on_exceed=custom_deny))
```

###  Weighted (costly) routes

```python
# A report endpoint costs 10 tokens per hit
app.use(RateLimit(limit=100, window=60, cost=10))
```

##  Response Headers

When `include_headers=True`, every response carries:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 99
X-RateLimit-Reset: 1718668800
```

Denied responses additionally include `Retry-After: <seconds>`.

##  Failure Modes

- **`fail_open=True`** (default): if the backend is unreachable (Redis down,
  DB error), requests are **allowed** and no limit headers are attached.
  Prioritizes availability.
- **`fail_open=False`**: backend failure causes the request to **fail** (a
  `500` surfaces via the app error handler). Prioritizes correctness/safety.

##  How a request is decided

For each request, the middleware runs this sequence:

1. Compute the identity with `key_func` (default: client IP, falling back to `X-Forwarded-For`). If it returns `None`, the request passes with no counting.
2. Build the backend key as `namespace + ":" + identity`.
3. Ask the strategy + backend for a `RateLimitResult` (`allowed`, `limit`, `remaining`, `reset_at`, `retry_after`).
4. If `allowed`, attach `X-RateLimit-Limit` / `Remaining` / `Reset` and let the handler run.
5. If not `allowed`, call `on_exceed` — by default a `429` with `Retry-After` and the quota headers; a custom callable may return its own response.

Backends store an **opaque state dict**; strategies are stateless and interpret that state. That separation is why `memory`, `redis`, and `record` are drop-in replacements for each other.

##  A realistic scenario: protecting a login endpoint

Brute-force protection wants a tight limit keyed by the target account (or IP), strict enough to matter but `fail_open=True` so a Redis blip doesn't lock users out:

```python
from sillo import SilloApp
from sillo.security import RateLimit

app = SilloApp()

# 5 attempts per 60s per IP, fixed window (simple, predictable resets)
app.use(
    RateLimit(
        limit=5,
        window=60,
        strategy="fixed",
        backend="memory",
        fail_open=True,
        namespace="login",
        key_func=lambda r: r.client.host if r.client else None,
    )
)


@app.post("/login")
async def login(request, response):
    ...
```

Keyed by IP, the limit applies across every login attempt from that address. Swap `backend="redis"` and the same counter is shared across all app instances behind a load balancer.

##  Works with

- **`sillo.security` Shield/CSRF/CORS** — rate limiting is a sibling middleware; order them so rate limiting runs early (cheap to reject) and CSRF validation runs only on accepted requests.
- **Authentication / sessions** — pass `key_func` that reads the authenticated identity (`request.state.user.id`) to rate-limit *per account* rather than per IP, which is harder for an attacker to rotate.
- **Dependency injection** — a dependency can compute the identity and stash it on `request.state` for `key_func` to read, keeping route handlers free of limiting logic.
- **`sillo.record`** — the `"record"` backend persists counters as `sillo_ratelimit_counters` rows; no Redis required, at the cost of DB round-trips per request.

##  Testing

Drive the middleware through `TestClient` and assert status codes and headers. Memory backend state is process-local, so repeated `client.get` calls accumulate against the same counter.

```python
from sillo import SilloApp
from sillo.security import RateLimit, RateLimitConfig
from sillo.testclient import TestClient


def test_allows_up_to_limit_then_429():
    app = SilloApp()
    app.use(RateLimit(limit=2, window=60, key_func=lambda r: "tester"))

    @app.get("/")
    async def home(request, response):
        return {"ok": True}

    client = TestClient(app)
    assert client.get("/").status_code == 200
    assert client.get("/").status_code == 200
    denied = client.get("/")
    assert denied.status_code == 429
    assert denied.headers["Retry-After"].isdigit()


def test_quota_headers():
    app = SilloApp()
    app.use(RateLimit(limit=2, window=60, key_func=lambda r: "h"))

    @app.get("/")
    async def home(request, response):
        return {"ok": True}

    r = TestClient(app).get("/")
    assert r.headers["X-RateLimit-Limit"] == "2"
    assert r.headers["X-RateLimit-Remaining"] == "1"
```

To reset between cases, call `backend.clear()` (the memory backend supports it) or use a fresh `SilloApp()` per test. For `fail_open=False`, assert that taking the backend down yields a `500` rather than `429`.

##  Production considerations

- **Backend choice** — `memory` is per-process; behind multiple workers/instances it under-counts, so use `redis` or `record` for real fairness.
- **`fail_open`** — `True` favors availability (a backend outage lets traffic through); `False` favors safety (outage denies everything). Pick based on what a flood costs you.
- **Key design** — IP-only limits are easy to evade by rotating addresses; per-account or per-API-key keys are stronger for abuse control.
- **`X-RateLimit-Reset`** is a Unix timestamp; clients use it to schedule retries. Keep `include_headers=True` so well-behaved clients back off instead of hammering.
- **Cost** — set `cost > 1` on expensive routes so one heavy call consumes more of the quota.

##  Design Notes

- Strategies are **stateless**; backends store opaque state. This keeps
  memory, Redis, and Record interchangeable.
- Redis updates run inside a **Lua script** so concurrent hits from different
  workers can't double-count.
- The token-bucket refill rate is `limit / window` tokens per second.

Built with ❤️ by the [@sillohq](https://github.com/sillohq) community.
