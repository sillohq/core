---
title: Request Lifecycle
description: Request ID generation and request-scoped context with the sillo.lifecycle module.
---

# Request Lifecycle

The `sillo.lifecycle` module provides first‑party middleware and helpers for request‑scoped concerns:

- **`RequestId`** — generates and propagates a unique ID per request
- **`RequestContext`** — a request‑scoped context manager for sharing data across your call chain

## Quick Start

```python
from sillo import silloApp
from sillo.lifecycle import RequestId

app = silloApp()

app.use(RequestId(
    header_name="X-Request-ID",
    force_generate=False,
    store_in_request=True,
    include_in_response=True,
))

@app.get("/")
async def home(request, response):
    req_id = getattr(request.state, "request_id", None)
    return {"message": "Hello with Request ID!", "request_id": req_id}
```

Every request now carries a unique request ID usable for tracing and debugging.

## RequestId Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `header_name` | `str` | `"X-Request-ID"` | Header used for extraction and setting |
| `force_generate` | `bool` | `False` | Always generate a new request ID instead of reusing a client‑supplied one |
| `store_in_request` | `bool` | `True` | Store the request ID on the request object |
| `request_attribute_name` | `str` | `"request_id"` | Attribute name used to store the ID on the request |
| `include_in_response` | `bool` | `True` | Echo the request ID back in the response headers |

## Usage Examples

### Basic Usage

```python
from sillo import silloApp
from sillo.lifecycle import RequestId

app = silloApp()
app.use(RequestId())
```

### Custom Configuration

```python
from sillo import silloApp
from sillo.lifecycle import RequestId

app = silloApp()

app.use(
    RequestId(
        header_name="X-Correlation-ID",
        force_generate=True,
        store_in_request=True,
        include_in_response=True,
        request_attribute_name="req_id",
    )
)
```

### Using Helper Functions

```python
from sillo.lifecycle import (
    generate_request_id,
    get_or_generate_request_id,
    validate_request_id,
)

new_id = generate_request_id()
req_id = get_or_generate_request_id(request)
is_valid = validate_request_id(some_request_id)
```

### Accessing Request ID in Handlers

```python
@app.get("/api/users")
async def get_users(request, response):
    request_id = getattr(request, "request_id", None)
    request_id = request.headers.get("X-Request-ID")
    from sillo.lifecycle import get_request_id_from_request
    request_id = get_request_id_from_request(request)
    return {"users": [], "request_id": request_id}
```

## Features

- **Automatic Generation**: UUID4‑based request IDs
- **Header Support**: Extracts IDs from incoming request headers
- **Request Storage**: Stores IDs on the request object for easy access
- **Response Headers**: Echoes IDs back for client‑side tracing
- **Customizable**: Configurable header name, attribute name, generation behavior
- **Validation**: Built‑in format validation
- **Thread Safe**: Safe under concurrent ASGI execution

## RequestContext

`RequestContext` is a request‑scoped context manager backed by a `ContextVar`. Anything you set inside the `with` block is available anywhere in the same request, without threading objects through every function call.

```python
from sillo.lifecycle import RequestContext

@app.get("/dashboard")
async def dashboard(request, response):
    with RequestContext() as ctx:
        ctx["user_id"] = 42
        ctx["trace"] = "abc123"
        # ... call deeper functions that read RequestContext()
        return {"ok": True}

def some_deep_helper():
    ctx = RequestContext()
    user_id = ctx.get("user_id")
    return user_id
```

`RequestContext()` always returns the current context dict (creating an empty one if none is active), so you can read it from anywhere in the request without passing it around.

## Advanced Usage

### Logging with Request ID

```python
import logging
from sillo.lifecycle import RequestId

app = silloApp()
app.use(RequestId())

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] - %(message)s'
)

@app.middleware
async def logging_middleware(request, response, call_next):
    request_id = getattr(request, "request_id", "unknown")
    logger = logging.LoggerAdapter(logging.getLogger(__name__), {"request_id": request_id})
    logger.info(f"Processing request: {request.method} {request.url.path}")
    response = await call_next()
    logger.info(f"Request completed with status: {response.status_code}")
    return response
```

### Custom Request ID Format

```python
import uuid
from sillo.lifecycle import RequestIdMiddleware

class CustomRequestIdMiddleware(RequestIdMiddleware):
    def __init__(self, prefix: str = "req", **kwargs):
        super().__init__(**kwargs)
        self.prefix = prefix

    def generate_request_id(self) -> str:
        return f"{self.prefix}-{uuid.uuid4().hex[:8]}"

app.use(CustomRequestIdMiddleware(prefix="api"))
```

### Distributed Tracing Integration

```python
from sillo.lifecycle import RequestId
import opentelemetry.trace as trace

app = silloApp()
app.use(RequestId())

@app.middleware
async def tracing_middleware(request, response, call_next):
    request_id = getattr(request, "request_id", None)
    span = trace.get_current_span()
    if span and request_id:
        span.set_attribute("request.id", request_id)
    return await call_next()
```

### Request ID Propagation

```python
import httpx
from sillo.lifecycle import get_request_id_from_request

@app.get("/api/external")
async def call_external_api(request, response):
    request_id = get_request_id_from_request(request)
    async with httpx.AsyncClient() as client:
        external_response = await client.get(
            "https://api.example.com/data",
            headers={"X-Request-ID": request_id},
        )
    return {"external_data": external_response.json(), "request_id": request_id}
```

## Best Practices

1. **Include request IDs in logs** for better debugging and tracing
2. **Use consistent header names** across your microservices
3. **Store request IDs early** in the middleware chain
4. **Consider different header names** for internal vs external IDs
5. **Validate request IDs** from external sources before trusting them
6. **Propagate request IDs** to downstream services for distributed tracing

### Production Configuration

```python
from sillo import silloApp
from sillo.lifecycle import RequestId
import logging

app = silloApp()

app.use(
    RequestId(
        header_name="X-Request-ID",
        force_generate=False,
        store_in_request=True,
        include_in_response=True,
    )
)

logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "request_id": "%(request_id)s", "message": "%(message)s"}'
)

@app.middleware
async def structured_logging(request, response, call_next):
    request_id = getattr(request, "request_id", "unknown")
    logger = logging.LoggerAdapter(logging.getLogger(__name__), {"request_id": request_id})
    start_time = time.time()
    logger.info(f"Request started: {request.method} {request.url.path}")
    try:
        response = await call_next()
        duration = time.time() - start_time
        logger.info(f"Request completed: {response.status_code} in {duration:.3f}s")
        return response
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Request failed: {str(e)} in {duration:.3f}s")
        raise
```

## Integration Examples

### With Database Queries

```python
import asyncpg
from sillo.lifecycle import get_request_id_from_request

@app.get("/api/users/{user_id}")
async def get_user(request, response, user_id: int):
    request_id = get_request_id_from_request(request)
    async with asyncpg.connect("postgresql://...") as conn:
        user = await conn.fetchrow(
            "SELECT * FROM users WHERE id = $1 -- Request ID: $2",
            user_id, request_id,
        )
    return {"user": dict(user), "request_id": request_id}
```

### With Background Tasks

```python
from sillo.lifecycle import get_request_id_from_request
import asyncio

@app.post("/api/process")
async def start_processing(request, response):
    request_id = get_request_id_from_request(request)
    data = await request.json
    asyncio.create_task(process_data_async(data, request_id))
    return {"status": "processing", "request_id": request_id}

async def process_data_async(data, request_id):
    logger = logging.LoggerAdapter(logging.getLogger(__name__), {"request_id": request_id})
    logger.info("Starting background processing")
    logger.info("Background processing completed")
```

### With Error Handling

```python
from sillo.exceptions import HTTPException
from sillo.lifecycle import get_request_id_from_request

@app.add_exception_handler(HTTPException)
async def http_exception_handler(request, response, exc):
    request_id = get_request_id_from_request(request)
    return {
        "error": exc.detail,
        "status_code": exc.status_code,
        "request_id": request_id,
        "timestamp": datetime.utcnow().isoformat(),
    }, exc.status_code
```

## Troubleshooting

### Request ID Not Appearing

1. Ensure the middleware is added to your app
2. Check that `store_in_request=True`
3. Verify the middleware is added early in the chain

### Duplicate Request IDs

1. Check if `force_generate=True` is needed
2. Verify client‑supplied IDs are unique

### Performance Issues

1. Consider shorter ID formats
2. Use custom ID generation for better performance
3. Profile your application to find bottlenecks

Built with ❤️ by the [@sillo-labs](https://github.com/sillo-labs) community.
