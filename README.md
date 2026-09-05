# Sillo

<p align="center">
  <img src="https://avatars.githubusercontent.com/u/199959103?s=400&u=2b9d0cb939318b295fefd0cdbc417f85d5d4ba87&v=4" alt="Sillo logo" width="160" height="160">
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

> [!IMPORTANT]
> **This branch is Sillo 1.0, and 1.0 is not released.**
>
> `main` is where 1.0 is being built. Nothing here is on PyPI, the API is still
> moving, and it is not backwards compatible with the released line — handlers
> take a single `ctx` argument, `sillo.graphql` and the WebSocket room layer
> have moved into [their own packages](https://docs.sillo.build/packages/), and
> more will change before it ships.
>
> **`pip install sillo-framework` installs 0.x, not this.** The released code
> lives on **[`v0.x`](https://github.com/sillohq/core/tree/v0.x)**, which is
> where fixes and dependency updates go and where releases are cut from. Its
> documentation is at
> **[docs.sillo.build/v0.x](https://docs.sillo.build/v0.x/guides/introduction/)**.
>
> Reading about the version you have installed? You want
> [`v0.x`](https://github.com/sillohq/core/tree/v0.x). Building against 1.0
> before it ships? Install from this branch:
>
> ```bash
> pip install "git+https://github.com/sillohq/core.git@main"
> ```
>
> The 1.0 documentation is at
> [docs.sillo.build/v1.0](https://docs.sillo.build/v1.0/guides/introduction/),
> and every page in it says the same thing at the top.

Sillo is the buildsmith framework for APIs, real-time systems, and production backends: fast, async, and built with everything you need to ship, with the ORM, authentication, queues, scheduler, and WebSockets already in place. The language does not change. You write the same Python, with the same type hints and the same `async`/`await`. What changes is how much is waiting for you when you start: routing, request validation, dependency injection, middleware, sessions, authentication, records, background work, WebSockets, OpenAPI, and testing are first-party modules sharing one configuration model.

Each of those is a solved problem with good packages behind it. The work that remains is the fitting, and that is what Sillo does once so you do not do it per project. One `auth=` declaration gates a route and writes its `securityScheme` into the OpenAPI spec. The queue and the scheduler start with the application lifecycle. Range requests, ETags, and content negotiation are middleware rather than something each project rewrites.

## Project Health

| | |
|---|---|
| Tests | 5,243 passing with none skipped, on CPython 3.10 through 3.14. Python 3.15 is in the matrix too and passes, but is not claimed on PyPI until it ships final |
| Coverage | 91%, with a 90% floor enforced in CI before anything is published |
| Types | Ships `py.typed`, so your own checker sees Sillo's annotations rather than `Any` |
| Type check | `ty` clean across the package |
| Lint and format | `ruff` clean, checked on every push |
| Dependencies | Five at install time. Everything else is an opt-in extra |
| License | BSD-3-Clause |

None of this is aspirational. The coverage floor fails the build rather than
printing a warning, the type check runs on every supported Python, and the
badges above read from those same workflows rather than from a number written
here by hand.

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

A dependency is called like a handler: its first positional parameter is the
context (`HttpContext`, or `WebSocketContext` on a socket route).

```python
from sillo import Depend, HttpContext, SilloApp

app = SilloApp()


async def get_current_user(ctx: HttpContext):
    return {"id": "user_1", "name": "Ada"}


@app.get("/me")
async def me(ctx: HttpContext, user=Depend(get_current_user)):
    return user
```

A dependency that reads the request does so straight off that first parameter:

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
