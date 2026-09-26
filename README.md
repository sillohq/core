# Sillo

<p align="center">
  <img src="https://raw.githubusercontent.com/sillohq/core/main/docs/docs/public/logo-colored.svg" alt="Sillo logo" width="160" height="160">
</p>

<p align="center">
  <strong>The Buildsmith Framework.</strong>
</p>

<p align="center">
  <a href="https://github.com/sillohq/core/actions/workflows/run-tests.yaml"><img src="https://img.shields.io/github/actions/workflow/status/sillohq/core/run-tests.yaml?branch=main&label=tests&logo=pytest&logoColor=white" alt="Tests"></a>
  <a href="https://codecov.io/gh/sillohq/core"><img src="https://img.shields.io/codecov/c/github/sillohq/core?label=coverage&logo=codecov&logoColor=white" alt="Coverage"></a>
  <a href="https://github.com/sillohq/core/actions/workflows/type-check.yaml"><img src="https://img.shields.io/github/actions/workflow/status/sillohq/core/type-check.yaml?branch=main&label=types&logo=python&logoColor=white" alt="Type check"></a>
  <a href="https://github.com/sillohq/core/actions/workflows/lint.yaml"><img src="https://img.shields.io/github/actions/workflow/status/sillohq/core/lint.yaml?branch=main&label=lint" alt="Lint"></a>
</p>

<p align="center">
  <a href="https://pypi.org/project/sillo-framework/"><img src="https://img.shields.io/pypi/v/sillo-framework?label=pypi&logo=pypi&logoColor=white" alt="PyPI"></a>
  <a href="https://pypi.org/project/sillo-framework/"><img src="https://img.shields.io/pypi/pyversions/sillo-framework?logo=python&logoColor=white" alt="Python versions"></a>
  <a href="https://peps.python.org/pep-0561/"><img src="https://img.shields.io/badge/typed-PEP%20561-blue" alt="PEP 561 typed"></a>
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/badge/lint-ruff-261230?logo=ruff&logoColor=white" alt="Ruff"></a>
  <a href="https://github.com/sillohq/core/blob/main/LICENSE"><img src="https://img.shields.io/pypi/l/sillo-framework?color=green" alt="License"></a>
</p>

<sub>`main` tracks Sillo 1.0, unreleased — `pip install sillo-framework` still gives you 0.x, from [`v0.x`](https://github.com/sillohq/core/tree/v0.x) ([docs](https://docs.sillo.build/v0.x/guides/introduction/)). Everything below is 1.0: install it with `pip install "git+https://github.com/sillohq/core.git@main"`, docs at [docs.sillo.build/v1.0](https://docs.sillo.build/v1.0/guides/introduction/).</sub>

Sillo is the buildsmith framework for APIs, real-time systems, and production backends: fast, async, and built with everything you need to ship, with the ORM, authentication, queues, scheduler, and WebSockets already in place. The language does not change. You write the same Python, with the same type hints and the same `async`/`await`. What changes is how much is waiting for you when you start: routing, request validation, dependency injection, middleware, sessions, authentication, records, background work, WebSockets, OpenAPI, and testing are first-party modules sharing one configuration model.

Each of those is a solved problem with good packages behind it. The work that remains is the fitting, and that is what Sillo does once so you do not do it per project. One `auth=` declaration gates a route and writes its `securityScheme` into the OpenAPI spec. The queue and the scheduler start with the application lifecycle. Range requests, ETags, and content negotiation are middleware rather than something each project rewrites.

The badges above are the only numbers this README states about itself — they
read live from the workflows that produce them, so they can't drift out of
date the way a hand-typed table does. `py.typed` ships in the package, so
your own checker sees Sillo's actual annotations rather than `Any`; five
dependencies land at install time, and every feature group past that —
records, JWT, Redis-backed cache and events, mail, encryption, S3, extra
hashing schemes, Granian — is opt-in, so a service that never sends mail
never carries a templating engine for it.

- [Requirements](#requirements)
- [Installation](#installation)
- [Hello World](#hello-world)
- [Request Validation](#request-validation)
- [Dependency Injection](#dependency-injection)
- [Routing](#routing)
- [Authentication](#authentication)
- [Record — the ORM Layer](#record--the-orm-layer)
- [Background Work: Tasks, Queues, and a Scheduler](#background-work-tasks-queues-and-a-scheduler)
- [WebSockets](#websockets)
- [OpenAPI, Without a Second Source of Truth](#openapi-without-a-second-source-of-truth)
- [Storage, Cache, and Events](#storage-cache-and-events)
- [What Sillo Provides](#what-sillo-provides)
- [Scope And Boundaries](#scope-and-boundaries)
- [Documentation](#documentation)
- [Testing](#testing)
- [Release Principles](#release-principles)

## Requirements

- Python 3.10+
- `uv` for project and dependency management

## Installation

**1.0 is not on PyPI yet.** `uv add sillo-framework` installs 0.x, which is a
different API — see the note at the top. To build against this branch:

```bash
uv add "sillo-framework @ git+https://github.com/sillohq/core.git@main"
```

Everything below documents 1.0. For the released line, read
[the v0.x branch](https://github.com/sillohq/core/tree/v0.x).

### Extras

Five dependencies are installed by default. Every feature group beyond that is
opt-in, so an application that never sends mail does not carry a mail library:

| Extra | Brings in |
|---|---|
| `record` | The ORM and the migration engine (Tortoise) |
| `jwt` | JWT signing and verification (PyJWT) |
| `cache` | Redis cache backend — an in-memory one needs nothing |
| `events` | Redis event distribution — likewise |
| `mail` | Templated email bodies (Jinja2) |
| `crypto` | The `encrypted` cast and `sillo.helpers.crypto` |
| `storage-s3` | HTTP client for the S3 driver, which is still landing. The local and memory drivers need nothing |
| `hashing-bcrypt`, `hashing-argon2`, `hashing-scrypt`, `hashing-all` | Password hashing. Falls back to `pbkdf2_sha256` if none is installed |
| `granian` | The Granian server, as an alternative to uvicorn |
| `all` | Everything above |

```bash
uv add "sillo-framework[record,jwt,cache]"
```

GraphQL and the WebSocket room layer are no longer extras. They are separate
packages that import into the `sillo` namespace:

```bash
uv add sillo-graphql     # imports as sillo.graphql
```

## Application setup

Use `app.install(...)` for subsystems that own application state, request
middleware or lifespan work.  It keeps the application's wiring together while
leaving `app.use(...)` for explicitly ordered HTTP middleware and
`app.on_startup(...)` for application-specific jobs:

```python
from sillo import SilloApp
from sillo.mail import Mail, MailConfig
from sillo.record import DatabaseConfig, Record
from sillo.storage import StorageConfig, StorageInstallable
from sillo.work import Work

app = SilloApp()

database = app.install(Record(DatabaseConfig.sqlite("app.db"), ("myapp.models",)))
mail = app.install(Mail(MailConfig(suppress_send=False)))
storage = app.install(StorageInstallable(StorageConfig()))
work = app.install(Work())
```

An installable is idempotent per application name.  Its returned service is
available through `app.installations` for diagnostics, and remains in its
documented `app.state` location for framework integrations.  Existing
`setup_record`, `setup_mail`, `setup_storage`, `setup_work` and
`setup_scheduler` functions remain supported and delegate to the same path.
See [Application Installables](https://docs.sillo.build/v1.0/advanced/installables/)
to build a subsystem of your own.

## Hello World

A handler takes one argument — the context — plus any path parameters,
dependencies and validation markers it declares. Return a value and Sillo
encodes it:

```python
from sillo import HttpContext, SilloApp

app = SilloApp(title="My API")


@app.get("/")
async def home(ctx: HttpContext):
    return {"message": "Hello from Sillo"}
```

When you need to say more than the body — a status code, a header, a redirect —
use one of the free response builders:

```python
from sillo import HttpContext, SilloApp, created, redirect

app = SilloApp(title="My API")


@app.post("/users")
async def make_user(ctx: HttpContext):
    return created({"id": "user_1"})


@app.get("/old")
async def old(ctx: HttpContext):
    return redirect("/new")
```

`json`, `html`, `text`, `redirect`, `file`, `stream`, `sse` and the rest are
importable from `sillo` directly. There is no `response` object to thread
through your call stack.

Run it with uvicorn:

```bash
uv run uvicorn app:app --reload
```

No import string is needed. `uvicorn` looks for `app.main:app`, `main:app`
and `app:app`, and you can pin it with the `SILLO_APP` environment variable or
a `[tool.sillo] app` entry in `pyproject.toml`. Pass one explicitly when you
want something else:

```bash
uv run uvicorn api.main:app --port 9000 --workers 4
```

`uvicorn` is built for development. For production, run the application
under a process supervisor with a reverse proxy in front of it.

## Request Validation

Sillo validates request bodies with Pydantic through `request_model`.

```python
from pydantic import BaseModel
from sillo import HttpContext, SilloApp, created

app = SilloApp()


class CreateUser(BaseModel):
    name: str
    email: str


@app.post("/users", request_model=CreateUser)
async def create_user(ctx: HttpContext, user: CreateUser):
    return created(user.model_dump())
```

The body is declared once, on the decorator, and injected into the first plain
parameter after the context. It is also available as `ctx.validated_data`.

Every other input location has a marker — `Query`, `Header`, `Cookie`, `Path`,
`Form`, `File` — and constraints go on the marker, feeding both the validation
and the generated OpenAPI schema, so the published contract and the enforced
one cannot drift apart:

```python
from sillo import HttpContext, Query, SilloApp

app = SilloApp()


@app.get("/users")
async def list_users(ctx: HttpContext, page=Query(1, type=int, ge=1, le=100)):
    return {"page": page}
```

Bad input returns 422 naming the location that failed. A parameter error is
wrapped in `detail`:

```json
{"detail": [{"loc": ["query", "page"], "msg": "Input should be less than or equal to 100", "type": "less_than_equal", "input": "999"}]}
```

A request-body error is currently returned as Pydantic's own error list,
unwrapped:

```json
[{"type": "missing", "loc": ["email"], "msg": "Field required", "input": {"name": "Ada"}}]
```

## Dependency Injection

Use `Depend` to inject request-scoped dependencies into handlers.

By default a dependency takes no context: nothing is passed positionally,
and its first parameter is analyzed like any other, free to carry a
`Depend` or extractor default of its own:

```python
from sillo import Depend, HttpContext, SilloApp, json

app = SilloApp()


def settings() -> dict:
    return {"feature_flags": []}


@app.get("/config")
async def show(ctx: HttpContext, cfg=Depend(settings)):
    return json(cfg)
```

Pass `get_context=True` for a dependency that does need the context — it is
then called like a handler, the active context (`HttpContext`, or
`WebSocketContext` on a socket route) as its first positional parameter:

```python
async def get_current_user(ctx: HttpContext):
    return {"id": "user_1", "name": "Ada"}


@app.get("/me")
async def me(ctx: HttpContext, user=Depend(get_current_user, get_context=True)):
    return user
```

A dependency that reads the request does so straight off that first
parameter, with `get_context=True`:

```python
def auth_header(ctx: HttpContext):
    return ctx.headers.get("Authorization")
```

## Routing

```python
from sillo import HttpContext, Router, SilloApp

app = SilloApp()
api = Router(prefix="/api")


@api.get("/users/{user_id:int}")
async def get_user(ctx: HttpContext, user_id: int):
    return {"id": user_id}


app.mount_router(api)
```

Path parameters are converted by the type in the pattern, so `user_id` arrives
as an `int` and a request for `/api/users/abc` never reaches the handler.

## Authentication

One `AuthenticationMiddleware` accepts any number of backends — session,
JWT, API key, or your own — and `useAuth` gates a route by naming which of
them may answer it. The gate and the OpenAPI `securityScheme` it writes come
from the same declaration, so the published contract can't say more or less
than what the middleware actually enforces:

```python
from sillo import HttpContext, SilloApp, json
from sillo.auth import AuthenticationMiddleware, JWTAuthBackend, useAuth
from sillo.users import SimpleUser

app = SilloApp()
app.use(AuthenticationMiddleware(SimpleUser, JWTAuthBackend(secret_key="change-me")))


@app.get("/me", auth=useAuth(schemes=["jwt"]))
async def me(ctx: HttpContext):
    return json({"id": ctx.user.identity})
```

Stack backends to accept more than one credential type on the same route
(`useAuth(schemes=["jwt", "apikey"])`), or write a backend of your own —
`AuthenticationBackend.authenticate(ctx)` returning an `AuthResult` is the
entire contract. Users, groups, and permissions sit on top as ordinary
mixins (`UserProtocol`, `HasScopes`-style permission checks), not a
parallel object model bolted onto Sillo's own.

## Record — the ORM Layer

Records are Tortoise ORM models with the parts a Django-adjacent codebase
expects layered back in: attribute casting, transactions with savepoints,
query scopes, and upsert:

```python
from tortoise import fields

from sillo.record import Model


class User(Model):
    id = fields.IntField(pk=True)
    email = fields.CharField(max_length=255, unique=True)
    plan = fields.CharField(max_length=50, default="free")
    is_active = fields.BooleanField(default=True)
    metadata = fields.TextField(null=True)

    _casts = {"metadata": "json"}  # dict in Python, JSON column in the database

    @classmethod
    def scope_vip(cls, queryset):
        return queryset.filter(plan="vip")

    @classmethod
    def scope_active(cls, queryset):
        return queryset.filter(is_active=True)


# from a handler, a script, a job -- scope_vip + scope_active, chained
active_vip = await User.all().vip().active().order_by("email")
```

A transaction is a context manager with real savepoints, not a special case
bolted onto the session:

```python
from sillo.record.transactions import transaction

# from inside a handler, a job, or a script
async with transaction() as tx:
    await ledger.debit(from_account, amount)
    async with tx.savepoint():
        await audit_log.write(event)  # rolled back alone if this fails
    await ledger.credit(to_account, amount)
```

Global scopes (multi-tenancy filters, soft-delete) attach once and apply to
every query on the model, with an explicit escape hatch for the query that
legitimately needs to see past them:

```python
User.add_global_scope(lambda qs: qs.filter(tenant_id=current_tenant()))

# from a handler, a job, or a script
await User.all()                     # tenant-filtered
await User.without_global_scopes()   # everyone, on purpose
```

## Background Work: Tasks, Queues, and a Scheduler

A job is a class with a `handle()` method; dispatching it is a classmethod
call from anywhere in the request path, a script, or another job:

```python
from sillo.work.queue.job import Job


class SendWelcomeEmail(Job):
    queue = "emails"
    tries = 3
    timeout = 30

    def __init__(self, user_id: str):
        self.user_id = user_id

    async def handle(self):
        user = await User.get(id=self.user_id)
        await mailer.send(user.email, "welcome")


# from a handler, a job, or a script
await SendWelcomeEmail.dispatch(new_user.id)
await SendWelcomeEmail.dispatch_after(300, new_user.id)  # five minutes out
```

The scheduler runs alongside the queue, on the same application lifecycle —
no separate cron process to keep in sync with the code it calls:

```python
from sillo.work.scheduler.manager import SchedulerManager
from sillo.work.scheduler.triggers import CronTrigger

scheduler = SchedulerManager()
scheduler.schedule(cleanup_expired_sessions, CronTrigger("0 3 * * *"))
scheduler.every(3600)(refresh_materialised_views)
```

Retries, timeouts, and rate limits are per-job middleware, not a global
setting every job inherits whether it needs it or not.

## WebSockets

A socket handler is declared the same way an HTTP one is — a coroutine
taking a context, with the same dependency injection and the same path
parameter conversion:

```python
from sillo import SilloApp
from sillo.websockets import WebSocketContext, WebSocketDisconnect

app = SilloApp()


@app.ws_route("/ws/rooms/{room_id:int}")
async def chat(ws: WebSocketContext, room_id: int):
    await ws.accept()
    try:
        while True:
            message = await ws.receive_text()
            await broadcast(room_id, message)
    except WebSocketDisconnect:
        await leave(room_id)
```

An HTTP route and a WebSocket route can share a path — a GraphQL endpoint
serving queries over POST and subscriptions over a socket, say — without one
shadowing the other or a mismatched scope reaching either handler.

## OpenAPI, Without a Second Source of Truth

The schema is generated from the same `request_model`, marker constraints,
and `useAuth` declarations that already enforce the request at runtime —
there is nothing to keep in sync by hand, and nothing the spec claims that
the framework does not also check:

```python
from sillo.openapi import Scalar, Swagger

app = SilloApp(title="My API", docs=[Swagger(path="/docs"), Scalar(path="/reference")])
```

Both interactive UIs read the one generated document; adding a second
renderer is a list entry, not a second integration.

## Storage, Cache, and Events

Storage buckets abstract local disk and S3-compatible object storage behind
one API, with signed URLs and per-bucket upload policies (content-type
allowlists, size limits, ownership checks) enforced before a byte is
written:

```python
from sillo.storage import BucketConfig, StorageConfig, setup_storage
from sillo.storage.policies import Owned

storage = setup_storage(app, StorageConfig(
    default="attachments",
    buckets={
        "attachments": BucketConfig(driver="local", root="storage/attachments"),
        "avatars": BucketConfig(driver="local", root="storage/avatars",
                                 policy=Owned(), accepts=("image/png", "image/jpeg")),
    },
))
```

Caching is one decorator, backend-agnostic between an in-memory store and
Redis:

```python
from sillo.cache import cache


@cache(ttl=120, tags=["catalog"])
async def get_product(product_id: int):
    return await Product.get(id=product_id)
```

The event system is a plain emitter (`on`, `emit`) with an optional Redis
transport for distributing events across processes — the same call site
either way, so a service can start on the in-memory transport and move to
Redis later without touching the code that emits or listens.

## What Sillo Provides

- Async ASGI application core, with lifespan-managed startup and shutdown
- HTTP routing, path converters, route groups, and mounted routers
- Response builders — `json`, `html`, `text`, `redirect`, `file`, `stream`, `sse`, `ndjson`, `xml`
- Pydantic request validation, with `Query`, `Header`, `Cookie`, `Path`, `Form` and `File` markers
- Dependency injection with nested dependencies and generator-based teardown
- Middleware pipeline, CORS, CSRF, rate limiting, and security headers
- Sessions, and pluggable auth backends for session, JWT and API-key credentials
- Users, groups, permissions, and the `useAuth` route gate
- OpenAPI generation and interactive documentation
- WebSocket routes, with `WebSocketContext` alongside `HttpContext`
- File uploads, streaming responses, static files, and frontend fallback serving
- Storage buckets over local disk or memory, with signed URLs and upload policies
- Cache abstraction with in-memory and Redis backends
- Event system, background tasks, a queue, and a scheduler
- Record layer for database-backed models, transactions, scopes, casting, and pagination
- Mail service utilities
- Sync and async test clients
- `sillo` command, and `sillo.console` for building a project's own

## Scope And Boundaries

Sillo runs on its own. No hosted service is required to put an application into production.

The framework is opinionated at the defaults and open at the boundaries. Auth backends, middleware, cache drivers, session stores, and hashing algorithms are contracts you can implement yourself, and anything the framework does on your behalf is something you can read, override, or replace.

Sillo ships a `sillo` command with the framework-level operations, built on `sillo.console`. Inside a project it also merges in whatever that project's `console.py` registers, so `sillo db:migrate` works without the framework owning the command set. The operations underneath stay plain functions in `sillo.record.commands`, `sillo.users.commands` and `sillo.work.commands`, so a project that wants different names writes its own console against them.

## Documentation

The documentation source lives in `docs/docs`.

Build it locally with:

```bash
cd docs/docs
bun run build
```

## Testing

Run the core test suite with:

```bash
python3 -m pytest -q
```

Some optional integrations require their extras to be installed before their tests can run.

## Release Principles

Sillo prioritizes:

- clear APIs and useful error messages
- strong defaults with replaceable internals
- production-oriented documentation
- compatibility, migration guidance, and honest release notes
- security and reliability before broad platform expansion

## License

BSD-3-Clause
