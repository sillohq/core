---
title: Resolvers
description: field, mutation and subscription — resolvers that read like sillo handlers, with ctx and Depend injected and kept out of the schema.
---

A route handler in `sillo` takes the context first and declares whatever else
it needs. A resolver here is the same thing.

```python
import strawberry
from sillo import Depend, HttpContext
from sillo.graphql import field, mutation, subscription


@strawberry.type
class Query:
    @field
    async def me(ctx: HttpContext, db=Depend(get_db)) -> User:
        return await db.users.get(ctx.user.id)
```

## The rule

**`ctx` and anything defaulted to `Depend` are injected and never appear in the
schema; every other parameter is a GraphQL argument.**

```python
@field
async def posts(ctx: HttpContext, db=Depend(get_db), limit: int = 10) -> list[Post]:
    return await db.posts.recent(limit)
```

```graphql
type Query {
  posts(limit: Int! = 10): [Post!]!
}
```

One argument. `ctx` and `db` are gone from the schema and present in the
function.

## What counts as injected

| Parameter | Injected as |
|---|---|
| Annotated `HttpContext`, `WebSocketContext`, `BaseContext` | The connection's context |
| Annotated `GraphContext` | The whole [context object](/packages/graphql/context/) |
| Named `ctx` or `context`, unannotated | The connection's context |
| Defaulted to `Depend(...)` | The resolved dependency |
| Named `root`, `self` or `parent` | The parent object |
| Annotated `strawberry.Info` | Strawberry's info |

Everything else is a GraphQL argument and **must be annotated** — GraphQL needs
a type for every argument. An unannotated one raises `ResolverError` at import,
naming the parameter, rather than producing a schema that is quietly wrong.

`*args` and `**kwargs` are refused for the same reason: a GraphQL field's
arguments are a fixed list.

## How it works

Strawberry derives a field's arguments from its resolver's signature, so the
injected parameters have to be gone by the time it looks. The decorator builds
a wrapper carrying a synthesized `__signature__` holding only the exposed
arguments, plus `root` and `info` — which Strawberry recognises and keeps out
of the schema — and fills the rest in at call time.

That is the same trick the framework's own router plays when it inspects a
handler before dispatch, and the injection reuses the framework's dependency
solver rather than reimplementing one.

It survives Python 3.14's deferred annotations (PEP 649): the decorator reduces
an annotation to a bare name whether it arrives as a string or as a live class,
so `ctx: HttpContext` is recognised either way.

## Dependencies

`Depend` works exactly as it does on a route, including nested dependencies and
generator dependencies with teardown.

```python
async def get_db():
    session = await pool.acquire()
    try:
        yield session
    finally:
        await session.close()


@field
async def posts(db=Depend(get_db)) -> list[Post]:
    return await db.posts.all()
```

Teardown runs through `aclose()`, which raises `GeneratorExit` at the `yield` —
so cleanup must be in a `finally`, exactly as on a route. Bare statements after
the `yield` never run, here or there.

### One operation, one dependency

**Two resolvers in one operation that both declare `Depend(get_db)` are handed
the same session.** The cache lives on the request's context and is dropped
with it.

This differs deliberately from a route. The framework only assigns a cache key
to dependencies that have dependencies of their own, so `Depend(get_db)`
resolves once per parameter — harmless in a handler that is called once,
pathological across twenty resolvers, where it would open twenty sessions to
answer one query.

## Mutations

The same rules.

```python
@strawberry.type
class Mutation:
    @mutation
    async def publish(ctx: HttpContext, id: int, db=Depend(get_db)) -> Post:
        post = await db.posts.get(id)
        post.published = True
        await db.commit()
        return post
```

## Subscriptions

An async generator. It may declare `ctx: WebSocketContext` to reach the socket.

```python
@strawberry.type
class Subscription:
    @subscription
    async def prices(ctx: WebSocketContext, symbol: str) -> AsyncGenerator[Price, None]:
        async for tick in feed(symbol):
            yield tick
```

A subscription that is not an async generator raises `ResolverError` at import.
See [Subscriptions](/packages/graphql/subscriptions/).

## Field options

```python
@field(
    cost=25,                    # against the cost budget
    auth=True,                  # or a predicate over the user
    name="search",              # the name in the schema
    description="Full-text search.",
    deprecation_reason="Use `find` instead.",
)
async def full_text_search(ctx: HttpContext, term: str) -> list[Hit]:
    ...
```

`name`, `description`, `deprecation_reason` and `permission_classes` pass
through to `strawberry.field`.

### `cost`

What one selection of this field costs against the budget. Use it for the
fields that are genuinely expensive; the default of 1 is right for the rest.
See [Cost & Limits](/packages/graphql/limits/).

### `auth`

`auth=True` refuses the field unless someone is signed in. A callable receives
the user and returns whether to allow it — sync or async.

```python
@field(auth=True)
async def drafts(ctx: HttpContext) -> list[Post]: ...

@field(auth=lambda user: user.is_staff)
async def audit_log(ctx: HttpContext) -> list[Entry]: ...
```

The check runs inside the resolver rather than as a schema directive, so a
denial is an error on that one field and the rest of the operation is still
answered — which is what a partial GraphQL response is for. Refusals raise
`GraphQLDenied` with `UNAUTHENTICATED` or `FORBIDDEN`.

A caller is "signed in" when `ctx.user` resolves. Without authentication
middleware mounted, that reads as nobody rather than raising, so a gated field
answers "not authenticated" instead of 500.

## Sync resolvers

Both work. A sync resolver is called directly; an async one is awaited.

```python
@field
def slug(root: Post) -> str:
    return slugify(root.title)
```
