---
title: Rate Limiting
description: Protect your sillo application with pluggable, distributed-ready rate limiting.
---

# Rate Limiting

`sillo.security.ratelimit` provides first-party request rate limiting with
**pluggable algorithms** and **pluggable backends**. Use it to protect against
abuse, brute-force login attempts, and accidental client loops, and to enforce
fair usage quotas across your API.

## Quick Start

```python
from sillo import silloApp
from sillo.security import RateLimit

app = silloApp()

# 100 requests per 60 seconds, per client IP, using the token-bucket strategy.
app.use(RateLimit(limit=100, window=60))
```

That's it. Clients exceeding the limit receive `429 Too Many Requests` with a
`Retry-After` header and `X-RateLimit-*` headers describing their quota.

## Algorithms (Strategies)

| Strategy | Name | Behavior |
|---|---|---|
| Token bucket (default) | `"token"` | `limit` tokens refilled steadily over `window`; allows short bursts, smooth throttling |
| Fixed window | `"fixed"` | Counts requests per fixed `window`; resets completely each window (cheap, allows boundary bursts) |
| Sliding window | `"sliding"` | Counts only timestamps within the trailing `window`; no boundary double-count |

```python
app.use(RateLimit(limit=100, window=60, strategy="sliding"))
```

## Backends

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
from sillo import silloApp
from sillo.record import setup_record, DatabaseConfig
from sillo.security import RateLimit

app = silloApp()
setup_record(
    app,
    DatabaseConfig.sqlite("app.db"),
    model_modules=["sillo.security.ratelimit.models"],
)
app.use(RateLimit(limit=100, window=60, backend="record"))
```

## Configuration

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

### Custom identity (per API key, per user)

```python
def key_by_api_key(request):
    return request.headers.get("x-api-key")

app.use(RateLimit(limit=1000, window=60, key_func=key_by_api_key))
```

### Custom deny response

```python
def custom_deny(request, response, result):
    return response.json(
        {"error": "slow_down", "retry_after": result.retry_after},
        status_code=429,
    )

app.use(RateLimit(limit=10, window=60, on_exceed=custom_deny))
```

### Weighted (costly) routes

```python
# A report endpoint costs 10 tokens per hit
app.use(RateLimit(limit=100, window=60, cost=10))
```

## Response Headers

When `include_headers=True`, every response carries:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 99
X-RateLimit-Reset: 1718668800
```

Denied responses additionally include `Retry-After: <seconds>`.

## Failure Modes

- **`fail_open=True`** (default): if the backend is unreachable (Redis down,
  DB error), requests are **allowed** and no limit headers are attached.
  Prioritizes availability.
- **`fail_open=False`**: backend failure causes the request to **fail** (a
  `500` surfaces via the app error handler). Prioritizes correctness/safety.

## Design Notes

- Strategies are **stateless**; backends store opaque state. This keeps
  memory, Redis, and Record interchangeable.
- Redis updates run inside a **Lua script** so concurrent hits from different
  workers can't double-count.
- The token-bucket refill rate is `limit / window` tokens per second.

Built with ❤️ by the [@sillo-labs](https://github.com/sillo-labs) community.
