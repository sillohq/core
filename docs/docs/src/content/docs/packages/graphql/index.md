---
title: GraphQL
description: "sillo-graphql — a production GraphQL endpoint over a Strawberry schema: sillo-style resolvers with DI, subscriptions, cost limits and persisted operations."
---

A production GraphQL endpoint over a Strawberry schema.

```bash
pip install sillo-graphql
```

Installs as `sillo-graphql`, imports as `sillo.graphql`. Strawberry keeps the
schema; this package owns everything around it — the transports, the safety,
and the observability.

```python
import strawberry
from sillo import Depend, HttpContext, SilloApp
from sillo.graphql import Graph, Limits, field


@strawberry.type
class Query:
    @field
    async def me(ctx: HttpContext, db=Depend(get_db)) -> User:
        return await db.users.get(ctx.user.id)


app = SilloApp()
Graph(strawberry.Schema(query=Query), limits=Limits(depth=8)).mount(app)
```

## The one rule

**`ctx` and anything defaulted to `Depend` are injected and never appear in the
schema; every other parameter is a GraphQL argument.**

```python
@field
async def posts(ctx: HttpContext, db=Depend(get_db), limit: int = 10) -> list[Post]:
    ...
```

That field takes exactly one argument, `limit`. See
[Resolvers](/packages/graphql/resolvers/).

## Build it, then mount it

```python
graph = Graph(schema, path="/graphql", ide=False, introspection=False)
graph.mount(app)
```

Configuration and mounting are separate steps, the way `AdminSite(...)` and
`admin.mount(app)` are. `mount` takes a `SilloApp` or a `Router`, so the
endpoint composes under a prefix.

## Where to go

| | |
|---|---|
| [Resolvers](/packages/graphql/resolvers/) | `field`, `mutation`, `subscription`, and the injection rule |
| [Context & Response](/packages/graphql/context/) | `GraphContext`, setting a status or cookie from a resolver |
| [Loaders](/packages/graphql/loaders/) | Batching, and the end of N+1 |
| [Cost & Limits](/packages/graphql/limits/) | Depth, aliases, weighted cost, `@field(cost=)` |
| [Errors](/packages/graphql/errors/) | Free builders, masking, `@graph.on_error` |
| [Subscriptions](/packages/graphql/subscriptions/) | `graphql-transport-ws`, SSE, authenticating a socket |
| [HTTP Transport](/packages/graphql/transport/) | GET, batching, uploads, content negotiation |
| [Persisted Operations](/packages/graphql/persisted/) | APQ, and trusted documents |
| [Observability](/packages/graphql/observability/) | Metrics, slow-operation logs, OpenTelemetry |
| [Testing](/packages/graphql/testing/) | `GraphClient`, subscription streams |

## Why it is not in core

The framework shipped a `sillo.graphql` until 1.0. It was a single route that
served the GraphiQL IDE on `GET` and called `schema.execute` on `POST` — about
sixty lines of logic, and enough to demonstrate GraphQL rather than to run it.

Everything a GraphQL endpoint needs beyond that is substantial and specific:
subscriptions over a WebSocket protocol, cost analysis, batching, persisted
operations, upload handling. None of it belongs to applications that do not
serve GraphQL, and all of it moves at Strawberry's cadence rather than the
framework's. So it moved out, and grew.

## Defaults changed, on purpose

Every default here is chosen for an endpoint on the public internet.

| | before | now |
|---|---|---|
| Explorer | served on every `GET` | off |
| Introspection | always on | off |
| Resolver exceptions | returned verbatim | masked and logged |
| Depth and cost | unlimited | enforced |
| Missing document | `500` | `400` |
| OpenAPI | endpoint described, incorrectly | excluded |

If you are moving from the framework's module, the shortest path is
`GraphQL(app, schema)` → `Graph(schema).mount(app)` and
`info.context["ctx"]` → a `ctx: HttpContext` parameter. The context is still a
`Mapping`, so the old subscript keeps working and a schema can migrate one
resolver at a time.

## The two import paths

`sillo.graphql` and `sillo_graphql` are the same module object. The code lives
in the top-level `sillo_graphql` package; a `.pth` registers a meta-path finder
at interpreter startup, and PEP 561 partial stubs serve type checkers, which
never run import hooks. Nothing is written into the framework's `sillo/`
directory.

Because the framework shipped its own `sillo.graphql` before 1.0, the alias
**refuses to load** against an older framework rather than silently shadowing
it, and says which two things disagree.

## Requirements

Python 3.10 through 3.14, `sillo-framework` 1.0 or newer, and
`strawberry-graphql`.

## Source

[github.com/sillohq/graphql](https://github.com/sillohq/graphql) —
BSD-3-Clause.
