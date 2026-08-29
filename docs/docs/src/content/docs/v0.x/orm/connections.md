---
title: Connections
description: "Working with more than one database: registering connections, routing a query with using_db, read replicas, connection pooling and the per-request connection context."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Sillo Record Connections
  - tag: meta
    attrs:
      property: og:description
      content: Multiple connections, using_db, replicas, pooling and the request context.
---

Most applications have one database and never touch this page. It is here for
the ones with a replica, a reporting database, or a legacy system alongside.

## The default connection

[`setup_record`](/v0.x/orm/setup/) registers one connection named `default`.
Everything uses it unless told otherwise.

```python
from tortoise import connections

conn = connections.get("default")
```

## The per-request context

Tortoise keeps the active connection in a context variable. The
`ensure_context` middleware [`setup_record` registers](/v0.x/orm/setup/#ensure_context)
sets it for the task each request runs in.

The consequence worth knowing: a model call from a task that escaped the
request may not find it.

```python
# fine — the middleware set the context for this task
@app.get("/posts")
async def list_posts(request, response):
    return response.json(await Post.all().values("id", "title"))


# risky — a new task, outside the request's context
asyncio.create_task(reindex_everything())
```

Use [background tasks](/v0.x/guides/work/background/) or a
[queued job](/v0.x/guides/work/queue/), both of which carry it. A job also survives
the process the request was served by, which is usually the real requirement.

## Registering a second connection

```python
from sillo.record import DatabaseConfig, DatabaseManager

replica = DatabaseManager(DatabaseConfig.from_env(prefix="REPLICA_"))
replica.register_models("database.models")
await replica.init()
```

```bash
DATABASE_URL=postgres://user:pass@primary/app
REPLICA_DATABASE_URL=postgres://user:pass@replica/app
```

The `prefix` on [`from_env`](/v0.x/orm/configuration/#fields) is what keeps the two
sets of environment variables apart.

## Routing a query

```python
await Post.all().using_db(replica_connection)
```

Per query, explicitly. There is no automatic read/write router, which is a
deliberate omission rather than a gap: an implicit router sends a read to a
replica moments after the write it depends on, and returns stale data with no
indication that it did.

Choosing per query means you decide where staleness is acceptable:

```python
# a report — seconds of lag are fine
stats = await Post.all().using_db(replica).annotate(n=Count("id")).group_by("status")

# right after a write — must be the primary
await post.save()
fresh = await Post.get(id=post.id)
```

### Replication lag

A replica is behind the primary: usually milliseconds, occasionally much more.
The failure mode is a user saving a form, being redirected, and seeing their
old data.

Practical rule: **read from the replica for anything the user did not just
change.** Dashboards, exports, search, listings someone else's writes feed.
Read from the primary immediately after a write in the same request.

## Pooling

`DB_POOL_SIZE` and `DB_MAX_OVERFLOW` bound the connections **per process**.

```bash
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
```

Size against the database's connection limit, not against traffic. Four
application processes at the defaults is up to 60 connections, and a worker and
a scheduler are more processes with their own pools. A small managed PostgreSQL
defaults to 100 total.

```
processes × (pool_size + max_overflow) ≤ the server's limit, with room spare
```

When that does not fit, a connection pooler (PgBouncer in transaction mode) is
the answer rather than a bigger number.

`DB_POOL_RECYCLE` (default 3600s) reopens connections older than that.
Proxies and managed databases drop idle connections without telling the client,
and the failure surfaces as an occasional error on a perfectly good query.

## Transactions are per connection

```python
from sillo.record.transactions import transaction

async with transaction("replica"):
    ...
```

A transaction covers one connection. Two blocks on two connections are two
transactions, and one can commit while the other rolls back.

Take the connection **inside** the block:

```python
# wrong — this may not be the connection the transaction opened
conn = connections.get("default")
async with transaction():
    await conn.execute_query(...)

# right
async with transaction():
    conn = connections.get("default")
    await conn.execute_query(...)
```

See [Transactions](/v0.x/orm/transactions/#multiple-connections).

## Health

```python
await database.health()
```

A trivial query, returning a boolean rather than raising, which is what a
health endpoint wants:

```python
@app.get("/health")
async def health(request, response):
    ok = await app.state["record"].health()
    return response.json({"database": ok}, status=200 if ok else 503)
```

Check every connection you depend on, not only the default. A replica that is
down while the primary is fine is still a broken deployment, and a health check
that only asks the primary will not say so.

## Closing

```python
await database.shutdown()
```

`setup_record` registers this on shutdown. Call it yourself in a script or a
[standalone console](/v0.x/cli/standalone-consoles/), where nothing has.

```python
manager = DatabaseManager(DatabaseConfig.from_env())
manager.register_models("database.models")
await manager.init()
try:
    ...
finally:
    await manager.shutdown()
```

Skipping it leaves connections open until the process exits, invisible in a
script that runs for a second, and a leak in one that loops.

## Different databases, different models

Models belong to an app label, and a label maps to a connection. A model in a
second database is a second label with its own
[migration commands](/v0.x/cli/standalone-consoles/#record_commands):

```python
console.add_many(record_commands(database, app="models"))
console.add_many(record_commands(reporting, app="reporting"))
```

Cross-database joins do not exist. A relation between models in different
databases has to be resolved in Python, and a
[`db_constraint=False`](/v0.x/orm/relationships/#db_constraintfalse) foreign key is
how you declare it without asking the schema for something it cannot provide.
