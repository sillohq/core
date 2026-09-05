---
title: What's in the Box
description: What `uv add sillo-framework` actually installs, which subsystems are extras you opt into, which live in separate packages, and the tools that sit alongside the framework.
head:
- tag: meta
  attrs:
    property: og:title
    content: "What's in the Box: the Sillo surface, mapped"
- tag: meta
  attrs:
    property: og:description
    content: Core, extras, packages and tools — where each line falls and why.
---

#  What's in the Box

Sillo is described as batteries-included, which is true about its *surface* and
misleading about its *install*. The base install is five packages. Everything
that carries a third-party dependency is something you ask for.

This page is the map: what comes with the framework, what is one flag away,
what is a separate install, and what is a tool rather than a library.

##  The base install

```bash
uv add sillo-framework
```

Five dependencies: `uvicorn`, `anyio`, `python-multipart`, `pydantic`, and
`typing-extensions` below Python 3.13. Python 3.10 or newer.

What that gives you, with no further installs:

- the async ASGI application, [routing](/v1.0/guides/routing/),
  [routers and sub-apps](/v1.0/guides/routers-and-subapps/)
- [handlers](/v1.0/guides/handlers/), the
  [request context](/v1.0/guides/request-info/) and the
  [response builder](/v1.0/guides/sending-responses/)
- [request validation](/v1.0/guides/validation/) with Pydantic, and
  [OpenAPI generation](/v1.0/guides/openapi/) from the same declarations
- [dependency injection](/v1.0/guides/dependency-injection/)
- the [middleware pipeline](/v1.0/guides/middleware/), with CORS, CSRF,
  [security headers](/v1.0/guides/security/), sessions, rate limiting, ETags
  and [content negotiation](/v1.0/guides/content-negotiation/) as first-party
  middleware
- [authentication](/v1.0/guides/authentication/),
  [permissions](/v1.0/guides/permissions/),
  [API keys](/v1.0/guides/api-keys/) and
  [session auth](/v1.0/guides/session-auth/) (JWT needs the `jwt` extra)
- [password hashing](/v1.0/guides/hashing/), falling back to `pbkdf2_sha256`
  from the standard library when no backend is installed
- [background tasks, queues, jobs and the scheduler](/v1.0/guides/work/)
- [caching](/v1.0/guides/cache/) and [events](/v1.0/guides/events/), in memory
- [WebSockets](/v1.0/guides/websockets/)
- [object storage](/v1.0/guides/storage/) with local and in-memory drivers
- [static files](/v1.0/guides/static-files/), file uploads and
  [streaming responses](/v1.0/guides/streaming-response/)
- the [`sillo` CLI](/v1.0/cli/) — a console script, not an extra
- the [test client](/v1.0/guides/start/testing/) and an
  [HTTP client](/v1.0/guides/http/client/)
- [typed configuration](/v1.0/guides/configuration/) and
  [`.env` loading](/v1.0/guides/environment/)

Note what is *not* on that list: a database, a Redis client, and a JWT library.

##  The extras

Each of these adds one dependency, for one subsystem.

| Extra | Brings | For |
|---|---|---|
| `record` | `tortoise-orm` | The [ORM](/v1.0/orm/) — models, migrations, factories |
| `jwt` | `pyjwt` | [JWT authentication](/v1.0/guides/jwt-auth/) |
| `cache` | `redis` | [Caching](/v1.0/guides/cache/) across processes |
| `events` | `redis` | [Event distribution](/v1.0/guides/events/) across processes |
| `crypto` | `cryptography` | The `encrypted` cast and `sillo.helpers.crypto` |
| `storage-s3` | `httpx` | The [S3 storage driver](/v1.0/guides/storage/) |
| `mail` | `jinja2` | Templated email bodies |
| `hashing-bcrypt` | `bcrypt` | bcrypt password hashing |
| `hashing-argon2` | `argon2-cffi` | Argon2 password hashing |
| `hashing-scrypt` | `scrypt` | scrypt password hashing |
| `hashing-all` | all three, plus `passlib` | All of the above |
| `granian` | `granian` | An alternative ASGI server to uvicorn |
| `all` | everything above | Not thinking about it |

```bash
uv add "sillo-framework[record,jwt,hashing-argon2]"
uv add "sillo-framework[all]"
```

Two of these are worth a second look. The S3 driver depends on `httpx` rather
than `boto3` — request signing is a few dozen lines of HMAC, and `boto3` is a
very large synchronous dependency to carry for it. And the hashing extras are
separate rather than bundled because a project standardises on one algorithm;
installing three compiled backends to use one is exactly the imposition the
extras exist to avoid.

##  Separate packages

These are not extras. They are their own distributions, versioned and released
on their own cadence, because each has a dependency, a release rhythm, or a
scope that the framework should not carry on everybody's behalf.

| Package | Install | Import | What it is |
|---|---|---|---|
| [Wire](/packages/wire/) | `sillo-wire` | `sillo.wire` | Rooms, presence, replay and fan-out for WebSockets |
| [GraphQL](/packages/graphql/) | `sillo-graphql` | `sillo.graphql` | A production GraphQL endpoint over a Strawberry schema |
| [Warder](/packages/warder/) | `warder` | `warder` | A declarative admin panel over your models, with a React interface |
| [Inertia](/v1.0/guides/inertia/) | `sillo-inertia` | `sillo_inertia` | Server-driven pages with React or Vue, no API layer |
| [OAuth](/v1.0/guides/oauth/) | `sillo-oauth` | `sillo_oauth` | Social login and OAuth2 providers |

Wire and GraphQL extend the framework's own surface, so they also take a name
inside it: `from sillo.wire import Hub` and `from sillo_wire import Hub` bind
the same class. The others keep their own top-level names — Warder most
deliberately of all, because it is not an extension of `sillo` but an
application you mount on yours. The [Packages index](/packages/) explains how
the aliasing works and why it is not a directory shipped into the framework.

##  The tools

Not libraries you import — programs you run.

| Tool | Install | What it does |
|---|---|---|
| [`sillo`](/v1.0/cli/) | ships with the framework | Migrations, users, queues, the scheduler, and your own commands |
| [`sillo-start`](/v1.0/start/) | `uv tool install sillo-start` | Creates a project by copying a working application, not by generating one |
| `sillo-vise` | `uv add sillo-vise` | `vise serve` — the development server, with readable logging and the Foreman operations dashboard mounted beside your app |
| [`@sillo/atlas`](/v1.0/advanced/atlas/) | npm | The OpenAPI reference UI and API client, ~79 KB with no runtime dependencies |

##  What moved in 1.0

If you are reading 0.x code or older articles, four things are not where they
used to be.

| Was, in 0.x | Is, in 1.0 |
|---|---|
| Built-in admin panel | [`warder`](/packages/warder/) |
| HTML templating layer (Jinja) | Removed; `mail` is the one place a template is still rendered |
| WebSocket rooms, channels and groups | [`sillo-wire`](/packages/wire/) |
| `sillo.graphql` in the framework | [`sillo-graphql`](/packages/graphql/), claiming the same import name |

The same reason applies to all four: each had grown a dependency, a release
cadence or a scope of its own. A package that claims a name the framework still
uses refuses to load and says so, rather than quietly shadowing it — which is
why `sillo-graphql` works against 1.0 and not against 0.x.

##  Deciding what you need

A useful default for a JSON API with users and a database:

```bash
uv add "sillo-framework[record,jwt,hashing-argon2]"
```

Add `cache` and `events` when you run more than one process. Add
[`sillo-wire`](/packages/wire/) when WebSockets need rooms rather than
connections. Add [`warder`](/packages/warder/) when somebody who is not you
needs to edit the data. Add nothing else until something asks for it.

If you would rather start from a working application than assemble one,
[`sillo-start`](/v1.0/start/) copies the
[official starter](/v1.0/guides/start/) — session auth against a real user
model, migrations, a JSON API and a queue, all already wired together.

##  Related

- [Installation](/v1.0/guides/installation/) — the actual install steps
- [Packages](/packages/) — the manuals for Wire, GraphQL and Warder
- [Philosophy](/v1.0/guides/philosophy/) — why the line between core and extra
  falls where it does
- [Frequently Asked Questions](/v1.0/guides/faq/) — including what breaks
  between 0.x and 1.0
