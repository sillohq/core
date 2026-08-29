---
title: Introduction
description: "Sillo is the buildsmith framework for APIs, real-time systems and production backends: fast, async, and built with everything you need to ship, with the ORM, authentication, admin, queues, scheduler and WebSockets already in place."
head:
- tag: meta
  attrs:
    property: og:title
    content: "Sillo: The Buildsmith Framework"
- tag: meta
  attrs:
    property: og:description
    content: Fast, async, and built with everything you need to ship, with the ORM, auth, admin, queues, scheduler and WebSockets designed against each other and sharing one config model.
---

#  Introduction

Sillo is the buildsmith framework: fast, async, and built with everything you need to ship.

The language does not change. You write the same Python, with the same type hints and the same `async`/`await` you already know. What changes is how much of the backend is waiting for you when you start: routing, validation, dependency injection, the ORM, authentication, sessions, background jobs, scheduling, caching, WebSockets, the admin, and the testing tools are all first-party modules that share one configuration model.

Each of those is a solved problem, and there are good packages for every one of
them. The work that remains is the fitting: reconciling interfaces,
configuration styles, failure modes, and upgrade cycles that were never
designed against each other. Sillo does that fitting once, so your time goes
into the product instead.

##  What Sillo Is

Sillo Core is the open foundation of the framework. It is designed to help a project start small and grow without replacing its architecture every time the product becomes more real.

A Sillo application can begin with one route:

```python
from sillo import SilloApp, HttpContext, json

app = SilloApp()

@app.get("/")
async def home(ctx: HttpContext):
    return json({"message": "Hello from Sillo"})
```

From there, the same application model can grow into validated endpoints, authenticated routes, database-backed records, queues, scheduled work, WebSocket channels, and operational tooling.

##  Core Concepts

Sillo is built around a small set of concepts that appear consistently across the framework.

| Concept | What it means |
|---|---|
| `SilloApp` | The application object. It owns routes, middleware, lifecycle hooks, state, and framework configuration. |
| Request | The incoming HTTP boundary: headers, query params, path params, body data, cookies, user state, and request-scoped data. |
| Response | A fluent response builder for JSON, text, HTML, files, streams, redirects, cookies, headers, and status codes. |
| Routes | Decorated functions or router definitions that bind HTTP methods and paths to handlers. |
| Middleware | Request/response pipeline units for cross-cutting concerns such as CORS, auth, sessions, rate limits, ETags, and content negotiation. |
| Validation | `request_model` turns untrusted request bodies into validated Pydantic models at the route boundary. |
| Dependency Injection | `Depend` wires services, shared state, request-aware providers, and reusable business logic into handlers. |
| Record | Sillo’s database layer on top of Tortoise ORM for models, setup, serialization, casting, scopes, pagination, and persistence helpers. |
| Workloads | Jobs, queues, events, scheduler managers, and background work that run outside the request cycle. |
| WebSockets | Real-time connections, consumers, channels, and broadcast patterns for interactive systems. |
| Testing | Test clients and framework patterns for exercising routes, validation, dependencies, auth, jobs, and application behaviour. |

These concepts recur across the framework in the same shape. Reading one subsystem teaches you how to read the next, so no feature feels like it was borrowed from somewhere else.

##  A Simple Example

This example shows a validated endpoint, path parameter, and response object working together.

```python
from pydantic import BaseModel
from sillo import SilloApp, HttpContext, json

app = SilloApp()


class CreateProject(BaseModel):
    name: str
    private: bool = False


@app.post("/teams/{team_id}/projects", request_model=CreateProject)
async def create_project(
    ctx: HttpContext,
    team_id: str,
    project: CreateProject,
):
    return json(
        {
            "team_id": team_id,
            "project": project.model_dump(),
            "status": "created",
        },
        status_code=201,
    )
```

What is happening:

- `team_id` comes from the path and is passed into the handler.
- `request_model=CreateProject` validates the request body.
- The validated Pydantic object can be injected into the handler.
- The response object builds a JSON response with a status code.

##  What Is Already in Place

These are first-party modules, in the framework, each with a page in these docs:

- async ASGI application foundation
- routing, route groups, routers, and sub-apps
- request and response helpers
- request validation with Pydantic
- dependency injection
- middleware pipeline
- CORS, CSRF, cookies, sessions, and security helpers
- authentication, permissions, API keys, JWT, and session auth
- Record ORM layer with database setup, models, casts, scopes, pagination, factories, and upserts
- background jobs, queues, workers, events, and scheduling
- caching with memory and Redis-compatible backends
- WebSockets, consumers, channels, and real-time patterns
- OpenAPI generation
- static files, templating, file uploads, and streaming responses
- test clients and testing utilities
- HTTP client utilities
- content negotiation, ETags, request lifecycle helpers, and protocol status constants under `sillo.http`

##  What Can You Build With Sillo?

Sillo is useful for many backend-heavy products:

- JSON APIs for web and mobile applications
- SaaS backends with teams, users, roles, billing, jobs, and dashboards
- internal tools and admin systems
- real-time applications using WebSockets and channels
- workflow systems with queues, retries, and scheduled jobs
- data-backed business platforms with records, pagination, permissions, and audit-friendly patterns
- API gateways and integration services
- background processing systems
- customer portals and product backends
- applications that need to move from prototype to production without changing frameworks

##  Who Is Sillo For?

Sillo is designed for developers and organisations building serious software with Python.

It is especially useful for:

- independent developers who want a productive framework that can grow with a project
- startups that need speed without accumulating avoidable operational debt
- product teams building APIs, SaaS products, internal systems, and real-time applications
- agencies that want repeatable backend foundations for client work
- mid-market engineering teams that need standardisation, visibility, and governance
- enterprise teams that care about security, lifecycle, compatibility, deployment choice, and operational clarity
- educators and communities teaching modern Python backend development

Sillo is less suitable if you only need a tiny script, a one-off HTTP handler, or a framework that intentionally avoids owning anything beyond routing.

##  Why Sillo?

Writing a route or a database query is rarely the hard part. The time goes into the system around them: making a dozen well-built components agree on configuration, on how they start and stop, on what a user is, and on what happens when one of them fails.

Sillo puts those pieces in place already agreeing with each other. That coherence shows up in small, checkable ways. One `auth=` declaration gates a route and writes its `securityScheme` into the OpenAPI document, so the gate and the spec cannot drift apart. The scheduler registers on `app.state` and starts with the application lifecycle. Range requests, ETags, and content negotiation are middleware rather than something each project rewrites.

The framework is guided by these principles:

- Strong defaults, open boundaries.
- Convenience without mystery.
- Documentation is part of the interface.
- Compatibility and upgrade paths matter.
- Anything the framework does on your behalf is something you can read, override, or replace.

Sillo is opinionated where a clear default helps, and transparent at the boundaries. Auth backends, middleware, cache drivers, session stores, and hashing algorithms are all contracts you can implement yourself.

##  Comparison

Sillo is not a drop-in clone of another Python framework, and the frameworks below are all good at what they are built for. The difference is scope: how much of the application is first-party and designed against the rest.

| Framework | Good at | Where Sillo differs |
|---|---|---|
| Flask | Minimal apps, simple routing, extension-based composition. | A broader first-party surface: validation, DI, auth, records, jobs, scheduling, caching, WebSockets, and testing all in the framework. |
| FastAPI | Typed APIs, Pydantic validation, async endpoints. | The same typed, async request layer, plus the ORM, admin, durable queue, and scheduler as first-party modules on one config model. |
| Django | A complete web framework with ORM, admin, and a mature ecosystem. | The same completeness, built async-first around `async`/`await` handlers, background workloads, and real-time systems. |
| Starlette | A low-level ASGI toolkit and primitives. | A higher-level application framework over the same ASGI foundation, so the application concerns above are already assembled. |

Ecosystem size and years in production are real advantages, and Django, Flask, and FastAPI have both. Sillo's argument is scope and coherence, not maturity.

##  How the pieces fit

sillo is an ASGI framework, which means it speaks the same protocol as
uvicorn, granian, hypercorn, and every ASGI middleware in the ecosystem.
Everything below builds on that one interface.

A request arrives at the server, which hands sillo a `scope`, a
`receive`, and a `send`. sillo builds a `HttpContext`, runs it through the
[middleware stack](/v1.0/guides/middleware/), matches it against the
[router](/v1.0/guides/routing/), resolves
[dependencies](/v1.0/guides/dependency-injection/) and
[validates inputs](/v1.0/guides/validation/), calls your
[handler](/v1.0/guides/handlers/), and serializes what comes back.

Around that core sit optional subsystems, each independent: an
[ORM layer](/v1.0/guides/record/), [background work](/v1.0/guides/work/),
[WebSockets](/v1.0/guides/websockets/), [templating](/v1.0/guides/templating/),
[caching](/v1.0/guides/cache/), [mail](/v1.0/guides/services/mail/), and an
[HTTP client](/v1.0/guides/http/client/). None of them are required. An
application that only serves JSON needs none of them.

##  What to read next

The path through the documentation depends on what you are building.

**A JSON API.** [Routing](/v1.0/guides/routing/) →
[Handlers](/v1.0/guides/handlers/) → [Validation](/v1.0/guides/validation/) →
[Error Handling](/v1.0/guides/error-handling/). That is enough to build
something real. Add [Record](/v1.0/guides/record/) when you need a database
and [Authentication](/v1.0/guides/authentication/) when you need users.

**A server-rendered application.** [Routing](/v1.0/guides/routing/) →
[Templating](/v1.0/guides/templating/) → [Sessions](/v1.0/guides/sessions/) →
[CSRF](/v1.0/guides/csrf/). The last is not optional if your forms
authenticate with cookies.

**Something real-time.** [WebSockets](/v1.0/guides/websockets/) first, and
read its scaling section before you design anything, because the answer
changes what you build.

**Anything going to production.** [Security](/v1.0/guides/security/), [Startup &
Shutdown](/v1.0/guides/startups-and-shutdowns/), and
[Concurrency](/v1.0/guides/concurrency/), in that order. The third one is where most
performance surprises come from.

##  A note on this documentation

These guides document what the framework does, including where it does
something surprising or wrong. Where a function has a defect, the page
covering it says so, shows the failure, and gives a working alternative.

That is deliberate. A guide that describes intended behaviour is a guide
that costs you an afternoon the first time reality differs. Every
`:::danger` and `:::caution` block in these pages marks something
verified by running it.


##  Conventions used throughout

A few things recur in every guide and are worth knowing once.

**Handlers take `request, response`.** Everything after those two is injected:
validated parameters, dependencies, the request body.

**`app.state` is process-wide, `ctx.state` is per-request.** The
first is written by lifespan hooks; the second by middleware.

**`setup_*` functions are idempotent.** `setup_record`, `setup_work`, and
`setup_mail` each store an object in `app.state` and register lifecycle
hooks, and calling one twice returns the existing object rather than
reconfiguring.

**Async by default.** The framework, the ORM, and the HTTP client are all
async. Synchronous handlers work and run in a thread; synchronous calls
inside an async handler block everything.

**Every page ends with "What not to do".** Those lists are the compressed
version of the page, and they are the part worth re-reading before
shipping.


##  Getting help

The guides are organised by subsystem, and the sidebar mirrors the
package layout, so `sillo.record` is under Record and `sillo.work` under
Work. If you know the module, you can find the page.

For questions the guides do not answer, the source is small enough to read.
Most modules are a few hundred lines, the abstractions are shallow, and the
answer to "what does this actually do" is usually one file away, which is how
several of the warnings in these pages were found.


##  Prerequisites

These guides assume working Python and a rough familiarity with HTTP: methods,
status codes, headers, and what a request body is. They do not assume prior
experience with an async framework; where `async`/`await` matters, the page
explains what it changes.

Python 3.10 or newer is required. Several guides use `match`, `X | None`
syntax, and `asyncio.timeout`, which is 3.11+.


##  A first application

The smallest thing that runs, to anchor everything above:

```python title="main.py"
from sillo import SilloApp, HttpContext, json

app = SilloApp()


@app.get("/")
async def index(ctx: HttpContext):
    return json({"status": "ok"})
```

```bash
uvicorn main:app --reload
```

That is a complete ASGI application. Everything else in these guides
(validation, the ORM, background work, WebSockets) is something you add to this
when you need it, and nothing is required to get here.

##  Next step

Continue with [Installation](/v1.0/guides/installation/) to install Sillo with
`uv` and build your first application.
