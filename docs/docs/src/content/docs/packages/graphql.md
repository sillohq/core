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

## Why it is not in core

The framework shipped a `sillo.graphql` until 1.0. It was a single route that
served the GraphiQL IDE on `GET` and called `schema.execute` on `POST` — about
sixty lines of logic, and enough to demonstrate GraphQL rather than to run it.

Everything a GraphQL endpoint needs beyond that is substantial and specific:
subscriptions over a WebSocket protocol, cost analysis, batching, persisted
operations, upload handling. None of it belongs to applications that do not
serve GraphQL, and all of it moves at Strawberry's cadence rather than the
framework's. So it moved out, and grew.

## Resolvers read like handlers

```python
@field
async def posts(ctx: HttpContext, db=Depend(get_db), limit: int = 10) -> list[Post]:
    return await db.posts.recent(limit)
```

One rule: **`ctx` and anything defaulted to `Depend` are injected and never
appear in the schema; every other parameter is a GraphQL argument.** That field
takes exactly one, `limit`.

Dependencies resolve through the framework's own solver and its pre-flattened
execution plan, cached for the operation — so twenty fields that each declare
`Depend(get_db)` share one session rather than opening twenty.

## What it adds

**Cost limits, enforced before execution.** Depth, aliases, breadth and
document size, plus a weighted cost that understands lists — a list field
multiplies everything under it, by the page size the caller asked for when
that is knowable. An operation over budget is refused before a resolver runs.

**Errors that say what happened, and no more.** Free builders in the shape of
the framework's response builders, with stable `extensions.code`:

```python
from sillo.graphql import not_found

raise not_found("No such post")     # extensions.code == "NOT_FOUND"
```

An exception that escapes a resolver is masked and logged rather than sent —
what it said may name a host, a table or a credential.

**Batching.** `@graph.loader` collects the keys sibling fields ask for in one
tick of the event loop and answers them with one call.

**Subscriptions.** `graphql-transport-ws` over the framework's own WebSocket
layer, with an initialisation timeout, keepalive, and cancellation of every
operation when the socket closes. `@graph.on_connect` authenticates from the
`connection_init` payload, which is where a browser can put a token. The same
subscriptions are available over `text/event-stream`.

**The rest of the HTTP surface.** Capped batching, `GET` for queries with
mutations refused, file uploads per the multipart request spec, and content
negotiation between `application/graphql-response+json` and the legacy
`application/json` that existing clients expect.

**Persisted operations.** APQ for bandwidth, and a trusted-document manifest
that makes the endpoint's workload finite and known.

## Defaults

Every default is chosen for a public endpoint, and three of them changed from
what the framework's module did:

| | before | now |
|---|---|---|
| Explorer | served on every `GET` | off |
| Introspection | always on | off |
| Resolver exceptions | returned verbatim | masked and logged |
| Depth and cost | unlimited | enforced |
| Missing document | `500` | `400` |

## Migrating

`GraphQL(app, schema)` becomes `Graph(schema).mount(app)`, and
`info.context["ctx"]` becomes a `ctx: HttpContext` parameter. The context is
still a `Mapping`, so the old subscript keeps working and a schema can move one
resolver at a time.

Full details, including the resolver bridge and the testing helpers, are in the
[package README](https://github.com/sillohq/graphql).
