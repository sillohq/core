---
title: Request Lifecycle
description: Request ID generation and request-scoped context with the sillo.lifecycle module.
---

#  Request Lifecycle

The `sillo.lifecycle` module provides first‑party middleware and helpers for request‑scoped concerns:

- **`RequestId`**: generates and propagates a unique ID per request
- **`RequestContext`**: a request‑scoped context manager for sharing data
  across your call chain

##  Quick Start

```python
from sillo import SilloApp
from sillo.http.lifecycle import RequestId

app = SilloApp()

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

##  RequestId Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `header_name` | `str` | `"X-Request-ID"` | Header used for extraction and setting |
| `force_generate` | `bool` | `False` | Always generate a new request ID instead of reusing a client‑supplied one |
| `store_in_request` | `bool` | `True` | Store the request ID on the request object |
| `request_attribute_name` | `str` | `"request_id"` | Attribute name used to store the ID on the request |
| `include_in_response` | `bool` | `True` | Echo the request ID back in the response headers |

##  Usage Examples

###  Basic Usage

```python
from sillo import SilloApp
from sillo.http.lifecycle import RequestId

app = SilloApp()
app.use(RequestId())
```

###  Custom Configuration

```python
from sillo import SilloApp
from sillo.http.lifecycle import RequestId

app = SilloApp()

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

###  Using Helper Functions

```python
from sillo.http.lifecycle import (
    generate_request_id,
    get_or_generate_request_id,
    validate_request_id,
)

new_id = generate_request_id()
req_id = get_or_generate_request_id(request)
is_valid = validate_request_id(some_request_id)
```

###  Accessing Request ID in Handlers

```python
@app.get("/api/users")
async def get_users(request, response):
    request_id = getattr(request.state, "request_id", None)
    request_id = request.headers.get("X-Request-ID")
    from sillo.http.lifecycle import get_request_id_from_request
    request_id = get_request_id_from_request(request)
    return {"users": [], "request_id": request_id}
```

##  Features

- **Automatic Generation**: UUID4‑based request IDs
- **Header Support**: Extracts IDs from incoming request headers
- **Request Storage**: Stores IDs on the request object for easy access
- **Response Headers**: Echoes IDs back for client‑side tracing
- **Customizable**: Configurable header name, attribute name, generation behavior
- **Validation**: Built‑in format validation
- **Thread Safe**: Safe under concurrent ASGI execution

##  RequestContext

`RequestContext` is a request‑scoped context manager backed by a `ContextVar`. Anything you set inside the `with` block is available anywhere in the same request, without threading objects through every function call.

```python
from sillo.http.lifecycle import RequestContext

@app.get("/dashboard")
async def dashboard(request, response):
    with RequestContext() as ctx:
        ctx["user_id"] = 42
        ctx["trace"] = "abc123"
        result = some_deep_helper()      # reads the same context
        return {"ok": True, "user": result}

def some_deep_helper():
    # RequestContext.current() returns the active context for this request,
    # or None if no block is active on the current task.
    ctx = RequestContext.current()
    if ctx is None:
        return None
    return ctx.get("user_id")
```

`RequestContext()` (used as a `with` block) creates *and activates* a new
context for the current request. To read it later from a function that did not
open the block, call the classmethod `RequestContext.current()`. Do **not**
write `RequestContext()` outside a `with` block, because that constructs a
fresh, empty context instead of returning the active one. The context resets
automatically when the `with` block exits, so values do not leak across
requests.

##  Advanced Usage

###  Logging with Request ID

```python
import logging
from sillo.http.lifecycle import RequestId

app = SilloApp()
app.use(RequestId())

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] - %(message)s'
)

async def logging_middleware(request, response, call_next):
    request_id = getattr(request.state, "request_id", "unknown")
    logger = logging.LoggerAdapter(logging.getLogger(__name__), {"request_id": request_id})
    logger.info(f"Processing request: {request.method} {request.url.path}")
    response = await call_next()
    logger.info(f"Request completed with status: {response.status_code}")
    return response

app.use(logging_middleware)
```

###  Custom Request ID Format

```python
import uuid
from sillo.http.lifecycle import RequestIdMiddleware

class CustomRequestIdMiddleware(RequestIdMiddleware):
    def __init__(self, prefix: str = "req", **kwargs):
        super().__init__(**kwargs)
        self.prefix = prefix

    def generate_request_id(self) -> str:
        return f"{self.prefix}-{uuid.uuid4().hex[:8]}"

app.use(CustomRequestIdMiddleware(prefix="api"))
```

###  Distributed Tracing Integration

```python
from sillo.http.lifecycle import RequestId
import opentelemetry.trace as trace

app = SilloApp()
app.use(RequestId())

async def tracing_middleware(request, response, call_next):
    request_id = getattr(request.state, "request_id", None)
    span = trace.get_current_span()
    if span and request_id:
        span.set_attribute("request.id", request_id)
    return await call_next()

app.use(tracing_middleware)
```

###  Request ID Propagation

```python
import httpx
from sillo.http.lifecycle import get_request_id_from_request

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

##  Best Practices

1. **Include request IDs in logs** for better debugging and tracing
2. **Use consistent header names** across your microservices
3. **Store request IDs early** in the middleware chain
4. **Consider different header names** for internal vs external IDs
5. **Validate request IDs** from external sources before trusting them
6. **Propagate request IDs** to downstream services for distributed tracing

###  Production Configuration

```python
from sillo import SilloApp
from sillo.http.lifecycle import RequestId
import logging

app = SilloApp()

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

async def structured_logging(request, response, call_next):
    request_id = getattr(request.state, "request_id", "unknown")
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

app.use(structured_logging)
```

##  Integration Examples

###  With Database Queries

```python
import asyncpg
from sillo.http.lifecycle import get_request_id_from_request

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

###  With Background Tasks

```python
from sillo.http.lifecycle import get_request_id_from_request
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

###  With Error Handling

```python
from sillo.exceptions import HTTPException
from sillo.http.lifecycle import get_request_id_from_request

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

##  Troubleshooting

###  Request ID Not Appearing

1. Ensure the middleware is added to your app
2. Check that `store_in_request=True`
3. Verify the middleware is added early in the chain

###  Duplicate Request IDs

1. Check if `force_generate=True` is needed
2. Verify client‑supplied IDs are unique

###  Performance Issues

1. Consider shorter ID formats
2. Use custom ID generation for better performance
3. Profile your application to find bottlenecks

Built with ❤️ by the [@sillohq](https://github.com/sillohq) community.


##  The full path of a request

Understanding the order explains most "why does this not work" questions,
because nearly all of them are something happening earlier or later than
expected.

1. The ASGI server accepts the connection and builds a `scope`
2. sillo constructs a `Request`
3. Middleware runs, outermost first
4. The router matches the path and extracts path parameters
5. Dependencies resolve
6. Query, header, cookie, and path values are validated
7. The body is read and validated, if anything declared it
8. Your handler runs
9. `response_model` validates the return value
10. The result is encoded
11. Middleware unwinds, innermost first
12. The server writes the response

Four consequences worth internalising.

**Middleware sees raw values.** It runs before validation, so
`request.query_params["page"]` is the string `"2"`, not the integer `2`.

**A validation failure skips your handler entirely.** Nothing in it runs,
so logging rejected requests belongs in an exception handler.

**The body is read at most once and only if requested.** A route that
declares no body never awaits it, which is why an endpoint ignoring a
posted body is not slowed by it. Reading it twice requires caching it
yourself.

**Middleware unwinds in reverse on the way out.** The first middleware
registered is the last to touch the response, which is why response
rewriting belongs innermost and header injection outermost.

##  Where to put what

| You want to… | Put it in |
|---|---|
| Run on every request, regardless of route | [Middleware](/v0.x/guides/middleware/) |
| Produce a value the handler uses | [A dependency](/v0.x/guides/dependency-injection/) |
| Reject bad input | [Validation](/v0.x/guides/validation/) |
| Run once per process | [A lifespan hook](/v0.x/guides/startups-and-shutdowns/) |
| Do work after responding | [A background task](/v0.x/guides/work/background/) |

The most common misplacement is putting per-request work in a lifespan
hook, or per-process work in a dependency. The first produces stale
shared state; the second recreates something expensive on every request.

##  Cancellation

If a client disconnects mid-request, the server cancels the task running
your handler. The handler sees `asyncio.CancelledError` at its next
`await`.

That means work after the disconnect does not happen, and a database
transaction in flight is rolled back by the connection's cleanup. It also
means anything in a `finally` still runs, which is where cleanup belongs.

Never suppress `CancelledError`. Catching it to "keep going" leaves a
task running after its response can no longer be delivered, and at scale
those accumulate into a process that is busy doing nothing useful.


##  Timing and where latency comes from

Measuring the handler alone will mislead you. A request spends time in
five places, and the handler is often not the largest.

**The server** parsing the request, small, and proportional to header count and
body size.

**Middleware**: every layer, on every request, including 404s. Ten layers at
one millisecond each is ten milliseconds on your fastest endpoint, and it does
not appear in handler timings.

**Dependency resolution**. Anything that queries in a dependency is latency
before your handler starts.

**The handler**, usually dominated by whatever it awaits, not by your code.

**Serialization**, proportional to response size, and pure CPU on the event
loop.

The way to find the real cost is to measure the whole thing at the
outermost middleware and compare it against the handler's own timing. A
large gap points at the layers around it, which is exactly where people
do not look.

##  Debugging a request end to end

Three tools, in the order they usually help.

`sillo urls` confirms the route exists and matches what you think.

A request id threaded through every log line ties the messages from middleware,
handler, and background work into one story. See [Request
Info](/v0.x/guides/request-info/).

The test client reproduces a request in-process, which removes the
network, the proxy, and the server from consideration. If it works there
and not in production, the difference is one of those three, and that is
a much smaller search.


##  Streaming and long-lived requests

Not every request follows the linear path above. A [streamed
response](/v0.x/guides/streaming-response/) returns from the handler before the body
has finished being produced, so middleware unwinds while data is still being
written. Anything measuring duration in middleware will report the wrong
number, and anything closing a resource there will close it too early.

A [WebSocket](/v0.x/guides/websockets/) leaves the request lifecycle entirely
after the handshake. HTTP middleware does not run per message, and the
connection may outlive many ordinary requests.


##  Summary

The order is fixed and knowable: middleware outward-in, routing, dependencies,
validation, handler, response validation, encoding, middleware inward-out.
Nearly every confusing behaviour in an application resolves to something
running at a different point in that sequence than expected, usually middleware
seeing unvalidated values, or per-process state being built per request.


##  Related

- [Middleware](/v0.x/guides/middleware/): the layers wrapping every request
- [Routing](/v0.x/guides/routing/): how a path becomes a handler
- [Validation](/v0.x/guides/validation/): where input is checked
- [Handlers](/v0.x/guides/handlers/): what runs at the centre
- [Concurrency](/v0.x/guides/concurrency/): what the loop is doing meanwhile
- [Startup & Shutdown](/v0.x/guides/startups-and-shutdowns/): what happens before
  the first request


##  Background work happens after the response

Anything you launch with [`BackgroundTask`](/v0.x/guides/work/background/) runs
after the response has been sent, on the same event loop. Two consequences: the
client is not waiting for it, which is the point; and it is not covered by any
middleware, so request-scoped context (`request.state`, a correlation id, an
open transaction) is gone unless you captured what you need before launching.

Capture values, not the request. A closure holding the request object
keeps the whole request alive, including its body buffer, for as long as
the task runs.
