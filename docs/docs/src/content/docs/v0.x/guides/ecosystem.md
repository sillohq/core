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
what is a separate install, and what is a tool rather than a library. It
describes the 0.x line — the released one. Four of these boundaries move in
1.0, and the last section says which.

##  The base install

```bash
uv add sillo-framework
```

Five dependencies: `uvicorn`, `anyio`, `python-multipart`, `pydantic`, and
`typing-extensions` below Python 3.13. Python 3.10 or newer.

What that gives you, with no further installs:

- the async ASGI application, [routing](/v0.x/guides/routing/),
  [routers and sub-apps](/v0.x/guides/routers-and-subapps/)
- [handlers](/v0.x/guides/handlers/), the
  [request context](/v0.x/guides/request-info/) and the
  [response builder](/v0.x/guides/sending-responses/)
- [request validation](/v0.x/guides/validation/) with Pydantic, and
  [OpenAPI generation](/v0.x/guides/openapi/) from the same declarations
- [dependency injection](/v0.x/guides/dependency-injection/)
- the [middleware pipeline](/v0.x/guides/middleware/), with CORS, CSRF,
  [security headers](/v0.x/guides/security/), sessions, rate limiting, ETags
  and [content negotiation](/v0.x/guides/content-negotiation/) as first-party
  middleware
- [authentication](/v0.x/guides/authentication/),
  [permissions](/v0.x/guides/permissions/),
  [API keys](/v0.x/guides/api-keys/) and
  [session auth](/v0.x/guides/session-auth/) (JWT needs the `jwt` extra)
- [password hashing](/v0.x/guides/hashing/), falling back to `pbkdf2_sha256`
  from the standard library when no backend is installed
- [background tasks, queues, jobs and the scheduler](/v0.x/guides/work/)
- [caching](/v0.x/guides/cache/) and [events](/v0.x/guides/events/), in memory
- [WebSockets](/v0.x/guides/websockets/)
- [object storage](/v0.x/guides/storage/) with local and in-memory drivers
- [static files](/v0.x/guides/static-files/), file uploads and
  [streaming responses](/v0.x/guides/streaming-response/)
- the [`sillo` CLI](/v0.x/cli/) — a console script, not an extra
- the [test client](/v0.x/guides/start/testing/) and an
  [HTTP client](/v0.x/guides/http/client/)
- [typed configuration](/v0.x/guides/configuration/) and
  [`.env` loading](/v0.x/guides/environment/)

Note what is *not* on that list: a database, a Redis client, and a JWT library.

###  Also in the framework, in 0.x only

Four subsystems are part of the framework on this line and become separate
packages in 1.0. They are documented here because this is the released
version, not because they are permanent:

- the [admin panel](/v0.x/orm/admin/), over your Record models
- [HTML templating](/v0.x/guides/templating/) with Jinja
- [WebSocket channels and groups](/v0.x/guides/websockets/channels/) — rooms,
  not just connections
- [GraphQL](/v0.x/guides/graphql/) over a Strawberry schema

See [What moves in 1.0](#what-moves-in-10) before you build something large on
any of them.

##  The extras

Each of these adds one dependency, for one subsystem.

| Extra | Brings | For |
|---|---|---|
| `record` | `tortoise-orm` | The [ORM](/v0.x/orm/) — models, migrations, factories |
| `jwt` | `pyjwt` | [JWT authentication](/v0.x/guides/jwt-auth/) |
| `cache` | `redis` | [Caching](/v0.x/guides/cache/) across processes |
| `events` | `redis` | [Event distribution](/v0.x/guides/events/) across processes |
| `crypto` | `cryptography` | The `encrypted` cast and `sillo.helpers.crypto` |
| `storage-s3` | `httpx` | The [S3 storage driver](/v0.x/guides/storage/) |
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

:::note
The extra names above are the ones the current release defines. They have
shifted across the 0.x line as subsystems moved — older 0.x releases carried
`templating` and `graphql` extras, and some pages in this manual still name
them. The package metadata for the version you actually installed is the
authority; `uv pip show sillo-framework` will tell you.
:::

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
| [GraphQL](/packages/graphql/) | `sillo-graphql` | `sillo.graphql` | A production GraphQL endpoint over a Strawberry schema — see the caveat below |
| [Warder](/packages/warder/) | `warder` | `warder` | A declarative admin panel over your models, with a React interface |
| [Inertia](/v0.x/guides/inertia/) | `sillo-inertia` | `sillo_inertia` | Server-driven pages with React or Vue, no API layer |
| [OAuth](/v0.x/guides/oauth/) | `sillo-oauth` | `sillo_oauth` | Social login and OAuth2 providers |

Wire and GraphQL extend the framework's own surface, so they also take a name
inside it: `from sillo.wire import Hub` and `from sillo_wire import Hub` bind
the same class. The others keep their own top-level names — Warder most
deliberately of all, because it is not an extension of `sillo` but an
application you mount on yours. The [Packages index](/packages/) explains how
the aliasing works and why it is not a directory shipped into the framework.

:::caution
`sillo-graphql` claims `sillo.graphql`, which the framework itself still ships
on this line. A package cannot claim a name the framework is using, so against
0.x the alias refuses to load and says why — rather than quietly shadowing the
built-in module. On 0.x, use the
[framework's own GraphQL support](/v0.x/guides/graphql/); `sillo-graphql` is
for 1.0.
:::

##  The tools

Not libraries you import — programs you run.

| Tool | Install | What it does |
|---|---|---|
| [`sillo`](/v0.x/cli/) | ships with the framework | Migrations, users, queues, the scheduler, and your own commands |
| [`sillo-start`](/v0.x/start/) | `uv tool install sillo-start` | Creates a project by copying a working application, not by generating one |
| `sillo-vise` | `uv add sillo-vise` | `vise serve` — the development server, with readable logging and the Foreman operations dashboard mounted beside your app |
| [`@sillo/atlas`](/v0.x/advanced/atlas/) | npm | The OpenAPI reference UI and API client, ~79 KB with no runtime dependencies |

##  What moves in 1.0

Four things leave the framework in 1.0. If you are starting something now and
expect to follow the framework forward, these are the four to make a decision
about rather than discover later.

| Here, in 0.x | In 1.0 |
|---|---|
| Built-in [admin panel](/v0.x/orm/admin/) | [`warder`](/packages/warder/) |
| [HTML templating layer](/v0.x/guides/templating/) (Jinja) | Removed; templated email bodies are the one place a template is still rendered |
| [WebSocket rooms, channels and groups](/v0.x/guides/websockets/channels/) | [`sillo-wire`](/packages/wire/) |
| [`sillo.graphql`](/v0.x/guides/graphql/) in the framework | [`sillo-graphql`](/packages/graphql/), claiming the same import name |

The same reason applies to all four: each had grown a dependency, a release
cadence or a scope of its own, and keeping it in core made everybody carry it.

None of them disappear — three become installs and one becomes a design
decision you make yourself. The templating removal is the only one without a
drop-in replacement: if you are rendering server-side HTML today, decide
whether that is where the application is going before 1.0 makes the decision
for you.

##  Deciding what you need

A useful default for a JSON API with users and a database:

```bash
uv add "sillo-framework[record,jwt,hashing-argon2]"
```

Add `cache` and `events` when you run more than one process. Add nothing else
until something asks for it.

For rooms and presence over WebSockets, and for an admin panel, 0.x has both in
the framework — see the [channels guide](/v0.x/guides/websockets/channels/) and
the [admin](/v0.x/orm/admin/). [`sillo-wire`](/packages/wire/) and
[`warder`](/packages/warder/) are where those go in 1.0.

If you would rather start from a working application than assemble one,
[`sillo-start`](/v0.x/start/) copies the
[official starter](/v0.x/guides/start/) — session auth against a real user
model, migrations, a JSON API and a queue, all already wired together.

##  Related

- [Installation](/v0.x/guides/installation/) — the actual install steps
- [Packages](/packages/) — the manuals for Wire, GraphQL and Warder
- [Philosophy](/v0.x/guides/philosophy/) — why the line between core and extra
  falls where it does
- [Frequently Asked Questions](/v0.x/guides/faq/) — including what breaks
  between 0.x and 1.0
