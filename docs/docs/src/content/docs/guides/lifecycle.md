---
title: Request Lifecycle
description: Request ID generation, context management, and lifecycle tracking in sillo.
---

# Request Lifecycle

The `sillo.lifecycle` module provides utilities for managing the request lifecycle — generating unique request IDs, storing request-scoped context, and tracking request metadata.

## Installation

`sillo.lifecycle` is a first-party module included with sillo. No extra install required.

## Request ID Middleware

Automatically generates or extracts unique request IDs per request, stored in `request.state` and included in response headers.

### Basic Usage

```python
from sillo import silloApp
from sillo.lifecycle import RequestId

app = silloApp()

app.use(RequestId())

@app.get("/")
async def home(request, response):
    req_id = getattr(request.state, "request_id", None)
    return {"request_id": req_id}
```

### Configuration

```python
app.use(RequestId(
    header_name="X-Request-ID",       # Header name (default)
    force_generate=False,              # Use incoming ID if present
    store_in_request=True,             # Store in request.state
    request_attribute_name="request_id",  # Attribute name
    include_in_response=True,          # Include in response headers
))
```

### Helper Functions

```python
from sillo.lifecycle import (
    generate_request_id,
    get_or_generate_request_id,
    get_request_id_from_request,
    validate_request_id,
)

new_id = generate_request_id()                      # "a1b2c3d4-..."
is_valid = validate_request_id(new_id)               # True
stored = get_request_id_from_request(request)        # from request.state
```

## Request Context

`RequestContext` is a request-scoped dict-like context manager that stores data tied to the current request lifecycle. Accessible anywhere in the request chain.

```python
from sillo.lifecycle import RequestContext

@app.get("/timed")
async def timed_handler(request, response):
    with RequestContext() as ctx:
        ctx["start"] = time.monotonic()
        result = await do_work()
        elapsed = time.monotonic() - ctx["start"]
        ctx["elapsed"] = elapsed
        return {"elapsed": elapsed, "result": result}
```

### Access from anywhere

```python
ctx = RequestContext.current()
if ctx:
    print(ctx.get("user_id"))
```

### API Reference

| Method | Description |
|---|---|
| `ctx[key]` | Get/set/delete item |
| `ctx.get(key, default)` | Get with default fallback |
| `ctx.set(key, value)` | Set item |
| `ctx.data` | Return the underlying dict |
| `RequestContext.current()` | Get current context (or None) |

Built with ❤️ by [@sillo-labs](https://github.com/sillo-labs).
