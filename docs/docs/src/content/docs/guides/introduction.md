---
title: Introduction
description: Learn what Sillo is, the core concepts behind it, what you can build, who it is for, and why teams choose it for serious Python software.
head:
- tag: meta
  attrs:
    property: og:title
    content: Introduction to Sillo
- tag: meta
  attrs:
    property: og:description
    content: Learn what Sillo is, the core concepts behind it, what you can build, who it is for, and why teams choose it for serious Python software.
---

#  Introduction

Sillo is a Python framework for building serious backend software: web applications, APIs, real-time systems, background workloads, internal tools, and business platforms.

It starts as a productive async web framework, but the goal is larger than routing requests. Sillo gives teams one coherent application model across HTTP, validation, dependency injection, records, authentication, sessions, background jobs, scheduling, caching, WebSockets, testing, and production operations.

The core idea is simple: teams should not have to assemble a fragile collection of unrelated tools before they can build reliable software.

##  What Sillo Is

Sillo Core is the open framework foundation of the Sillo platform. It is designed to help a project start small and grow without replacing its architecture every time the product becomes more real.

A Sillo application can begin with one route:

```python
from sillo import silloApp

app = silloApp()

@app.get("/")
async def home(request, response):
    return response.json({"message": "Hello from Sillo"})
```

From there, the same application model can grow into validated endpoints, authenticated routes, database-backed records, queues, scheduled work, WebSocket channels, and operational tooling.

##  Core Concepts

Sillo is built around a small set of concepts that appear consistently across the framework.

| Concept | What it means |
|---|---|
| `silloApp` | The application object. It owns routes, middleware, lifecycle hooks, state, and framework configuration. |
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

These concepts are meant to form one product language. A developer should not feel like every feature belongs to a different framework.

##  A Simple Example

This example shows a validated endpoint, path parameter, and response object working together.

```python
from pydantic import BaseModel

from sillo import silloApp
from sillo.core.http import Request, Response

app = silloApp()


class CreateProject(BaseModel):
    name: str
    private: bool = False


@app.post("/teams/{team_id}/projects", request_model=CreateProject)
async def create_project(
    request: Request,
    response: Response,
    team_id: str,
    project: CreateProject,
):
    return response.json(
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

##  Features

Sillo includes the common backend pieces teams repeatedly need:

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

Software teams rarely fail because they cannot write a route or database query. They struggle because the surrounding system becomes fragmented.

Sillo exists to make that surrounding system coherent.

The framework is guided by these principles:

- Strong defaults, open boundaries.
- Developer experience is part of the product.
- Enterprise readiness should be real, not theatrical.
- Operations belong in the product story.
- Documentation is part of the interface.
- Compatibility and upgrade paths matter.
- Open source earns trust.

Sillo is opinionated where teams benefit from a clear default, but it should remain transparent and replaceable at the boundaries. Convenience should not mean mystery. Enterprise readiness should not mean unnecessary ceremony.

##  Comparison

Sillo is not a drop-in clone of another Python framework. It combines ideas from productive web frameworks, async API frameworks, and full-stack application platforms.

| Framework | Good at | Sillo difference |
|---|---|---|
| Flask | Minimal apps, simple routing, extension-based composition. | Sillo provides a broader first-party application model for validation, DI, auth, records, jobs, scheduling, caching, WebSockets, and testing. |
| FastAPI | Typed APIs, Pydantic validation, async endpoints. | Sillo focuses on the complete backend lifecycle, explicit dependency patterns, first-party workload primitives, and a path toward operations. |
| Django | Batteries-included web apps, ORM, admin, mature ecosystem. | Sillo is async-first and designed around modern Python APIs, explicit handlers, background workloads, real-time systems, and deployment/operations coherence. |
| Starlette | Low-level ASGI toolkit and primitives. | Sillo builds a higher-level product framework on top of ASGI ideas so teams do not assemble every application concern manually. |

The goal is not to win by having every feature. The goal is to make the repeated work of serious backend development feel like one designed system.

##  The Platform Direction

Sillo Core is the foundation. The broader platform direction includes first-party products for visual administration, managed deployment, server operations, identity, observability, templates, and integrations.

That long-term direction matters because backend software does not stop at code. Teams also need to deploy it, operate it, secure it, observe it, govern access, and help non-engineering teams use it safely.

Sillo’s promise is to help developers move from an idea to dependable enterprise software with fewer disconnected decisions, clearer systems, and tools that grow with their ambition.

##  Next Step

Continue with [Installation](/guides/installation/) to install Sillo with `uv` and build your first application.


##  How the pieces fit

sillo is an ASGI framework, which means it speaks the same protocol as
uvicorn, granian, hypercorn, and every ASGI middleware in the ecosystem.
Everything below builds on that one interface.

A request arrives at the server, which hands sillo a `scope`, a
`receive`, and a `send`. sillo builds a `Request`, runs it through the
[middleware stack](/guides/middleware/), matches it against the
[router](/guides/routing/), resolves
[dependencies](/guides/dependency-injection/) and
[validates inputs](/guides/validation/), calls your
[handler](/guides/handlers/), and serializes what comes back.

Around that core sit optional subsystems, each independent: an
[ORM layer](/guides/record/), [background work](/guides/work/),
[WebSockets](/guides/websockets/), [templating](/guides/templating/),
[caching](/guides/cache/), [mail](/guides/services/mail/), and an
[HTTP client](/guides/http/client/). None of them are required. An
application that only serves JSON needs none of them.

##  What to read next

The path through the documentation depends on what you are building.

**A JSON API.** [Routing](/guides/routing/) →
[Handlers](/guides/handlers/) → [Validation](/guides/validation/) →
[Error Handling](/guides/error-handling/). That is enough to build
something real. Add [Record](/guides/record/) when you need a database
and [Authentication](/guides/authentication/) when you need users.

**A server-rendered application.** [Routing](/guides/routing/) →
[Templating](/guides/templating/) → [Sessions](/guides/sessions/) →
[CSRF](/guides/csrf/). The last is not optional if your forms
authenticate with cookies.

**Something real-time.** [WebSockets](/guides/websockets/) first, and
read its scaling section before you design anything, because the answer
changes what you build.

**Anything going to production.** [Security](/guides/security/),
[Startup & Shutdown](/guides/startups-and-shutdowns/), and
[Concurrency](/guides/concurrency/) — in that order. The third one is
where most performance surprises come from.

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

**Handlers take `request, response`.** Everything after those two is
injected — validated parameters, dependencies, the request body.

**`app.state` is process-wide, `request.state` is per-request.** The
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

For questions the guides do not answer, the source is small enough to
read. Most modules are a few hundred lines, the abstractions are shallow,
and the answer to "what does this actually do" is usually one file away —
which is how several of the warnings in these pages were found.


##  Prerequisites

These guides assume working Python and a rough familiarity with HTTP —
methods, status codes, headers, and what a request body is. They do not
assume prior experience with an async framework; where `async`/`await`
matters, the page explains what it changes.

Python 3.10 or newer is required. Several guides use `match`, `X | None`
syntax, and `asyncio.timeout`, which is 3.11+.


##  A first application

The smallest thing that runs, to anchor everything above:

```python title="main.py"
from sillo import silloApp

app = silloApp()


@app.get("/")
async def index(request, response):
    return response.json({"status": "ok"})
```

```bash
sillo run --app main:app --reload
```

That is a complete ASGI application. Everything else in these guides —
validation, the ORM, background work, WebSockets — is something you add
to this when you need it, and nothing is required to get here.
