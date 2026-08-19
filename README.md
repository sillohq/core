# Sillo

<p align="center">
  <img src="https://avatars.githubusercontent.com/u/199959103?s=400&u=2b9d0cb939318b295fefd0cdbc417f85d5d4ba87&v=4" alt="Sillo logo" width="160" height="160">
</p>

<p align="center">
  <strong>Python With the Pieces Already in Place.</strong>
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

Sillo is an async Python web framework for APIs, web applications, real-time systems, and business backends. The language does not change. You write the same Python, with the same type hints and the same `async`/`await`. What changes is how much is waiting for you when you start: routing, request validation, dependency injection, middleware, sessions, authentication, records, background work, WebSockets, OpenAPI, and testing are first-party modules sharing one configuration model.

Each of those is a solved problem with good packages behind it. The work that remains is the fitting, and that is what Sillo does once so you do not do it per project. One `auth=` declaration gates a route and writes its `securityScheme` into the OpenAPI spec. The queue and the scheduler start with the application lifecycle. Range requests, ETags, and content negotiation are middleware rather than something each project rewrites.

## Project Health

| | |
|---|---|
| Tests | 4,746 passing with none skipped, on CPython 3.10 through 3.14. Python 3.15 is in the matrix too and passes, but is not claimed on PyPI until it ships final |
| Coverage | 91%, with a 90% floor enforced in CI before anything is published |
| Types | Ships `py.typed`, so your own checker sees Sillo's annotations rather than `Any` |
| Type check | `ty` clean across the package |
| Lint and format | `ruff` clean, checked on every push |
| Dependencies | Seven at install time. The other 14 feature groups are opt-in extras |
| License | BSD-3-Clause |

None of this is aspirational. The coverage floor fails the build rather than
printing a warning, the type check runs on every supported Python, and the
badges above read from those same workflows rather than from a number written
here by hand.

## Requirements

- Python 3.10+
- `uv` for project and dependency management

## Installation

```bash
uv add sillo-framework
```

For optional feature groups:

```bash
uv add "sillo-framework[templating]"
uv add "sillo-framework[jwt]"
uv add "sillo-framework[cache]"
uv add "sillo-framework[record]"
uv add "sillo-framework[graphql]"
```

For a full development setup:

```bash
uv add "sillo-framework[all]"
```

## Hello World

```python
from sillo import SilloApp

app = SilloApp(title="My API")


@app.get("/")
async def home(request, response):
    return response.json({"message": "Hello from Sillo"})
```

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
from sillo import SilloApp

app = SilloApp()


class CreateUser(BaseModel):
    name: str
    email: str


@app.post("/users", request_model=CreateUser)
async def create_user(request, response, user: CreateUser):
    return response.json(user.model_dump(), status_code=201)
```

The validated model is also available as `request.validated_data`.

## Dependency Injection

Use `Depend` to inject request-scoped dependencies into handlers.

```python
from sillo import Depend, SilloApp

app = SilloApp()


async def get_current_user():
    return {"id": "user_1", "name": "Ada"}


@app.get("/me")
async def me(request, response, user=Depend(get_current_user)):
    return response.json(user)
```

When a dependency needs the current request:

```python
from sillo import Depend


def auth_header(request=Depend(get_request=True)):
    return request.headers.get("Authorization")
```

## Routing

```python
from sillo import Router, SilloApp

app = SilloApp()
api = Router(prefix="/api")


@api.get("/users/{user_id:int}")
async def get_user(request, response, user_id: int):
    return response.json({"id": user_id})


app.mount_router(api)
```

## What Sillo Provides

- Async ASGI application core
- HTTP routing, route groups, and mounted routers
- Request and response helpers
- Pydantic request validation
- Dependency injection with nested dependencies
- Query, header, and cookie parameter helpers
- Middleware pipeline
- CORS and CSRF support
- Sessions and authentication utilities
- API keys, JWT helpers, users, permissions, and guards
- OpenAPI generation and interactive docs
- File uploads, streaming responses, static files, and frontend fallback serving
- WebSockets, consumers, channels, groups, events, and history helpers
- Cache abstraction with memory and Redis support
- Event system and background work primitives
- Record layer for database-backed models, transactions, scopes, casting, and pagination
- Mail service utilities
- Sync and async test clients
- Model admin at `/admin/` that authenticates against your own user model
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
