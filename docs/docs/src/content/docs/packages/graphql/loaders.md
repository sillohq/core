---
title: Loaders
description: Request-scoped batching — the end of N+1, wired as a decorator rather than a registry to thread through.
---

N+1 is GraphQL's defining failure. `{ posts { author { name } } }` asks for one
author per post, and a resolver written the obvious way issues one query per
post. Twenty posts, twenty-one queries.

A loader collects the keys its siblings asked for during the same tick of the
event loop and answers them with one call.

```python
@graph.loader
async def load_author(keys: list[int]) -> list[User]:
    rows = await User.objects.filter(id__in=keys).all()
    return align(rows, keys)


@field
async def author(ctx: HttpContext, root: Post) -> User:
    return await load_author(root.author_id)
```

Twenty posts, two queries.

## The contract

A batch function takes a list of keys and returns **one value per key, in the
same order**. Returning a different number raises `LoaderError` naming both
counts — that mistake otherwise surfaces as data attached to the wrong parent,
which is far worse than an exception.

```python
def align(rows, keys):
    """One row per key, in the key order — the shape a loader must return."""
    by_id = {row.id: row for row in rows}
    return [by_id.get(key) for key in keys]
```

A database returns rows in whatever order it likes and omits the ones that do
not exist, so realigning is almost always necessary. Write it once.

## There is no registry to thread through

The batch a call joins is found from a context variable the transport sets, so
loaders can be defined at module scope and called from anywhere in a resolver.
State is per operation: two concurrent requests never share a cache.

Calling one outside an operation raises `LoaderError` and says what to do about
it, rather than silently building a batch that never dispatches.

## Options

```python
@graph.loader(max_batch_size=500, cache=False, name="authors")
async def load_author(keys: list[int]) -> list[User]:
    ...
```

**`max_batch_size`** chunks a large batch into several calls. Databases refuse
a ten-thousand-item `IN` clause; this is where you say so. `None` — the default
— passes the whole batch.

**`cache`** deduplicates repeated keys within one operation. On by default,
which is what you want: `{ posts { author { name } } }` over twenty posts by
the same three authors should ask for three. Turn it off when a value can
change during one operation, which mostly means after a mutation.

**`name`** appears in error messages; it defaults to the function's name.

## Beyond one key at a time

```python
await load_author(1)                      # one
await load_author.load(1)                 # the same
await load_author.load_many([1, 2, 3])    # one batch, in order
```

## Priming and forgetting

```python
@field
async def post(ctx: HttpContext, id: int) -> Post:
    post = await Post.objects.get(id=id)
    # The author came back with the row; do not fetch it again.
    load_author.prime(post.author_id, post.author)
    return post
```

```python
@mutation
async def rename(ctx: HttpContext, id: int, name: str) -> User:
    user = await update(id, name=name)
    load_author.forget(id)          # anything later must re-read
    return user
```

Forgetting a key that was never cached is harmless.

## Failure is per key

If the batch function raises, every waiter gets that exception — the batch
failed, so they all did.

But an `Exception` **in the returned list** fails only that key:

```python
@graph.loader
async def load_author(keys):
    rows = await User.objects.filter(id__in=keys).all()
    by_id = {row.id: row for row in rows}
    return [by_id.get(k) or KeyError(f"no user {k}") for k in keys]
```

One missing row becomes one field error, and the other nineteen posts still
render their author. That is the whole point of a partial response.

## Loaders that take a compound key

Keys need not be scalars. A key that cannot be hashed skips the cache rather
than failing, so a list or a dict works:

```python
@graph.loader
async def load_permissions(keys: list[tuple[int, str]]) -> list[bool]:
    return await permissions_for(keys)


@field
async def can_edit(context: GraphContext, root: Post) -> bool:
    return await load_permissions((context.user.id, root.id))
```

Prefer a tuple over a dict — a tuple hashes, so it caches.

## Outside a request

Background jobs and tests can open a scope of their own:

```python
from sillo.graphql import LoaderRegistry


async def nightly_digest():
    async with LoaderRegistry().scope():
        for post in await Post.objects.all():
            await load_author(post.author_id)
```

## What to watch

If a page is slow and the loader is not helping, the usual cause is a resolver
that awaits something else before calling the loader. Batching happens across
one tick of the event loop; a resolver that awaits a database round-trip first
lands in a later tick than its siblings and batches alone.

Fetch first, then resolve — or prime the loader from the parent query, which
skips the round trip entirely.
