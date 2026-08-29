---
title: Middleware
description: Intercept and shape requests and responses in sillo with function middleware (app.use), class-based middleware (BaseMiddleware), route- and router-scoped middleware, and raw ASGI middleware.
head:
- tag: meta
  attrs:
    property: og:title
    content: Middleware in sillo
- tag: meta
  attrs:
    property: og:description
    content: "Function and class-based middleware in sillo: app.use, BaseMiddleware, route/router scope, and raw ASGI middleware."
---

#  Middleware

Middleware is code that runs around your handlers, before a request reaches
them and after the response comes back. Use it for cross-cutting concerns that
would otherwise repeat on every route: logging, timing, authentication, CORS,
request-ID injection, rate limiting, response shaping.

sillo gives you three layers, from highest-level to lowest:

- **Function middleware** via `app.use(fn)`: takes the context and an
  `await call_next()` continuation.
- **Class-based middleware** via `BaseMiddleware`: the same idea in a class,
  as a single `dispatch` method.
- **Raw ASGI middleware** via `app.wrap_asgi(...)`: operates on the raw
  `scope`/`receive`/`send` triple, for third-party or framework-agnostic
  middleware.

This page covers all three, how they nest, and how to scope them to a single route or an entire router.

##  The smallest useful form

A middleware function takes two positional arguments: the context and a
continuation (commonly named `call_next`). Call and `await` the continuation to
pass control downstream; whatever it returns is the response, which you then
return:

```python
from sillo import SilloApp, HttpContext

app = SilloApp()

async def log_requests(ctx: HttpContext, call_next):
    print(f"→ {ctx.method} {ctx.url.path}")
    response = await call_next()      # run the rest of the pipeline
    print(f"← {response.status_code}")
    return response

app.use(log_requests)
```

The continuation's name is yours to choose: sillo binds it by position, not by
name. The rule that matters: **you must `await call_next()` and return its
result**, or the client's request will hang.

<aside type="tip" title="What the continuation returns">
`await call_next()` returns the response produced by the rest of the pipeline (the inner middleware plus your handler). You can modify that response before returning it, or return a different response entirely to short-circuit the request.
</aside>

##  Function middleware in depth

###  Before and after the handler

Anything before `await call_next()` runs *before* the handler; anything after runs *after* the handler returns:

```python
import time
from sillo import SilloApp, HttpContext

app = SilloApp()

async def time_it(ctx: HttpContext, call_next):
    start = time.perf_counter()
    response = await call_next()
    duration_ms = (time.perf_counter() - start) * 1000
    response.set_header("X-Process-Time", f"{duration_ms:.1f}ms")
    return response

app.use(time_it)
```

You can also mutate `request` (or `ctx.state`) before the handler and read it back inside the handler:

```python
from sillo import HttpContext

async def attach_request_id(ctx: HttpContext, call_next):
    ctx.state.request_id = "req_" + str(id(ctx))
    return await call_next()

@app.get("/")
async def index(ctx: HttpContext):
    return {"request_id": ctx.state.request_id}
```

###  Short-circuiting

If a middleware returns a response *without* calling `call_next()`, the
pipeline stops, no further middleware or handler runs. This is how auth and
validation gates work:

```python
from sillo.exceptions import HTTPException
from sillo import HttpContext

async def require_token(ctx: HttpContext, call_next):
    if not ctx.headers.get("Authorization"):
        raise HTTPException(401, "Missing Authorization header")
    return await call_next()

app.use(require_token)
```

Returning a response object directly (e.g. `return response.json({"error": ...}, status_code=401)`) works the same way. Raising `HTTPException` is cleaner when you have an exception handler registered (see [Error Handling](/v1.0/guides/error-handling/)).

###  Ordering

`app.use(fn)` inserts the middleware at the **front** of the pipeline, so the **last** `use` call you write is the **outermost** (runs first on the way in, last on the way out):

```python
app.use(correlation_id)   # runs 3rd in, 1st out
app.use(authentication)   # runs 2nd in, 2nd out
app.use(logging)          # runs 1st in, 3rd out
```

Add them in the order you want them to wrap *outward from the handler*: the middleware closest to the handler is written first. A practical rule: put cheap, request-early concerns (logging, IDs) last, and request-late gates (auth) first so they reject before more work happens. If in doubt, test the order with a print in each.

##  Class-based middleware

For middleware that carries configuration or reusable logic, subclass
`BaseMiddleware` from `sillo.middleware` and implement `dispatch`.

```python
from sillo.middleware import BaseMiddleware
from sillo import HttpContext

class TimingMiddleware(BaseMiddleware):
    async def dispatch(self, ctx: HttpContext, call_next):
        start = time.perf_counter()
        response = await call_next()
        ms = (time.perf_counter() - start) * 1000
        return response.set_header("X-Process-Time", f"{ms:.1f}ms")

app.use(TimingMiddleware())
```

One hook, and the two phases are just the two sides of the `await`: everything
before it runs on the way in, everything after it runs on the way out. State
that has to cross between them is a local variable — `start` above — rather
than something parked on `ctx.state` for a second method to find later.

Two rules:

1. **`await call_next()` takes no arguments, and you return its result.** The
   continuation already has the context; there is nothing to hand it.
2. **Returning without awaiting `call_next()` short-circuits the request.** The
   handler never runs, and neither does anything below you in the stack. That is
   how a gate is written — see the auth example further down.

###  Catching errors inside middleware

Because `dispatch` wraps the call to `call_next()`, an ordinary `try` guards
the whole downstream pipeline:

```python
from sillo import HttpContext, json

class ErrorGuardMiddleware(BaseMiddleware):
    async def dispatch(self, ctx: HttpContext, call_next):
        try:
            return await call_next()
        except Exception as exc:                       # noqa: BLE001
            return json(
                {"error": type(exc).__name__, "detail": str(exc)},
                status_code=500,
            )
```

This is the clearest thing the single hook buys: with a separate post-phase
method there was no `try` that could span both halves, so an exception from the
handler reached neither.

Prefer raising `HTTPException` and letting a registered handler format the error (see [Error Handling](/v1.0/guides/error-handling/)) over hand-rolling JSON in every middleware.

##  Route-scoped middleware

Pass `middleware=[...]` to a route so it applies only to that endpoint. It runs inside the app-wide middleware, right before the handler:

```python
from sillo import HttpContext, json

async def require_auth(ctx: HttpContext, call_next):
    if not ctx.headers.get("Authorization"):
        return json({"error": "unauthorized"}, status_code=401)
    return await call_next()

@app.get("/admin/dashboard", middleware=[require_auth])
async def dashboard(ctx: HttpContext):
    return {"ok": True}
```

The same `middleware=[...]` keyword works on `app.route(...)`, `Route(...)`, and the router decorators (`@router.get(..., middleware=[...])`).

##  Router-scoped middleware

A `Router` has its own `use` method. Middleware added there runs for every route mounted under that router, after app-level middleware:

```python
from sillo.core.routing import Router
from sillo import HttpContext, json

app = SilloApp()
api = Router(prefix="/api")

async def api_auth(ctx: HttpContext, call_next):
    if not ctx.headers.get("X-API-Key"):
        return json({"error": "missing api key"}, status_code=401)
    return await call_next()

api.use(api_auth)

@api.get("/users")
async def list_users(ctx: HttpContext):
    return {"users": []}

app.mount_router(api)
```

`Router` also accepts `middleware=[...]` in its constructor, applying to all routes added to it.

##  Raw ASGI middleware

`app.wrap_asgi(...)` wraps the entire sillo app in a standard ASGI middleware
that sees the raw `scope`, `receive`, and `send` callables, before sillo builds
an `HttpContext` from them. Use this for third-party ASGI middleware (GZip,
correlation IDs, Sentry) or when you need to touch the ASGI layer directly.

```python
def gzip_middleware(app):
    async def middleware(scope, receive, send):
        # inspect or rewrite scope here
        await app(scope, receive, send)
    return middleware

app.wrap_asgi(gzip_middleware)
```

A class-based form is also supported, implement `__call__(self, scope, receive,
send)` and store the wrapped `app`:

```python
class ScopeLogger:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        print("scope:", scope["type"], scope.get("path"))
        await self.app(scope, receive, send)

app.wrap_asgi(ScopeLogger)
```

Raw ASGI middleware does **not** have access to sillo's `HttpContext`,
only the ASGI primitives. If you need sillo objects, use `app.use` instead.

##  `use` vs `wrap_asgi`

| | `app.use(fn)` | `app.wrap_asgi(mw)` |
| --- | --- | --- |
| Abstraction | High. Sillo `HttpContext` | Low. ASGI `scope`/`receive`/`send` |
| Framework | sillo-specific | Framework-agnostic |
| Best for | Auth, logging, request/response shaping | Third-party ASGI middleware, low-level tweaks |
| Continuation | `await call_next()` | `await app(scope, receive, send)` |

Pick `use` for application logic that touches sillo features; pick `wrap_asgi` to integrate standard ASGI components.

##  First-party middleware modules

sillo ships ready-made middleware under dedicated modules:

```python
# Security: CSRF, CORS, Shield (security headers)
from sillo.security import CSRFMiddleware, CSRFConfig, CORSMiddleware, CorsConfig, Shield
app.use(CSRFMiddleware(config=CSRFConfig(enabled=True, secret_key="...")))
app.use(CORSMiddleware(config=CorsConfig(allow_origins=["*"])))
app.use(Shield())

# Request lifecycle: request IDs + request-scoped context
from sillo.http.lifecycle import RequestId
app.use(RequestId())

# URL normalization: trailing/double-slash + optional case folding
from sillo.normalize import Normalize, SlashAction
app.use(Normalize(slash_action=SlashAction.REDIRECT_REMOVE))

# Content negotiation: Accept / Accept-Language handling
from sillo.http.accepts import Accepts
app.use(Accepts())
```

See [Security](/v1.0/guides/security/), [CSRF](/v1.0/guides/csrf/), [CORS](/v1.0/guides/cors/), [Request Lifecycle](/v1.0/guides/request-lifecycle/), [URL Normalization](/v1.0/guides/url-normalization/), and [Content Negotiation](/v1.0/guides/content-negotiation/) for each module's options.

##  Common mistakes

- **Not returning `await call_next()`.** A middleware that calls `call_next()` but forgets `return` leaves the response unpropagated and the client hangs. Always `return await call_next()`.
- **Calling the continuation with arguments.** The sillo continuation takes no arguments: `await call_next()`, not `await call_next(ctx)`.
- **Mutating the response but not returning it.** The setters return the response so they can chain, but nothing is sent unless you `return` it.
- **Wrong order for gates.** Put auth/validation middleware where it rejects
  *before* expensive downstream work. Remember the last `app.use` written is
  outermost.
- **Expecting your post-phase to run after a short-circuit.** Everything you wrote after `await call_next()` is skipped when you return before reaching it — which is the point, but it does mean a response built by a gate above you goes out unshaped by anything below.

##  Testing middleware

Drive middleware through `TestClient` like any endpoint: assert headers, status
codes, and short-circuit behavior:

```python
from sillo import SilloApp, HttpContext, json
from sillo.testclient import TestClient

app = SilloApp()

async def add_header(ctx: HttpContext, call_next):
    response = await call_next()
    response.set_header("X-Traced", "yes")
    return response

app.use(add_header)

@app.get("/ping")
async def ping(ctx: HttpContext):
    return {"ok": True}

client = TestClient(app)

def test_header_added():
    resp = client.get("/ping")
    assert resp.status_code == 200
    assert resp.headers["X-Traced"] == "yes"

def test_short_circuit():
    async def reject(ctx: HttpContext, call_next):
        return json({"error": "no"}, status_code=401)

    app.use(reject)
    assert client.get("/ping").status_code == 401
```

##  Works with

- [Handlers](/v1.0/guides/handlers/): what middleware wraps
- [Routing](/v1.0/guides/routing/): `middleware=` on routes and routers
- [Error Handling](/v1.0/guides/error-handling/): format errors raised in middleware
- [Dependency Injection](/v1.0/guides/dependency-injection/): inject shared logic
  instead of middleware when it's per-handler
- [Request Lifecycle](/v1.0/guides/request-lifecycle/): `RequestId` is middleware
  under the hood


##  Order is the whole design

Middleware runs as nested layers: the first registered is the outermost,
sees the request first and the response last. Everything about how a
stack behaves follows from that.

```mermaid
graph LR
    RQ["request"] --> C1["CORS"] --> L1["logging"] --> A1["auth"]
    A1 --> R1["rate limit"] --> H["handler"]
    H --> R2["rate limit"] --> A2["auth"] --> L2["logging"]
    L2 --> C2["CORS"] --> RS["response"]
```

Four ordering rules that come up in practice.

**Error handling goes outermost.** It can only catch what happens inside
it. A handler registered after the thing that raises will never see the
exception.

**CORS goes near the outside.** A rejected request still needs CORS
headers, or the browser reports a CORS failure instead of the real 401
and you debug the wrong thing.

**Authentication goes before authorization**, and both go before anything that
depends on knowing who the caller is, including per-user rate limits and audit
logging.

**Compression and response rewriting go last**, closest to the handler,
so they operate on the final body rather than one an outer layer will
replace.

##  What middleware costs

Every layer runs on every request, including the ones that 404. Ten
middleware each taking one millisecond is ten milliseconds added to your
fastest endpoint, and it will not show up in handler timings.

Two rules keep that bounded. Do no I/O in middleware unless every request
genuinely needs it. A database lookup in middleware is a query on every
static-file request too. And return early: a middleware that can decide without
calling `call_next` should, because everything below it is then skipped
entirely.

```python title="short-circuiting cheaply"
from sillo import HttpContext, json

async def block_bad_agents(ctx: HttpContext, call_next):
    if ctx.headers.get("user-agent", "") in BLOCKLIST:
        return json({"error": "forbidden"}, status_code=403)
    return await call_next()
```

##  Exceptions inside middleware

A middleware that raises before `call_next` prevents the handler from running
at all. One that raises after has already let the handler run (including its
side effects) and then discards the response. That asymmetry is worth being
deliberate about: validation-shaped work belongs before, response shaping
belongs after, and anything that might fail after the handler has committed a
database transaction needs to not throw.

Always call `call_next` exactly once. Calling it twice runs the handler
twice; not calling it at all means returning a response yourself, which
is fine and intentional, but must be a decision rather than an omission.


##  Testing middleware

A middleware is a function of `(request, response, call_next)`, so the
cheapest test calls it directly with a stub `call_next`. That proves the
logic without a server, a route, or a client.

For the ordering (which is where the real bugs are) assert on behaviour through
the full stack: send a request that should be rejected by an outer layer and
check that the inner one never ran. A counter in the handler is enough:

```python
def test_rate_limit_runs_before_handler():
    for _ in range(101):
        client.get("/limited")
    assert handler_calls == 100
```
