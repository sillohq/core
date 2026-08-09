---
title: Dependency Injection
description: sillo's dependency injection system — from a single injected function to nested, cached, and request-scoped dependencies, plus how Query/Header/Cookie and request_model plug in.
head:
- tag: meta
  attrs:
    property: og:title
    content: Dependency Injection in sillo
- tag: meta
  attrs:
    property: og:description
    content: How sillo resolves dependencies — nesting, caching, request injection, and parameter extractors.
---

#  Dependency Injection

Dependency injection (DI) is how sillo lets a handler declare *what it needs* — a database session, the current user, a parsed query, a config object — without wiring it up by hand inside the function body. The framework inspects the handler's signature, builds an execution plan, runs each dependency in order, and passes the results in as arguments.

The payoff is the same as anywhere else DI is used: handlers stay small and focused, cross-cutting logic lives in one place, and everything is easy to test because a dependency is just a callable you can call directly or swap out.

sillo's DI is built on two ideas:

- **`Depend(...)`** marks a handler parameter as "fill this in by calling this other function."
- **Parameter extractors** (`Query`, `Header`, `Cookie`) mark a parameter as "read this value out of the request."

Both are resolved by the same machinery, so you can mix them freely in one signature.

##  The smallest useful form

```python
from sillo import SilloApp, Depend

app = SilloApp()


def get_greeting() -> str:
    return "Hello"


@app.get("/greet")
async def greet(request, response, greeting: str = Depend(get_greeting)):
    return response.json({"message": greeting})
```

`Depend(get_greeting)` tells sillo: *before calling `greet`, call `get_greeting()`, and bind its return value to the `greeting` parameter.* The dependency takes no arguments here, so it's just a zero-arg factory.

<aside type="tip" title="Dependencies are plain callables">
`get_greeting` is an ordinary function. That's the whole point — you can unit-test it without a server, and you can reuse it across many routes. sillo only cares that it's callable and that its return type matches the annotated parameter.
</aside>

##  Dependencies that take arguments

Most dependencies need something from the request — the path, a header, the database. A dependency is just a function, so it can declare the same parameter extractors a handler uses:

```python
from sillo import Query, Depend


def paginate(page: int = Query(1), size: int = Query(20)):
    offset = (page - 1) * size
    return {"offset": offset, "limit": size, "page": page}


@app.get("/items")
async def items(request, response, p: dict = Depend(paginate)):
    return response.json({"pagination": p, "rows": []})
```

Here `paginate` declares `page` and `size` as `Query` extractors. When sillo solves the `p` dependency, it first solves those two extractors from the incoming request, then calls `paginate(offset=..., limit=..., page=...)`, then binds the result to `p`.

This is the key mental model: **a dependency's own parameters are solved recursively before the dependency itself runs.** There is no special "dependency API" — dependencies are solved by the exact same engine as the route.

##  Injecting the raw request

Sometimes a dependency needs the whole request object — to read a header that has no extractor, to touch `request.state`, or to read the client IP. Use `Depend(get_request=True)`:

```python
from sillo import Depend


def get_client_ip(request=Depend(get_request=True)):
    return request.get_client_ip()


@app.get("/ping")
async def ping(request, response, ip: str = Depend(get_client_ip)):
    return response.json({"client_ip": ip})
```

`get_request=True` is special: it doesn't call a function. It injects the live `Request` object directly. You can also write a normal dependency that takes `request` as a parameter and sillo will inject it:

```python
def get_client_ip(request):
    return request.get_client_ip()
```

Both forms work; `get_request=True` is the shorthand when a dependency *only* needs the request.

##  Nested dependencies

Dependencies can depend on other dependencies. sillo resolves the full tree, deepest first, and passes each result into its parent.

```python
from sillo import SilloApp, Depend

app = SilloApp()


def get_db():
    # imagine this returns a connection / session factory
    return {"conn": "db-connection"}


def get_current_tenant(request, db: dict = Depend(get_db)):
    # reads a header, uses the db handle
    tenant = request.headers.get("X-Tenant", "default")
    return {"tenant": tenant, "db": db}


@app.get("/data")
async def data(
    request,
    response,
    ctx: dict = Depend(get_current_tenant),
):
    return response.json(ctx)
```

Resolution order for `GET /data`:

1. `get_current_tenant` needs `request` (injected) and `db` (a dependency).
2. sillo solves `db` first → calls `get_db()` → `{"conn": ...}`.
3. sillo calls `get_current_tenant(request=..., db={"conn": ...})` → result bound to `ctx`.
4. The handler runs with `ctx` populated.

You never write this ordering yourself. Declare the graph; sillo topsorts and executes it.

##  Caching within a single request

If two dependencies both depend on `get_db`, you usually don't want to open two connections for one request. sillo caches dependency results **per request** by default.

The cache key is the dependency callable plus the names of any request-derived extractors it consumed. So `get_db()` (no request input) is cached once and reused by every other dependency that asks for it in the same request. But a dependency like `get_current_tenant(request, db=...)` keyed on the `X-Tenant` header would be re-run if the header value differed.

```python
def get_db():
    print("OPENING CONNECTION")   # printed once per request
    return object()


def needs_db_a(db=Depend(get_db)):
    return db


def needs_db_b(db=Depend(get_db)):
    return db


@app.get("/x")
async def x(request, response, a=Depend(needs_db_a), b=Depend(needs_db_b)):
    # get_db() ran exactly once
    return response.json({"same": a is b})
```

If you need to disable caching for a specific dependency, set `use_cache=False` on the `Depend` — though for most apps the default is what you want.

##  Dependencies that clean up after themselves

Some dependencies own a resource that must be released when the response is finished — an open file, a spawned task, a transaction. Declare the dependency as an **async generator** and `yield` the value instead of `return`ing it:

```python
from contextlib import asynccontextmanager
from sillo import Depend


async def db_transaction():
    txn = {"id": "txn-1", "open": True}
    print("BEGIN")
    try:
        yield txn
    finally:
        txn["open"] = False
        print("COMMIT / ROLLBACK")


@app.post("/charge")
async def charge(request, response, txn: dict = Depend(db_transaction)):
    # use txn here
    return response.json({"charged": True})
```

sillo runs the body of the generator up to `yield` to produce the value, injects that value, runs the handler, and then resumes the generator after the handler returns so the `finally` block (cleanup) executes. This is the canonical pattern for "open something, use it in the handler, close it afterward" without leaking resources.

<aside type="caution" title="yield, not return">
A cleanup dependency must `yield` exactly once. If you `return` instead, the teardown code after the value never runs. The generator is resumed automatically when the response is sent.
</aside>

##  Combining DI with request body validation

Two different mechanisms feed a handler:

- **`request_model`** (set on the route) validates the JSON body and exposes it as `request.validated_data`, optionally injected by name.
- **`Depend` / extractors** feed *other* parameters.

They compose cleanly:

```python
from pydantic import BaseModel
from sillo import SilloApp, Depend, Query

app = SilloApp()


class CreateOrder(BaseModel):
    item_id: int
    quantity: int


def get_actor(request):
    return request.headers.get("X-Actor", "anon")


@app.post("/orders", request_model=CreateOrder)
async def create_order(
    request,
    response,
    order: CreateOrder = Depend(lambda: request.validated_data),
    actor: str = Depend(get_actor),
    dry_run: bool = Query(False),
):
    return response.json({
        "order": order.model_dump(),
        "actor": actor,
        "dry_run": dry_run,
    })
```

(For a route-level `request_model`, you can also bind the validated model to a parameter by matching its name to the model; see [Request Parameters](/guides/request-parameters/) and [Handling Inputs](/guides/request-inputs/).)

##  Using dependencies at the router and app level

DI isn't limited to one route. You can attach `Dependencies` to a `Router` or `SilloApp` so every route under it gets them — useful for "require auth on everything under `/admin`" style wiring:

```python
from sillo import SilloApp, Depend
from sillo.core.routing import Router

app = SilloApp()

admin = Router(prefix="/admin")
# every route registered on `admin` resolves `actor` automatically
admin.add_route(...)  # dependencies can be passed per route via the route's `dependencies=`
```

Per-route dependencies are passed through the `Route(..., dependencies=[Depend(...)])` list, or — more commonly — you simply declare `Depend(...)` on the specific handler parameter you want.

##  A full worked example: per-request DB session + auth

This ties the pieces together. A `db_session` dependency opens a connection for the request and closes it after; an `auth_user` dependency reads a bearer token and loads the user; a route composes both plus a body model.

```python
import asyncio
from pydantic import BaseModel
from sillo import SilloApp, Depend, Query

app = SilloApp()


# --- resource-owning dependency (generator => auto cleanup) ---
async def db_session():
    session = {"id": "sess-1"}
    print("session open")
    try:
        yield session
    finally:
        print("session closed")


# --- request-derived dependency (nested) ---
def get_token(request):
    return request.headers.get("Authorization", "").removeprefix("Bearer ")


def auth_user(request, token: str = Depend(get_token)):
    if not token:
        # raise a clean HTTP error; caught by the error handler
        from sillo.exceptions import HTTPException
        raise HTTPException(401, "Missing bearer token")
    return {"user_id": "u_1", "token": token[:6]}


class NoteIn(BaseModel):
    text: str


@app.post("/notes", request_model=NoteIn)
async def create_note(
    request,
    response,
    session: dict = Depend(db_session),
    user: dict = Depend(auth_user),
    note: NoteIn = Depend(lambda: request.validated_data),
    echo: bool = Query(False),
):
    return response.json({
        "session": session["id"],
        "user": user["user_id"],
        "note": note.model_dump(),
        "echo": echo,
    })
```

Resolution for `POST /notes`:

1. `db_session` runs → yields a session, kept open.
2. `get_token` runs (request injected) → returns the bearer string.
3. `auth_user` runs with `token` → returns the user dict (or raises 401).
4. The route's `request_model=NoteIn` validates the body → `request.validated_data`.
5. The `note` dependency reads `request.validated_data` → the `NoteIn` instance.
6. `echo` is read from the query string.
7. Handler runs. When the response is sent, `db_session`'s `finally` closes the session.

This is the shape of a real sillo route: cheap, pure functions for logic; the framework owns ordering, caching, validation, and cleanup.

##  Testing dependencies in isolation

Because a dependency is just a callable, you test it without a server. For request-derived ones, build the smallest fake `Request` you need, or refactor the pure logic out of the extractor:

```python
# pure core, easy to test
def build_user(token: str) -> dict:
    if not token:
        raise ValueError("missing token")
    return {"user_id": "u_1", "token": token[:6]}


def auth_user(request, token: str = Depend(get_token)):
    return build_user(token)   # real logic lives in build_user


def test_build_user():
    assert build_user("abc123")["user_id"] == "u_1"
    try:
        build_user("")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")
```

For end-to-end checks, drive the route through `TestClient` (see [Installation](/guides/installation/) for setup) — the whole DI tree resolves exactly as it would in production:

```python
from sillo.testclient import TestClient

resp = TestClient(app).post(
    "/notes",
    json={"text": "hi"},
    headers={"Authorization": "Bearer secret"},
)
assert resp.status_code == 200
```

##  Common pitfalls

- **Forgetting `Depend`** — writing `user: User = get_user` binds the *function object*, not its result. Always wrap with `Depend(get_user)`.
- **Mutating shared state in a singleton dependency** — dependencies are re-solved per request (and cached within it), but a module-level object they return is shared across requests. Keep per-request state in the request, not in globals.
- **Over-nesting** — three or four levels of dependencies is fine; a dozen is a smell. Flatten when a dependency only exists to pass values through.
- **Doing I/O in a non-generator dependency** — if you open a connection and `return` it, nothing closes it. Use `yield` so the teardown runs.

##  Works with

- [Request Parameters](/guides/request-parameters/) — `Query`, `Header`, `Cookie` extractors in handlers and dependencies
- [Handlers](/guides/handlers/) — the handler contract and return values
- [Routers & Sub-Apps](/guides/routers-and-subapps/) — organize dependency-protected function handlers behind a prefix
- [Middleware](/guides/middleware/) — request-scoped logic that runs for every request, not just injected ones

##  Related topics

- [Routing](/guides/routing/) — path syntax, `name=`, and route options like `request_model`
- [Error Handling](/guides/error-handling/) — turning validation failures into clean responses
- [Authentication](/guides/authentication/) — `useAuth` and the auth dependency used by protected routes


##  When a dependency is the wrong tool

Dependencies resolve per request, before the handler. That makes them
right for anything scoped to a request and wrong for two neighbouring
cases.

**Per-process resources belong in the lifespan.** A connection pool, an
HTTP client, a template environment — creating one per request is
expensive and pointless. Build it once in a
[startup hook](/guides/startups-and-shutdowns/) and read it from
`app.state` inside a dependency if you want it injected.

**Cross-cutting behaviour belongs in middleware.** Logging every request,
adding a header to every response, enforcing a rate limit — a dependency
would have to be declared on every route, and the one you forget is the
one that matters. [Middleware](/guides/middleware/) applies by position
in the stack rather than by remembering.

The dividing question: does this produce a *value the handler uses*, or
does it *do something regardless of the handler*? Values are
dependencies; behaviour is middleware.

##  Keeping the dependency graph shallow

A dependency that depends on three others, each depending on two more,
resolves correctly and becomes very hard to reason about — a handler
signature with one parameter can trigger a dozen database queries you
cannot see from the route.

Two habits prevent that. Keep the graph at most two levels deep, so a
reader can hold it in their head. And make expensive dependencies
obvious at the call site by naming them for what they cost —
`current_user_with_permissions` says more than `user`.

When a handler needs five injected values, that is usually a sign the
handler is doing five things.
