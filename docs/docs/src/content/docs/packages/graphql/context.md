---
title: Context & Response
description: GraphContext — the typed context a resolver is handed, and how a resolver influences the HTTP response it is part of.
---

`sillo`'s pitch is one typed context object per connection, and this package
keeps that promise inside GraphQL: a resolver declares `ctx: HttpContext` and
gets the same object an HTTP handler would.

```python
@field
async def agent(ctx: HttpContext) -> str:
    return ctx.headers.get("user-agent", "unknown")
```

## GraphContext

What Strawberry is handed as `context_value`, and what a resolver gets by
annotating `GraphContext`.

```python
from sillo.graphql import GraphContext


@field
async def whoami(context: GraphContext) -> str:
    return str(context.user)
```

| | |
|---|---|
| `http` | The `HttpContext`, or `None` during a subscription |
| `socket` | The `WebSocketContext`, or `None` over HTTP |
| `connection` | Whichever of the two this operation arrived on |
| `user` | The authenticated user, or `None` |
| `response` | What this operation wants done to the response |
| `loaders` | The request-scoped [loader registry](/packages/graphql/loaders/) |
| `extra` | Whatever a `@graph.context` hook returned |
| `operation_name` | The operation being executed |
| `cost` | Its measured [cost](/packages/graphql/limits/) |

Most resolvers want `ctx` — the connection — rather than the whole thing. Reach
for `GraphContext` when you need `response`, `extra` or `cost`.

`user` is read through rather than snapshotted, because authentication
middleware may resolve it lazily. Without any middleware it answers `None`
rather than raising, so a field gated on `auth=` says "not authenticated"
instead of 500.

### The legacy shape still works

`GraphContext` is a `Mapping`, so the shape the framework's old module had
keeps working:

```python
@strawberry.field
def old_style(self, info) -> str:
    ctx = info.context["ctx"]          # the connection context
    return ctx.method
```

That is deliberate: a schema can migrate one resolver at a time rather than all
at once.

## Influencing the response

Strawberry executes the whole document before this package builds a response,
so a resolver cannot return one. It can record intent, and the transport
applies it afterwards.

```python
@field
async def report(context: GraphContext) -> Report:
    context.response.set_status(202)
    context.response.set_header("x-generated-by", "reports-v2")
    context.response.set_cookie("last_report", "42", httponly=True)
    return await build_report()
```

| | |
|---|---|
| `set_status(code)` | Ask for a status |
| `set_header(name, value)` | Set a response header |
| `set_cookie(...)` | The arguments of `BaseResponse.set_cookie` |
| `delete_cookie(...)` | The arguments of `BaseResponse.delete_cookie` |

**Later writes win, and the status only ever goes up.** Two resolvers
disagreeing about whether the answer is 200 or 404 should not depend on which
the executor reached first.

Over a subscription there is no response to influence, and the recorded calls
are simply never applied.

### Setting a session cookie from a mutation

The usual reason to want this:

```python
@mutation
async def login(context: GraphContext, email: str, password: str) -> User:
    user = await authenticate(email, password)
    if user is None:
        raise unauthenticated("Those credentials do not match")

    context.response.set_cookie(
        "session", await issue_session(user),
        httponly=True, secure=True, samesite="lax",
    )
    return user
```

## Adding your own keys

`@graph.context` runs per operation and merges what it returns into `extra`.

```python
@graph.context
async def tenant(ctx: HttpContext) -> dict:
    return {"tenant": await tenant_for(ctx.headers.get("x-tenant"))}
```

Read it back either way:

```python
@field
async def settings(context: GraphContext) -> Settings:
    return await load_settings(context.extra["tenant"])
```

```python
@field
async def settings(info: strawberry.Info) -> Settings:
    return await load_settings(info.context["tenant"])
```

Hooks may be sync or async, are given the connection's context, and stack —
register as many as you like. A hook that returns anything other than a mapping
is ignored, so an early `return` costs nothing.

Over a WebSocket the hook is given the socket, and `extra["connection_params"]`
holds the `connection_init` payload. See
[Subscriptions](/packages/graphql/subscriptions/).

## Root values

```python
Graph(schema, root_value=Root())
```

Passed to every execution, query and subscription alike. Rarely needed with
Strawberry, where fields carry their own resolvers, but available for schemas
built the other way round.

## The dependency cache

`GraphContext` carries the cache the framework's dependency solver uses, so one
operation shares one value per dependency. It is created with the context and
dropped with it, which is what makes request-scoped dependencies safe — nothing
survives into the next operation.

Two resolvers in one query that both declare `Depend(get_db)` get one session.
See [Resolvers](/packages/graphql/resolvers/).
