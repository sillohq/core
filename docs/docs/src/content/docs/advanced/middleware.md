---
title: "Middleware Architecture"
description: "BaseMiddleware, ASGI bridge, middleware chain, execution order"
---

> Internal engineering reference for the sillo middleware subsystem.
>
> **Source files covered:**
>
> | File | Primary responsibility |
> |------|----------------------|
> | `core/sillo/middleware/base.py` | `BaseMiddleware` — dispatch-style two-hook base class |
> | `core/sillo/middleware/gzip.py` | `GZipMiddleware` / `GZipResponder` — ASGI-native compression |
> | `core/sillo/_internals/_middleware.py` | `ASGIRequestResponseBridge`, `_CachedRequest`, `DefineMiddleware`, `_StreamingResponse`, `wrap_middleware()` |
> | `core/sillo/middleware/__init__.py` | Re-exports `BaseMiddleware`, `CORSMiddleware`, `CSRFMiddleware` |
> | `core/sillo/middleware/utils.py` | `use_for_route()` — conditional-route decorator |
> | `core/sillo/application.py` | `SilloApp.use()` — application-level middleware registration |
> | `core/sillo/core/routing/router.py` | `Router.use()`, `Router.build_middleware_stack()` — router-level middleware |
> | `core/sillo/types.py` | `ASGIApp`, `MiddlewareType`, `Scope`, `Receive`, `Send` type aliases |

---

## 1. Conceptual Overview

Sillo's middleware system sits between the ASGI server (uvicorn, granian, daphne) and
the application's route handlers. Every HTTP request passes through zero or more
middleware layers before reaching a handler, and every response passes back through
those same layers in reverse order. This is the classic **onion model**.

Sillo supports two distinct middleware authoring styles that serve different needs:

| Style | Authoring interface | Runs at | Example use case |
|-------|-------------------|---------|------------------|
| **Dispatch-style** | `async def mw(request, response, call_next)` | Request/Response abstraction level | Auth, logging, rate limiting |
| **ASGI-native** | `async def mw(scope, receive, send)` | Raw ASGI protocol level | GZip compression, WebSocket interception |

The framework bridges dispatch-style middleware into the ASGI pipeline via
`ASGIRequestResponseBridge`, so both styles compose seamlessly inside the same chain.

---

## 2. The Two Worlds: ASGI vs Dispatch Middleware

### 2.1 The ASGI Protocol

Every ASGI application is a callable with this signature:

```python
# core/sillo/types.py
ASGIApp = typing.Callable[[Scope, Receive, Send], typing.Awaitable[Any]]

Scope   = typing.MutableMapping[str, typing.Any]   # connection metadata
Receive = typing.Callable[[], typing.Awaitable[Message]]  # inbound channel
Send    = typing.Callable[[Message], typing.Awaitable[None]]  # outbound channel
Message = typing.MutableMapping[str, typing.Any]   # protocol message dict
```

An ASGI middleware wraps an inner `ASGIApp` and intercepts `scope`, `receive`, and/or
`send` before delegating to the wrapped app:

```python
class RawASGIMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope, receive, send):
        # inspect scope, modify receive/send, then:
        await self.app(scope, receive, send)
```

### 2.2 The Dispatch Abstraction

Most application developers don't want to think in terms of ASGI message dicts. Sillo's
dispatch style provides a friendlier interface:

```python
# core/sillo/types.py
MiddlewareType = typing.Callable[
    [Request, Response, RequestResponseEndpoint],
    typing.Awaitable[Response | StreamingResponse],
]
```

A dispatch-style middleware receives high-level `Request` and `Response` objects plus a
`call_next` callable that advances the chain:

```python
async def logging_middleware(request: Request, response: Response, call_next):
    start = time.monotonic()
    result = await call_next()
    elapsed = time.monotonic() - start
    print(f"{request.method} {request.url.path} took {elapsed:.3f}s")
    return result
```

### 2.3 Why Two Worlds?

The bridge exists because:

1. **Developer ergonomics** — dispatch-style is far easier to write and debug for the
   90% case (read a header, call next, modify a response header).
2. **Protocol power** — ASGI-native middleware can intercept WebSocket handshakes,
   manipulate streaming bodies chunk-by-chunk, and inspect the raw scope dict. GZip
   compression requires this level of access.
3. **Composability** — `ASGIRequestResponseBridge` lets both styles mix in a single
   chain without either side knowing about the other.

---

## 3. Onion Model — How the Chain Works

The middleware stack is an onion. Each layer wraps the next. The outermost middleware
sees the request first and the response last.

```mermaid
graph TB
    subgraph "Middleware Onion Model"
        direction TB
        CLIENT["🌐 Client"]
        M1["Middleware A\n(outermost)"]
        M2["Middleware B"]
        M3["Middleware C"]
        BRIDGE["ASGIRequestResponseBridge"]
        HANDLER["Route Handler"]

        CLIENT -->|"HTTP Request"| M1
        M1 -->|"request ↓"| M2
        M2 -->|"request ↓"| M3
        M3 -->|"request ↓"| BRIDGE
        BRIDGE -->|"request ↓"| HANDLER
        HANDLER -->|"response ↑"| BRIDGE
        BRIDGE -->|"response ↑"| M3
        M3 -->|"response ↑"| M2
        M2 -->|"response ↑"| M1
        M1 -->|"HTTP Response"| CLIENT
    end
```

**Key insight:** middleware added *first* via `app.use()` runs *outermost* (sees
request first, response last). This is because `app.use()` inserts at position 0
of the middleware list, and chain construction iterates in reverse — see §5.

---

## 4. DefineMiddleware — The Deferred Descriptor

**File:** `core/sillo/_internals/_middleware.py` (lines 27–93)

`DefineMiddleware` is a container that pairs a middleware factory with its constructor
arguments. It does **not** instantiate the middleware — it just stores the recipe.

```python
class DefineMiddleware:
    """Container that pairs a middleware factory with its positional and keyword arguments."""

    def __init__(self, cls: MiddlewareFactory, *args: Any, **kwargs: Any) -> None:
        self.cls = cls        # the middleware class or factory callable
        self.args = args      # positional args for the constructor
        self.kwargs = kwargs  # keyword args for the constructor

    def __iter__(self) -> Iterator[Any]:
        """Yield (cls, args, kwargs) — enables tuple unpacking."""
        as_tuple = (self.cls, self.args, self.kwargs)
        return iter(as_tuple)
```

### Why a Descriptor?

Middleware is registered at definition time but instantiated at request time (or more
precisely, when `build_middleware_stack` runs). `DefineMiddleware` enables:

- **Deferred construction** — the middleware class isn't called until the stack is built.
- **Uniform interface** — both ASGI-native middleware and dispatch-style middleware
  (wrapped via `wrap_middleware`) produce a `DefineMiddleware` with the same shape.
- **Unpacking** — `for cls, args, kwargs in reversed(middleware)` works because
  `__iter__` yields a 3-tuple.

```python
# Example: creating a DefineMiddleware explicitly
dm = DefineMiddleware(GZipMiddleware, minimum_size=1024, compresslevel=6)
cls, args, kwargs = dm
# cls == GZipMiddleware
# args == ()
# kwargs == {"minimum_size": 1024, "compresslevel": 6}
```

---

## 5. Chain Construction — Reversed Wrapping

The middleware chain is built by iterating the middleware list **in reverse** and
wrapping each layer around the previous result.

### 5.1 The Core Loop

```python
# core/sillo/application.py, SilloApp.handle_request() (lines 1189–1204)
app = self.app
middleware = (
    [Middleware(ASGIRequestResponseBridge, dispatch=ServerErrorMiddleware(...))]
    + self.http_middleware
    + [Middleware(ASGIRequestResponseBridge, dispatch=self.exceptions_handler)]
)
for cls, args, kwargs in reversed(middleware):
    app = cls(app, *args, **kwargs)
```

And in the router:

```python
# core/sillo/core/routing/router.py, Router.build_middleware_stack() (lines 909–932)
def build_middleware_stack(self, app: ASGIApp) -> ASGIApp:
    for cls, args, kwargs in reversed(self.middleware):
        app = cls(app, *args, **kwargs)
    return app
```

### 5.2 Why Reverse?

Consider three middleware registered in order `[A, B, C]`:

```mermaid
graph LR
    subgraph "Registration order: [A, B, C]"
        direction LR
        REG_A["A (index 0)"] --> REG_B["B (index 1)"] --> REG_C["C (index 2)"]
    end
```

After `reversed([A, B, C])`, iteration produces `C, B, A`:

```mermaid
graph TB
    subgraph "Wrapping process (reversed iteration)"
        direction TB
        STEP1["Step 1: app = C(inner_app)"]
        STEP2["Step 2: app = B(C(inner_app))"]
        STEP3["Step 3: app = A(B(C(inner_app)))"]
        STEP1 --> STEP2 --> STEP3
    end
```

Result at runtime: `A` is outermost, `C` is innermost. Request flows `A → B → C → handler`.
The first middleware registered is the first to see every request.

### 5.3 The Full Stack at the Application Level

```mermaid
graph TB
    subgraph "SilloApp middleware assembly"
        direction TB
        SE["ServerErrorMiddleware\n(via Bridge) — outermost"]
        MW1["User Middleware 1\n(first registered)"]
        MW2["User Middleware 2"]
        MWn["User Middleware N\n(last registered)"]
        EX["ExceptionsHandler\n(via Bridge) — innermost"]
        ROUTER["Router → Route Handler"]

        SE --> MW1 --> MW2 --> MWn --> EX --> ROUTER
    end
```

The `ServerErrorMiddleware` is always outermost (catches unhandled exceptions).
The `ExceptionsHandler` is always innermost (handles application-level exception
mappings). User middleware sits between them.

---

## 6. BaseMiddleware — The Two-Hook Pattern

**File:** `core/sillo/middleware/base.py` (lines 9–168)

`BaseMiddleware` is the recommended base class for dispatch-style middleware. It splits
the middleware lifecycle into two hooks:

| Hook | When it runs | Purpose |
|------|-------------|---------|
| `process_request(request, response, call_next)` | Before the downstream handler | Inspect/modify request, decide whether to call next |
| `process_response(request, response)` | After `call_next` returns | Modify the response |

### 6.1 Full Source

```python
class BaseMiddleware:
    async def __call__(self, request, response, call_next):
        self._call_next = False                          # ← flag reset

        async def wrapped_call_next() -> Any:
            self._call_next = True                       # ← flag set
            return await call_next()                     # ← advance chain

        cnext = await self.process_request(request, response, wrapped_call_next)
        if self._call_next:                              # ← was call_next invoked?
            returned_response = await self.process_response(request, response)
            if returned_response:
                return returned_response
            return cnext
        return cnext                                     # ← short-circuit path
```

### 6.2 The Two Paths

```mermaid
flowchart TD
    START["__call__(request, response, call_next)"]
    RESET["self._call_next = False"]
    PR["process_request(request, response, wrapped_call_next)"]
    CHECK{"self._call_next\nis True?"}
    SHORT["Return cnext\n(short-circuit — call_next\nwas never called)"]
    PRESP["process_response(request, response)"]
    RET_CHECK{"returned_response\nis truthy?"}
    RET_MOD["Return returned_response\n(response was replaced)"]
    RET_ORIG["Return cnext\n(original downstream response)"]

    START --> RESET --> PR --> CHECK
    CHECK -->|"No"| SHORT
    CHECK -->|"Yes"| PRESP --> RET_CHECK
    RET_CHECK -->|"Yes"| RET_MOD
    RET_CHECK -->|"No"| RET_ORIG
```

### 6.3 Simple Subclass Example

```python
from sillo.middleware import BaseMiddleware

class TimingMiddleware(BaseMiddleware):
    async def process_request(self, request, response, call_next):
        request.state.start_time = time.monotonic()
        return await call_next()       # always proceed

    async def process_response(self, request, response):
        elapsed = time.monotonic() - request.state.start_time
        response.headers["X-Response-Time"] = f"{elapsed:.4f}s"
        # return None → BaseMiddleware returns the downstream response unchanged
```

### 6.4 Short-Circuit Example (Auth Guard)

```python
class AuthGuard(BaseMiddleware):
    async def process_request(self, request, response, call_next):
        token = request.headers.get("Authorization")
        if not token or not verify_token(token):
            # NEVER call call_next → _call_next stays False
            # The response from process_request is returned directly
            return response.status(401).json({"error": "Unauthorized"})
        return await call_next()       # proceed to handler

    async def process_response(self, request, response):
        # This never runs for unauthorized requests
        # because _call_next is False
        pass
```

When `process_request` returns without calling `call_next`, the flag `_call_next`
remains `False`. The `__call__` method skips `process_response` entirely and returns
whatever `process_request` returned — typically an error response.

---

## 7. The `_call_next` Flag Pattern in Depth

The `_call_next` flag is the mechanism that makes short-circuiting work. Here's a
step-by-step trace of both paths:

### 7.1 Path A: Middleware Proceeds (Happy Path)

```
1. __call__ is invoked
2. self._call_next = False                          ← reset
3. wrapped_call_next is passed to process_request
4. process_request calls wrapped_call_next()
   4a. self._call_next = True                       ← flag set
   4b. await call_next()                            ← chain advances
   4c. downstream response is returned to process_request
5. process_request returns the response (stored in cnext)
6. __call__ checks: self._call_next is True
7. process_response(request, response) is called
8. If process_response returns a value → that replaces the response
   If process_response returns None → cnext (downstream response) is returned
```

### 7.2 Path B: Middleware Short-Circuits

```
1. __call__ is invoked
2. self._call_next = False                          ← reset
3. wrapped_call_next is passed to process_request
4. process_request does NOT call wrapped_call_next
   → self._call_next remains False
5. process_request returns an error response (stored in cnext)
6. __call__ checks: self._call_next is False
7. process_response is SKIPPED entirely
8. cnext (the error response) is returned directly
```

### 7.3 Important: Why a Flag Instead of a Return Value?

The flag pattern exists because `process_request` has **two possible return semantics**:

1. It can return the result of `await call_next()` (the downstream response) — proceed.
2. It can return a completely different response — short-circuit.

Without the flag, the framework couldn't distinguish between "process_request returned
a response that happened to come from call_next" and "process_request returned its
own response to short-circuit". The flag is set *inside* `wrapped_call_next`, which is
only called if the middleware actually invokes it.

### 7.4 Thread Safety Note

The `_call_next` flag is an instance attribute set during a single `__call__` invocation.
Because ASGI is single-threaded per request and `__call__` is `async`, there is no race
condition. However, if you store mutable state on `self` across requests (which you
shouldn't), be aware that the flag is overwritten on each invocation.

---

## 8. ASGIRequestResponseBridge — Bridging the Gap

**File:** `core/sillo/_internals/_middleware.py` (lines 220–430)

`ASGIRequestResponseBridge` is the critical adapter that converts dispatch-style
middleware into an ASGI application. It is the single point where the high-level
`Request`/`Response` abstraction meets the raw ASGI `scope`/`receive`/`send` protocol.

```mermaid
graph TB
    subgraph "ASGIRequestResponseBridge Architecture"
        direction TB
        INSCOPE["scope / receive / send\n(ASGI protocol)"]
        BRIDGE["ASGIRequestResponseBridge.__call__"]
        CREQ["_CachedRequest(scope, receive)\nwraps ASGI receive into Request"]
        RESP["Response(request)"]
        DISPATCH["dispatch_func(request, response, call_next)"]
        INNER["self.app(scope, receive_or_disconnect, send_no_error)\n(inner ASGI app — runs in background)"]
        MEMSTREAM["anyio MemoryObjectStream\n(send_stream ↔ recv_stream)"]
        STREAMRESP["_StreamingResponse(body_stream())"]
        FINAL["returned_response(scope, wrapped_receive, send)\nsends to real client"]

        INSCOPE --> BRIDGE
        BRIDGE --> CREQ
        BRIDGE --> RESP
        BRIDGE --> DISPATCH
        DISPATCH -->|"call_next()"| INNER
        INNER -->|"sends messages"| MEMSTREAM
        MEMSTREAM -->|"receives messages"| STREAMRESP
        STREAMRESP -->|"returned to dispatch"| DISPATCH
        DISPATCH -->|"returns response"| FINAL
        FINAL -->|"sends to"| INSCOPE
    end
```

### 8.1 The `__call__` Method — Step by Step

```python
async def __call__(self, scope, receive, send):
    # 1. Non-HTTP scopes pass through directly
    if scope["type"] != "http":
        await self.app(scope, receive, send)
        return

    # 2. Create the dispatch-layer objects
    request = _CachedRequest(scope, receive)
    response = Response(request=request)
    wrapped_receive = request.wrapped_receive
    response_sent = anyio.Event()

    # 3. Define call_next — runs inner app in background
    async def call_next(*_):
        # ... runs self.app in a background task
        # ... streams response through memory channel
        # ... returns _StreamingResponse
        ...

    # 4. Create memory stream for inter-task communication
    streams = anyio.create_memory_object_stream()
    send_stream, recv_stream = streams

    # 5. Run the dispatch function with structured concurrency
    with recv_stream, send_stream, collapse_excgroups():
        async with anyio.create_task_group() as task_group:
            # 6. Invoke the dispatch middleware
            returned_response = await self.dispatch_func(
                request, response, call_next
            )
            # 7. The returned response is a _StreamingResponse
            #    Send it to the real client
            await returned_response(scope, wrapped_receive, send)
            # 8. Signal that the response has been fully sent
            response_sent.set()
            recv_stream.close()
```

### 8.2 The `call_next` Closure

The `call_next` function is the heart of the bridge. When the dispatch middleware calls
it, the following happens:

1. **Background task starts** — `self.app(scope, receive_or_disconnect, send_no_error)`
   runs in a child task of the `anyio.TaskGroup`.

2. **`receive_or_disconnect`** wraps the original receive to race against
   `response_sent` — once the middleware finishes sending the response, the inner app
   gets a synthetic `http.disconnect` to stop it from reading more body.

3. **`send_no_error`** writes ASGI messages into the `send_stream` end of an
   `anyio.MemoryObjectStream`.

4. **The main task reads** from `recv_stream` to get the `http.response.start` message
   (headers, status) and constructs a `_StreamingResponse` with a `body_stream()` async
   generator that yields body chunks from the channel.

5. **The `_StreamingResponse`** is attached to the `response` object and returned to
   the dispatch middleware.

```mermaid
sequenceDiagram
    participant Client
    participant Bridge as ASGIRequestResponseBridge
    participant Dispatch as dispatch_func (e.g. BaseMiddleware)
    participant InnerApp as self.app (inner ASGI app)
    participant MemStream as MemoryObjectStream

    Client->>Bridge: HTTP request (scope, receive, send)
    Bridge->>Bridge: Create _CachedRequest, Response
    Bridge->>Dispatch: dispatch_func(request, response, call_next)

    Note over Dispatch: process_request runs...
    Dispatch->>Bridge: call_next()

    Bridge->>InnerApp: Start in background task
    InnerApp->>MemStream: http.response.start (status, headers)
    Bridge->>MemStream: Read response.start
    Bridge->>Bridge: Create _StreamingResponse
    Bridge->>Dispatch: Return _StreamingResponse

    Note over Dispatch: process_response runs...
    Dispatch->>Bridge: Return final response

    Bridge->>Client: Send response.start

    loop Body chunks
        InnerApp->>MemStream: http.response.body (chunk)
        Bridge->>Client: Send body chunk
    end

    InnerApp->>MemStream: http.response.body (more_body=false)
    Bridge->>Client: Send final chunk

    Bridge->>Bridge: response_sent.set()
```

### 8.3 Non-HTTP Passthrough

WebSocket and lifespan scopes bypass the bridge entirely:

```python
if scope["type"] != "http":
    await self.app(scope, receive, send)
    return
```

This means dispatch-style middleware only ever sees HTTP requests. WebSocket middleware
must be written as ASGI-native middleware.

---

## 9. _CachedRequest — Three-State Receive

**File:** `core/sillo/_internals/_middleware.py` (lines 96–218)

`_CachedRequest` is a `Request` subclass that solves a fundamental problem: the dispatch
middleware may read the request body (via `request.body()` or `request.stream()`), but
the inner ASGI app also needs to read the body via the `receive` callable. The body can
only be consumed once from the network, so `_CachedRequest` caches and replays it.

### 9.1 The Three States

`wrapped_receive()` manages three distinct states:

```mermaid
stateDiagram-v2
    [*] --> NotConsumed: Initial state

    NotConsumed --> NotConsumed: stream() called but not exhausted\n→ forward next chunk
    NotConsumed --> Consumed: body() was called\n→ return cached body
    NotConsumed --> Consumed: stream() fully consumed\n→ return empty body
    NotConsumed --> Disconnected: ClientDisconnect caught\n→ return disconnect

    Consumed --> Disconnected: Client disconnect detected\n→ return disconnect
    Consumed --> Consumed: Already consumed\n→ wait for disconnect msg

    Disconnected --> Disconnected: Any subsequent call\n→ immediate disconnect

    state NotConsumed {
        note right of NotConsumed
            Neither body() nor stream()
            has been fully consumed.
            Chunks are forwarded as they
            arrive from the network.
        end note
    }

    state Consumed {
        note right of Consumed
            Body is fully consumed.
            Downstream gets empty body
            or cached body, then waits
            for disconnect.
        end note
    }

    state Disconnected {
        note right of Disconnected
            Client has disconnected.
            All calls return
            http.disconnect immediately.
        end note
    }
```

### 9.2 State Transition Code

```python
async def wrapped_receive(self) -> Message:
    # STATE 1: Disconnected — fast path
    if self._wrapped_rcv_disconnected:
        return {"type": "http.disconnect"}

    # STATE 2: Consumed but not yet disconnected
    if self._wrapped_rcv_consumed:
        if self._is_disconnected:
            self._wrapped_rcv_disconnected = True
            return {"type": "http.disconnect"}
        msg = await self.receive()
        if msg["type"] != "http.disconnect":
            raise RuntimeError(f"Unexpected message received: {msg['type']}")
        self._wrapped_rcv_disconnected = True
        return msg

    # STATE 3: Not yet consumed
    if getattr(self, "_body", None) is not None:
        # body() was called — return cached body in one shot
        self._wrapped_rcv_consumed = True
        return {"type": "http.request", "body": self._body, "more_body": False}
    elif self._stream_consumed:
        # stream() was fully consumed — return empty so downstream doesn't hang
        self._wrapped_rcv_consumed = True
        return {"type": "http.request", "body": b"", "more_body": False}
    else:
        # Neither consumed — forward the next chunk from the stream
        try:
            stream = self.stream()
            chunk = await stream.__anext__()
            self._wrapped_rcv_consumed = self._stream_consumed
            return {"type": "http.request", "body": chunk,
                    "more_body": not self._stream_consumed}
        except ClientDisconnect:
            self._wrapped_rcv_disconnected = True
            return {"type": "http.disconnect"}
```

### 9.3 Why This Matters

Without `_CachedRequest`, if a dispatch middleware calls `await request.body()` to
inspect the payload (e.g., for request signing verification), the inner ASGI app would
get an empty body because the network stream was already consumed. `_CachedRequest`
ensures:

- `body()` callers get the full body cached in memory.
- `stream()` callers get chunks forwarded one at a time.
- The inner app always sees a complete body (cached or empty).
- Client disconnections are handled without deadlocks.

---

## 10. _StreamingResponse — Async Body Relay

**File:** `core/sillo/_internals/_middleware.py` (lines 432–520)

`_StreamingResponse` is a `BaseResponse` subclass that streams its body from an async
iterator. It's the return type of `call_next()` — the bridge constructs it from the
messages received through the memory channel.

```python
class _StreamingResponse(BaseResponse):
    def __init__(self, content, status_code=200, headers=None,
                 media_type=None, info=None):
        self.info = info
        self.content_iterator = content   # AsyncGenerator yielding bytes
        self.status_code = status_code
        self.media_type = media_type
        super().__init__(headers=dict(headers or {}), status_code=status_code)

    async def __call__(self, scope, receive, send):
        if self.info is not None:
            await send({"type": "http.response.debug", "info": self.info})
        await send({
            "type": "http.response.start",
            "status": self.status_code,
            "headers": self.raw_headers,
        })
        should_close_body = True
        async for chunk in self.content_iterator:
            if isinstance(chunk, dict):
                # ASGI message (e.g., pathsend) — pass through directly
                should_close_body = False
                await send(chunk)
                continue
            await send({"type": "http.response.body", "body": chunk, "more_body": True})
        if should_close_body:
            await send({"type": "http.response.body", "body": b"", "more_body": False})
```

### 10.1 Body Stream Lifecycle

```mermaid
sequenceDiagram
    participant Resp as _StreamingResponse
    participant Gen as body_stream() generator
    participant Mem as recv_stream (memory channel)
    participant Send as ASGI send callable

    Resp->>Send: http.response.start (status, headers)

    loop Until more_body=false
        Gen->>Mem: receive() → message
        Mem-->>Gen: http.response.body
        Gen->>Gen: yield message["body"]
        Resp->>Send: http.response.body (chunk, more_body=true)
    end

    Gen->>Gen: Check for app_exc → re-raise if present
    Resp->>Send: http.response.body (b"", more_body=false)
```

### 10.2 Exception Propagation

If the inner ASGI app raises an exception, it's captured in `app_exc` and re-raised
inside `body_stream()` after the body is fully consumed. This ensures the exception
propagates through the middleware chain's error handling rather than being silently lost.

---

## 11. GZipMiddleware — ASGI-Native Compression

**File:** `core/sillo/middleware/gzip.py` (lines 13–297)

Unlike `BaseMiddleware`, `GZipMiddleware` is an **ASGI-native** middleware. It operates
directly on the `scope`/`receive`/`send` protocol to intercept and compress response
bodies at the byte level.

### 11.1 Architecture

```python
class GZipMiddleware:
    def __init__(self, app: ASGIApp, minimum_size: int = 500,
                 compresslevel: int = 9):
        self.app = app
        self.minimum_size = minimum_size
        self.compresslevel = compresslevel

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = Headers(scope=scope)
            if "gzip" in headers.get("Accept-Encoding", ""):
                responder = GZipResponder(self.app, self.minimum_size,
                                          compresslevel=self.compresslevel)
                await responder(scope, receive, send)
                return
        await self.app(scope, receive, send)
```

### 11.2 Decision Flow

```mermaid
flowchart TD
    REQ["GZipMiddleware.__call__(scope, receive, send)"]
    IS_HTTP{"scope['type'] == 'http'?"}
    PASSTHRU["Pass through to self.app\n(no compression)"]
    HAS_GZIP{"Accept-Encoding\ncontains 'gzip'?"}
    RESPONDER["Create GZipResponder\nand delegate"]
    NORMAL["Pass through to self.app\n(client doesn't support gzip)"]

    REQ --> IS_HTTP
    IS_HTTP -->|"No (WebSocket, lifespan)"| PASSTHRU
    IS_HTTP -->|"Yes"| HAS_GZIP
    HAS_GZIP -->|"No"| NORMAL
    HAS_GZIP -->|"Yes"| RESPONDER
```

### 11.3 Constructor Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `app` | (required) | The inner ASGI application |
| `minimum_size` | 500 | Minimum body size in bytes before compression is applied |
| `compresslevel` | 9 | GZip compression level (1=fastest, 9=best compression) |

### 11.4 Registration

GZip middleware is registered as ASGI-native middleware directly on the router or
application, not via `app.use()`:

```python
# On a router
router = Router(middleware=[DefineMiddleware(GZipMiddleware, minimum_size=1024)])

# Or on the application
app = SilloApp(middleware=[
    DefineMiddleware(GZipMiddleware, minimum_size=500, compresslevel=6)
])
```

---

## 12. GZipResponder — The Four Cases

**File:** `core/sillo/middleware/gzip.py` (lines 79–276)

`GZipResponder` is where the actual compression logic lives. It wraps the inner app's
`send` callable with `send_with_gzip`, which intercepts each ASGI message and applies
the appropriate compression strategy.

### 12.1 State Variables

```python
class GZipResponder:
    def __init__(self, app, minimum_size, compresslevel=9):
        self.app = app
        self.minimum_size = minimum_size
        self.send: Send = unattached_send      # sentinel — raises if called before init
        self.initial_message: Message = {}      # cached http.response.start
        self.started = False                     # have we sent the start message?
        self.declared_length: int | None = None  # Content-Length from headers
        self.passthrough = False                 # True → skip compression for all chunks
        self.content_encoding_set = False        # True → downstream already compressed
        self.gzip_buffer = io.BytesIO()          # in-memory buffer for compressed bytes
        self.gzip_file = gzip.GzipFile(          # GZip file object wrapping the buffer
            mode="wb", fileobj=self.gzip_buffer, compresslevel=compresslevel
        )
```

### 12.2 The Four Cases in `send_with_gzip`

The method handles `http.response.body` messages through four distinct branches:

```mermaid
flowchart TD
    MSG["send_with_gzip(message)"]
    TYPE{"message['type']?"}
    START["http.response.start\n→ Cache message, read Content-Length,\ncheck Content-Encoding"]
    BODY["http.response.body"]

    CE_SET{"content_encoding_set?"}
    CASE1["CASE 1: Pre-encoded\nPass through unchanged\n(Downstream already compressed)"]

    PASSTHRU{"passthrough?"}
    CASE2["CASE 2: Below threshold\nPass through uncompressed\n(Too small to benefit)"]

    STARTED{"started?"}
    BELOW{"_below_threshold\n(body, more_body)?"}
    MORE{"more_body?"}

    CASE2B["Set passthrough=True\nSend start + body uncompressed"]

    CASE3["CASE 3: Standard GZip\nCompress entire body\nUpdate Content-Encoding,\nContent-Length, Vary headers"]

    CASE4_INIT["CASE 4a: Streaming init\nSet Content-Encoding=gzip\nRemove Content-Length\nCompress first chunk"]

    CASE4_CONT["CASE 4b: Streaming continuation\nCompress subsequent chunks\nClose gzip on final chunk"]

    MSG --> TYPE
    TYPE -->|"response.start"| START
    TYPE -->|"response.body"| BODY

    BODY --> CE_SET
    CE_SET -->|"Yes"| CASE1
    CE_SET -->|"No"| PASSTHRU

    PASSTHRU -->|"Yes"| CASE2
    PASSTHRU -->|"No"| STARTED

    STARTED -->|"No (first body chunk)"| BELOW
    BELOW -->|"Yes"| CASE2B
    BELOW -->|"No"| MORE
    MORE -->|"No (complete body)"| CASE3
    MORE -->|"Yes (streaming)"| CASE4_INIT

    STARTED -->|"Yes (subsequent chunks)"| CASE4_CONT
```

### 12.3 Case 1: Pre-Encoded Content

**Trigger:** `content_encoding_set is True` (downstream already set a `Content-Encoding`
header)

```python
elif message_type == "http.response.body" and self.content_encoding_set:
    if not self.started:
        self.started = True
        await self.send(self.initial_message)
    await self.send(message)
```

**Behavior:** The response passes through completely untouched. If the downstream handler
already compressed the body (e.g., Brotli from a CDN), GZip doesn't double-compress.

### 12.4 Case 2: Below Minimum Size Threshold

**Trigger:** `passthrough is True` (set when the first body chunk was below
`minimum_size`)

```python
elif message_type == "http.response.body" and self.passthrough:
    await self.send(message)
```

**And the initial decision:**

```python
if self._below_threshold(body, more_body):
    self.passthrough = True
    await self.send(self.initial_message)
    await self.send(message)
```

**Behavior:** Responses smaller than `minimum_size` (default 500 bytes) are sent
uncompressed. GZip framing overhead (~20 bytes) means tiny responses can actually get
*larger* when compressed.

The `_below_threshold` method is careful about multi-chunk responses:

```python
def _below_threshold(self, body: bytes, more_body: bool) -> bool:
    if self.declared_length is not None:
        return self.declared_length < self.minimum_size  # use Content-Length
    return len(body) < self.minimum_size and not more_body  # only if complete
```

### 12.5 Case 3: Standard Single-Shot GZip

**Trigger:** First body chunk, not below threshold, `more_body is False`

```python
elif not more_body:
    self.gzip_file.write(body)
    self.gzip_file.close()
    body = self.gzip_buffer.getvalue()

    headers = MutableHeaders(raw=self.initial_message["headers"])
    headers["Content-Encoding"] = "gzip"
    headers["Content-Length"] = str(len(body))
    headers.add_vary_header("Accept-Encoding")
    message["body"] = body

    await self.send(self.initial_message)
    await self.send(message)
```

**Behavior:** The entire body is compressed in one shot. Headers are updated with:
- `Content-Encoding: gzip`
- `Content-Length` → set to the compressed size
- `Vary: Accept-Encoding` → added for cache correctness

### 12.6 Case 4: Streaming GZip

**Trigger:** First body chunk, not below threshold, `more_body is True`

**Initialization (first chunk):**

```python
else:
    headers = MutableHeaders(raw=self.initial_message["headers"])
    headers["Content-Encoding"] = "gzip"
    headers.add_vary_header("Accept-Encoding")
    del headers["Content-Length"]   # can't know compressed size in advance

    self.gzip_file.write(body)
    message["body"] = self.gzip_buffer.getvalue()
    self.gzip_buffer.seek(0)
    self.gzip_buffer.truncate()

    await self.send(self.initial_message)
    await self.send(message)
```

**Continuation (subsequent chunks):**

```python
elif message_type == "http.response.body":  # pragma: no branch
    body = message.get("body", b"")
    more_body = message.get("more_body", False)

    self.gzip_file.write(body)
    if not more_body:
        self.gzip_file.close()

    message["body"] = self.gzip_buffer.getvalue()
    self.gzip_buffer.seek(0)
    self.gzip_buffer.truncate()

    await self.send(message)
```

**Behavior:** Each chunk is compressed incrementally. The GZip file object maintains
internal state across chunks, so the compressed output is a valid single GZip stream
when concatenated. `Content-Length` is removed (can't know the final compressed size).

### 12.7 Resource Cleanup

The GZip buffer and file are managed with a context manager in `__call__`:

```python
async def __call__(self, scope, receive, send):
    self.send = send
    with self.gzip_buffer, self.gzip_file:
        await self.app(scope, receive, self.send_with_gzip)
```

This ensures the `gzip.GzipFile` is properly closed and the `BytesIO` buffer is freed
even if an exception occurs during response processing.

### 12.8 The `unattached_send` Sentinel

```python
async def unattached_send(message: Message) -> typing.NoReturn:
    raise RuntimeError("send awaitable not set")
```

This is the initial value of `self.send`. If any code tries to send a message before
`__call__` binds the real `send`, it fails immediately with a clear error rather than
silently dropping the message.

---

## 13. app.use() — Application-Level Registration

**File:** `core/sillo/application.py` (lines 889–933)

`SilloApp.use()` registers a dispatch-style middleware at the application level. It
wraps the middleware in an `ASGIRequestResponseBridge` and inserts it at **position 0**
of the middleware list.

```python
def use(self, middleware: MiddlewareType) -> None:
    if self.auth_user_model is None:
        self.auth_user_model = getattr(middleware, "user_model", None)

    self.http_middleware.insert(
        0,
        Middleware(ASGIRequestResponseBridge, dispatch=middleware),
    )
```

### 13.1 Inside-Out Insertion

Inserting at position 0 means the most recently added middleware is the **outermost**
layer. Combined with reverse iteration during chain construction (§5), this produces
the intuitive "first added = first to execute" ordering.

```python
app.use(A)  # http_middleware = [Bridge(A)]
app.use(B)  # http_middleware = [Bridge(B), Bridge(A)]
app.use(C)  # http_middleware = [Bridge(C), Bridge(B), Bridge(A)]

# Chain construction (reversed iteration):
# app = Bridge(A)(inner)
# app = Bridge(B)(Bridge(A)(inner))
# app = Bridge(C)(Bridge(B)(Bridge(A)(inner)))
#
# Request flow: C → B → A → handler
# C was added last but runs first (outermost)
```

Wait — this seems backwards. Let me re-read the code. The list after three inserts is
`[C, B, A]`. Reversed iteration produces `A, B, C`. So the wrapping is:

```
app = A(inner)
app = B(A(inner))
app = C(B(A(inner)))
```

Result: `C` is outermost, `A` is innermost. **The last middleware added runs first.**

```mermaid
graph LR
    subgraph "app.use() insertion order"
        direction LR
        USE_A["app.use(A) → [A]"]
        USE_B["app.use(B) → [B, A]"]
        USE_C["app.use(C) → [C, B, A]"]
        USE_A --> USE_B --> USE_C
    end
end
```

```mermaid
graph TB
    subgraph "Resulting call chain"
        direction TB
        C["C (outermost — added last)"]
        B["B"]
        A["A (innermost — added first)"]
        H["Route Handler"]
        C --> B --> A --> H
    end
```

### 13.2 Auth Model Side Effect

`app.use()` has a side effect: if `self.auth_user_model` hasn't been set yet, it
checks the middleware for a `user_model` attribute and adopts it. This lets
`AuthenticationMiddleware` configure the app's auth model without an explicit
constructor argument.

### 13.3 The Full Middleware Assembly

When a request arrives, `SilloApp.handle_request()` assembles the complete stack:

```python
middleware = (
    [Middleware(ASGIRequestResponseBridge, dispatch=ServerErrorMiddleware(...))]
    + self.http_middleware   # user middleware (from app.use())
    + [Middleware(ASGIRequestResponseBridge, dispatch=self.exceptions_handler)]
)
for cls, args, kwargs in reversed(middleware):
    app = cls(app, *args, **kwargs)
```

This means:
1. `ServerErrorMiddleware` is always outermost (catches all unhandled exceptions).
2. User middleware runs next (in reverse registration order).
3. `ExceptionsHandler` is always innermost (handles mapped exceptions before they
   reach the route handler).

---

## 14. Router.use() — Router-Level Registration

**File:** `core/sillo/core/routing/router.py` (lines 1160–1186)

`Router.use()` works identically to `SilloApp.use()` but applies to a specific router:

```python
def use(self, middleware: MiddlewareType) -> None:
    if callable(middleware):
        mdw = Middleware(ASGIRequestResponseBridge, dispatch=middleware)
        self.middleware.insert(0, mdw)
```

### 14.1 Router Middleware vs App Middleware

| Aspect | `app.use()` | `router.use()` |
|--------|-------------|----------------|
| Scope | All routes in the application | Only routes on this router (and sub-routers) |
| Storage | `self.http_middleware` | `self.middleware` |
| Applied in | `handle_request()` | `build_middleware_stack()` / `__call__()` |
| Ordering | Runs before router middleware | Runs after app middleware |

### 14.2 Route-Level Middleware

Individual routes can also have middleware, applied in `Route.__init__`:

```python
# core/sillo/core/routing/router.py (lines 418–443)
def apply_middleware(app: ASGIApp) -> ASGIApp:
    middleware = []
    for mdw in self.middleware:
        middleware.append(wrap_middleware(mdw))
    for cls, args, kwargs in reversed(middleware):
        app = cls(app, *args, **kwargs)
    return app

self.app = apply_middleware(route_handler_as_asgi_app)
```

---

## 15. use_for_route() — Conditional Route Middleware

**File:** `core/sillo/middleware/utils.py` (lines 10–113)

`use_for_route()` is a decorator factory that makes a middleware execute only for
requests matching a specific URL pattern.

### 15.1 Usage

```python
@use_for_route("/api/v1/*")
async def api_rate_limit(request, response, call_next):
    # Only runs for /api/v1/* routes
    if rate_limiter.exceeded(request):
        return response.status(429).json({"error": "Too many requests"})
    return await call_next()

app.use(api_rate_limit)
```

### 15.2 Pattern Matching

```python
if route.endswith("/*"):
    route = route[:-2]               # strip /*
    route = f"^{route}/.*$"          # wildcard: match any sub-path
else:
    route = f"^{route}$"             # exact match
```

| Pattern | Regex | Matches |
|---------|-------|---------|
| `/api/users` | `^/api/users$` | Only `/api/users` exactly |
| `/api/*` | `^/api/.*$` | `/api/users`, `/api/orders/123`, etc. |

### 15.3 Class Method Support

The decorator detects whether the function is a class method (named `__call__`) and
wraps accordingly:

```python
if func.__name__ == "__call__":
    return wrapper_klass   # includes self parameter
else:
    return wrapper_func    # standalone function
```

This enables:

```python
class AuthMiddleware:
    @use_for_route("/admin/*")
    async def __call__(self, request, response, call_next):
        if not request.user.is_admin:
            return response.status(403).json({"error": "Forbidden"})
        return await call_next()
```

### 15.4 Passthrough Behavior

When the URL doesn't match, the middleware calls `call_next()` immediately — it acts
as a no-op pass-through:

```python
async def wrapper_func(request, response, call_next):
    if re.match(route, request.url.path):
        return await func(request, response, call_next)
    else:
        return await call_next()   # ← pass through
```

---

## 16. wrap_middleware() — The Normalization Glue

**File:** `core/sillo/_internals/_middleware.py` (lines 528–546)

`wrap_middleware()` converts a dispatch-style middleware function into a
`DefineMiddleware` instance that wraps it in an `ASGIRequestResponseBridge`:

```python
def wrap_middleware(middleware_function: MiddlewareType) -> DefineMiddleware:
    return DefineMiddleware(ASGIRequestResponseBridge, dispatch=middleware_function)
```

This is used in route-level middleware application:

```python
# In Route.__init__:
for mdw in self.middleware:
    middleware.append(wrap_middleware(mdw))
for cls, args, kwargs in reversed(middleware):
    app = cls(app, *args, **kwargs)
```

The normalization ensures that even raw dispatch functions get the bridge treatment
before entering the ASGI chain.

---

## 17. Complete Request Lifecycle Diagram

This diagram traces a single HTTP request through every layer of the middleware system:

```mermaid
sequenceDiagram
    participant Server as ASGI Server (uvicorn)
    participant App as SilloApp
    participant SMW as ServerErrorMiddleware (via Bridge)
    participant UserMW as User Middleware (via Bridge)
    participant EXH as ExceptionsHandler (via Bridge)
    participant Router as Router
    participant RouteMW as Route Middleware (via Bridge)
    participant Handler as Route Handler

    Server->>App: __call__(scope, receive, send)
    App->>App: scope["app"] = self
    App->>App: handle_request(scope, receive, send)
    App->>App: Assemble middleware stack

    Note over App: middleware = [ServerError] + http_middleware + [ExceptionsHandler]
    Note over App: for cls, args, kwargs in reversed(middleware):
    Note over App:     app = cls(app, *args, **kwargs)

    App->>SMW: __call__(scope, receive, send)

    SMW->>SMW: Create _CachedRequest, Response
    SMW->>SMW: process_request (catches exceptions)

    SMW->>UserMW: call_next() → dispatch_func(request, response, call_next)

    Note over UserMW: process_request runs...
    UserMW->>UserMW: _call_next = True

    UserMW->>EXH: call_next()

    EXH->>Router: __call__(scope, receive, send)
    Router->>Router: build_middleware_stack(app)
    Router->>RouteMW: apply_middleware(route_handler)

    RouteMW->>Handler: dispatch to matched route handler
    Handler-->>RouteMW: Response

    RouteMW-->>EXH: Response
    EXH-->>UserMW: _StreamingResponse
    UserMW->>UserMW: process_response runs...
    UserMW-->>SMW: Final Response

    SMW->>SMW: process_response (or catch exception)
    SMW-->>App: Response

    App-->>Server: ASGI messages (response.start + response.body chunks)
```

---

## 18. Writing Custom Middleware — Patterns & Anti-Patterns

### 18.1 Recommended: Subclass BaseMiddleware

```python
from sillo.middleware import BaseMiddleware

class RequestIDMiddleware(BaseMiddleware):
    async def process_request(self, request, response, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        return await call_next()

    async def process_response(self, request, response):
        request_id = getattr(request.state, "request_id", None)
        if request_id:
            response.headers["X-Request-ID"] = request_id
        # Return None to pass through the original response
```

### 18.2 Short-Circuit Pattern

```python
class RateLimitMiddleware(BaseMiddleware):
    def __init__(self, max_requests: int = 100, window: int = 60, **kwargs):
        super().__init__(**kwargs)
        self.max_requests = max_requests
        self.window = window
        self.requests: dict[str, list[float]] = {}

    async def process_request(self, request, response, call_next):
        client_ip = request.client.host
        now = time.time()

        # Clean old entries
        self.requests.setdefault(client_ip, [])
        self.requests[client_ip] = [
            t for t in self.requests[client_ip] if now - t < self.window
        ]

        if len(self.requests[client_ip]) >= self.max_requests:
            # SHORT-CIRCUIT: don't call call_next
            return response.status(429).json({
                "error": "Rate limit exceeded",
                "retry_after": self.window,
            })

        self.requests[client_ip].append(now)
        return await call_next()
```

### 18.3 Conditional Application Pattern

```python
from sillo.middleware.utils import use_for_route

@use_for_route("/api/*")
async def api_cors(request, response, call_next):
    result = await call_next()
    result.headers["Access-Control-Allow-Origin"] = "*"
    return result
```

### 18.4 Anti-Patterns to Avoid

**❌ Storing request state on `self`**

```python
class BadMiddleware(BaseMiddleware):
    async def process_request(self, request, response, call_next):
        self.current_user = await get_user(request)  # ← shared across requests!
        return await call_next()
```

Use `request.state` instead:

```python
class GoodMiddleware(BaseMiddleware):
    async def process_request(self, request, response, call_next):
        request.state.user = await get_user(request)  # ← per-request
        return await call_next()
```

**❌ Forgetting to call `call_next()`**

```python
class BadMiddleware(BaseMiddleware):
    async def process_request(self, request, response, call_next):
        log(request)
        # Missing: return await call_next()
        # Chain stops here — handler never runs
```

**❌ Calling `call_next()` multiple times**

```python
class BadMiddleware(BaseMiddleware):
    async def process_request(self, request, response, call_next):
        result1 = await call_next()  # ← first call
        result2 = await call_next()  # ← second call — undefined behavior!
        return result1
```

**❌ Not returning from `process_response` when you want to replace the response**

```python
class ConfusedMiddleware(BaseMiddleware):
    async def process_response(self, request, response):
        new_response = Response(body="modified")
        # Forgot to return new_response → original response is used
```

Fix:

```python
class FixedMiddleware(BaseMiddleware):
    async def process_response(self, request, response):
        return Response(body="modified")  # ← return the replacement
```

---

## 19. Security Middleware

**File:** `core/sillo/middleware/__init__.py`

The middleware package re-exports two security middleware classes:

```python
from sillo.security.cors import CORSMiddleware
from sillo.security.csrf import CSRFMiddleware
from .base import BaseMiddleware

__all__ = ["BaseMiddleware", "CORSMiddleware", "CSRFMiddleware"]
```

These are importable directly from `sillo.middleware`:

```python
from sillo.middleware import CORSMiddleware, CSRFMiddleware
```

### 19.1 Import Ordering Constraint

The `__init__.py` imports `CORSMiddleware` and `CSRFMiddleware` **before**
`BaseMiddleware` to avoid circular import issues. The security modules import
`BaseMiddleware` from `sillo.middleware.base` directly, not from the package
init, which prevents the cycle:

```
sillo.middleware.__init__  →  imports CORSMiddleware from sillo.security.cors
sillo.security.cors        →  imports BaseMiddleware from sillo.middleware.base  (NOT from sillo.middleware)
sillo.middleware.__init__  →  imports BaseMiddleware from .base
```

If the ordering were reversed, importing `sillo` would fail with `ImportError`.

---

## 20. Testing Middleware

### 20.1 Testing BaseMiddleware Subclasses

```python
import pytest
from sillo.testing import TestClient
from sillo import SilloApp

class TestTimingMiddleware:
    def test_adds_response_time_header(self):
        app = SilloApp()
        app.use(TimingMiddleware())

        @app.get("/test")
        async def handler(request, response):
            return {"ok": True}

        client = TestClient(app)
        resp = client.get("/test")
        assert resp.status_code == 200
        assert "X-Response-Time" in resp.headers

    def test_short_circuit_returns_401(self):
        app = SilloApp()
        app.use(AuthGuard())

        @app.get("/protected")
        async def handler(request, response):
            return {"secret": True}

        client = TestClient(app)
        resp = client.get("/protected")
        assert resp.status_code == 401
```

### 20.2 Testing ASGI-Native Middleware

```python
class TestGZipMiddleware:
    def test_compresses_large_response(self):
        app = SilloApp()
        # GZipMiddleware is ASGI-native, typically added via middleware param

        @app.get("/large")
        async def handler(request, response):
            return {"data": "x" * 10000}

        client = TestClient(app)
        resp = client.get("/large", headers={"Accept-Encoding": "gzip"})
        assert resp.headers.get("Content-Encoding") == "gzip"

    def test_skips_small_response(self):
        app = SilloApp()

        @app.get("/small")
        async def handler(request, response):
            return {"ok": True}

        client = TestClient(app)
        resp = client.get("/small", headers={"Accept-Encoding": "gzip"})
        assert "Content-Encoding" not in resp.headers
```

---

## 21. Performance Considerations

### 21.1 Bridge Overhead

Every dispatch-style middleware goes through `ASGIRequestResponseBridge`, which creates:
- A `_CachedRequest` object
- A `Response` object
- An `anyio.MemoryObjectStream` (two endpoints)
- A background task for the inner ASGI app

For performance-critical paths (high-throughput APIs), prefer ASGI-native middleware
that doesn't need the bridge.

### 21.2 GZip Compression Costs

| Level | Speed | Ratio | Use case |
|-------|-------|-------|----------|
| 1 | Fastest | ~30% | Real-time APIs |
| 6 | Balanced | ~40% | General purpose |
| 9 | Slowest | ~42% | Static assets, batch responses |

The `minimum_size` parameter (default 500 bytes) prevents wasting CPU on small responses
where GZip framing overhead negates the compression benefit.

### 21.3 Memory Impact

`_CachedRequest` caches the request body in memory when `body()` is called. For large
file uploads, this can be significant. If your middleware only needs headers, avoid
calling `body()` — use `request.headers` or `request.stream()` instead.

### 21.4 Streaming vs Single-Shot

GZip's Case 4 (streaming) avoids buffering the entire response body in memory. This is
important for large responses (SSE, file downloads) where buffering would cause memory
pressure.

---

## 22. Decision Flowcharts

### 22.1 Which Middleware Style to Use?

```mermaid
flowchart TD
    START["Need to write middleware"]
    WS{"Need WebSocket\ninterception?"}
    ASGI["Use ASGI-native\n(scope, receive, send)"]
    CHUNK{"Need to process\nresponse body\nchunk-by-chunk?"}
    SIMPLE{"Just need to\ninspect/modify\nrequest/response?"}
    BASE["Subclass BaseMiddleware"]
    RAW["Use ASGI-native\n(scope, receive, send)"]
    USE["Use dispatch-style\n(request, response, call_next)"]

    START --> WS
    WS -->|"Yes"| ASGI
    WS -->|"No"| CHUNK
    CHUNK -->|"Yes"| RAW
    CHUNK -->|"No"| SIMPLE
    SIMPLE -->|"Need process_request +\nprocess_response hooks"| BASE
    SIMPLE -->|"Simple pass-through\nwith modifications"| USE
```

### 22.2 Where to Register Middleware?

```mermaid
flowchart TD
    START["Where should this middleware run?"]
    SCOPE{"Scope?"}
    ALL["app.use(middleware)"]
    ROUTER["router.use(middleware)"]
    ROUTE["@use_for_route(pattern)\n+ app.use()"]
    ASGI_ONLY{"ASGI-native?"}
    DIRECT["Add to middleware=[]\nparam on app/router"]

    START --> SCOPE
    SCOPE -->|"All routes in the app"| ALL
    SCOPE -->|"Routes in one router"| ROUTER
    SCOPE -->|"Specific URL patterns"| ROUTE
    SCOPE -->|"Needs raw ASGI access"| ASGI_ONLY
    ASGI_ONLY -->|"Yes"| DIRECT
```

---

## 23. Appendix: Type Reference

### 23.1 Core Types (from `core/sillo/types.py`)

```python
Scope = typing.MutableMapping[str, typing.Any]
Message = typing.MutableMapping[str, typing.Any]
Receive = typing.Callable[[], typing.Awaitable[Message]]
Send = typing.Callable[[Message], typing.Awaitable[None]]
ASGIApp = typing.Callable[[Scope, Receive, Send], typing.Awaitable[Any]]

MiddlewareType = typing.Callable[
    [Request, Response, RequestResponseEndpoint],
    typing.Awaitable[Response | StreamingResponse],
]

RequestResponseEndpoint = typing.Callable[
    [], typing.Awaitable[Response | StreamingResponse]
]
```

### 23.2 Class Hierarchy

```mermaid
classDiagram
    class ASGIApp {
        <<type alias>>
        Callable[[Scope, Receive, Send], Awaitable[Any]]
    }

    class DefineMiddleware {
        +cls: MiddlewareFactory
        +args: tuple
        +kwargs: dict
        +__iter__() Iterator
    }

    class ASGIRequestResponseBridge {
        +app: ASGIApp
        +dispatch_func: MiddlewareType
        +__call__(scope, receive, send)
    }

    class _CachedRequest {
        +_wrapped_rcv_disconnected: bool
        +_wrapped_rcv_consumed: bool
        +_wrapped_rc_stream: AsyncIterator
        +wrapped_receive() Message
    }

    class _StreamingResponse {
        +info: Mapping
        +content_iterator: AsyncIterable
        +status_code: int
        +__call__(scope, receive, send)
    }

    class BaseMiddleware {
        +__call__(request, response, call_next)
        +process_request(request, response, call_next)
        +process_response(request, response)
    }

    class GZipMiddleware {
        +app: ASGIApp
        +minimum_size: int
        +compresslevel: int
        +__call__(scope, receive, send)
    }

    class GZipResponder {
        +app: ASGIApp
        +minimum_size: int
        +gzip_buffer: BytesIO
        +gzip_file: GzipFile
        +send_with_gzip(message)
    }

    class Request {
        <<from sillo.core.http>>
    }

    class BaseResponse {
        <<from sillo.core.http>>
    }

    ASGIRequestResponseBridge --> ASGIApp : wraps
    ASGIRequestResponseBridge --> _CachedRequest : creates
    ASGIRequestResponseBridge --> _StreamingResponse : returns
    _CachedRequest --|> Request : extends
    _StreamingResponse --|> BaseResponse : extends
    DefineMiddleware --> ASGIRequestResponseBridge : factory for
    GZipMiddleware --> GZipResponder : delegates to
    GZipResponder --> ASGIApp : wraps
```

### 23.3 File Index

| File | Line Range | Key Symbols |
|------|-----------|-------------|
| `core/sillo/middleware/base.py` | 9–168 | `BaseMiddleware`, `__call__`, `process_request`, `process_response` |
| `core/sillo/middleware/gzip.py` | 13–297 | `GZipMiddleware`, `GZipResponder`, `send_with_gzip`, `unattached_send` |
| `core/sillo/_internals/_middleware.py` | 27–93 | `DefineMiddleware` |
| `core/sillo/_internals/_middleware.py` | 96–218 | `_CachedRequest`, `wrapped_receive` |
| `core/sillo/_internals/_middleware.py` | 220–430 | `ASGIRequestResponseBridge`, `call_next` |
| `core/sillo/_internals/_middleware.py` | 432–520 | `_StreamingResponse` |
| `core/sillo/_internals/_middleware.py` | 528–546 | `wrap_middleware()` |
| `core/sillo/middleware/utils.py` | 10–113 | `use_for_route()` |
| `core/sillo/middleware/__init__.py` | 1–16 | Re-exports: `BaseMiddleware`, `CORSMiddleware`, `CSRFMiddleware` |
| `core/sillo/application.py` | 889–933 | `SilloApp.use()` |
| `core/sillo/core/routing/router.py` | 909–932 | `Router.build_middleware_stack()` |
| `core/sillo/core/routing/router.py` | 1160–1186 | `Router.use()` |
| `core/sillo/core/routing/router.py` | 418–443 | `Route.apply_middleware()` |
| `core/sillo/types.py` | 1–41 | `ASGIApp`, `MiddlewareType`, `Scope`, `Receive`, `Send` |

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────────────────┐
│                    MIDDLEWARE QUICK REFERENCE                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  DISPATCH-STYLE (most common)                                       │
│  ─────────────────────────────                                      │
│  async def my_mw(request, response, call_next):                     │
│      # pre-processing                                               │
│      result = await call_next()                                     │
│      # post-processing                                              │
│      return result                                                  │
│                                                                     │
│  app.use(my_mw)                                                     │
│                                                                     │
│  BASE MIDDLEWARE SUBCLASS                                           │
│  ──────────────────────────                                         │
│  class MyMW(BaseMiddleware):                                        │
│      async def process_request(self, request, response, call_next): │
│          return await call_next()                                   │
│      async def process_response(self, request, response):           │
│          response.headers["X-Foo"] = "bar"                          │
│          # return None → pass through downstream response           │
│          # return Response → replace downstream response            │
│                                                                     │
│  ASGI-NATIVE                                                        │
│  ──────────                                                         │
│  class MyASGIMiddleware:                                            │
│      def __init__(self, app): self.app = app                        │
│      async def __call__(self, scope, receive, send):                │
│          await self.app(scope, receive, send)                       │
│                                                                     │
│  CONDITIONAL                                                        │
│  ───────────                                                        │
│  @use_for_route("/api/*")                                           │
│  async def api_only(request, response, call_next):                  │
│      return await call_next()                                       │
│                                                                     │
│  ORDER: last app.use() = outermost (runs first)                     │
│  SHORT-CIRCUIT: don't call call_next() → skip handler + post-hooks │
│  REPLACE RESPONSE: return from process_response                     │
│  PASS THROUGH: return None from process_response                    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```
