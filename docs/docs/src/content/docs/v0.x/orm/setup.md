---
title: Setup
description: "Wiring a database into a Sillo application with setup_record: model registration, the connection lifecycle, per-request context, and the health check."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Sillo ORM Setup
  - tag: meta
    attrs:
      property: og:description
      content: setup_record, DatabaseManager, and the connection lifecycle.
---

One call wires a database into an application.

```python
from sillo import SilloApp
from sillo.record import DatabaseConfig, setup_record

app = SilloApp()

setup_record(
    app,
    DatabaseConfig.from_env(),
    model_modules=["database.models", "sillo.admin.models"],
)
```

That does four things: builds a `DatabaseManager`, registers the model
modules, connects on startup and disconnects on shutdown, and puts the manager
on `app.state["record"]`.

## Why `app.state` matters

The manager on `app.state` is what the [`sillo` command](/v0.x/cli/) looks for. Find
one and the `db:*` migration commands and the `user:*` account commands appear;
find none and they do not.

So the wiring you were writing anyway is what gives you the tooling. There is
no second place to configure it.

## Model modules

```python
model_modules=["database.models", "sillo.admin.models"]
```

Dotted paths to modules containing models. Tortoise discovers models by
importing these, a model in a module not listed here has no table, and the
error you get is a confusing one about a missing relation rather than a missing
model.

`sillo.admin.models` is required if you mount the [admin panel](/v0.x/orm/admin/):
it holds the activity log every admin site writes to.

## Installing the driver

Record depends on Tortoise; Tortoise needs a driver per backend, and none is
installed by default:

```bash
uv add aiosqlite     # SQLite
uv add asyncpg       # PostgreSQL
uv add asyncmy       # MySQL / MariaDB
```

Plus the extra itself:

```bash
uv add "sillo-framework[record]"
```

## The lifecycle

| Phase | What happens |
| --- | --- |
| Startup | `init()` connects, and generates schemas if configured to |
| Per request | `ensure_context` middleware makes the connection available |
| Shutdown | `shutdown()` closes the connections |

`setup_record` registers all three. You do not call them.

### `ensure_context`

Registered as middleware. Tortoise keeps its connection in a context variable,
and an ASGI application handling concurrent requests needs that variable set
for the task the handler runs in. This is what does it.

The practical consequence: a model call from inside a request works. A model
call from a background task that escaped the request (a bare
`asyncio.create_task`) may not, because it is a different task with a different
context. Use [background tasks](/v0.x/guides/work/background/), which carry it.

## Using the manager directly

```python
database = app.state["record"]

await database.health()          # True when the connection answers
config = database.orm_config()   # the dict Tortoise/Aerich want
```

`health()` runs a trivial query and returns a boolean rather than raising,
which is what a `/health` endpoint wants:

```python
@app.get("/health")
async def health(request, response):
    ok = await app.state["record"].health()
    return response.json({"database": ok}, status=200 if ok else 503)
```

## Building one by hand

`setup_record` is a convenience. The pieces are public:

```python
from sillo.record import DatabaseConfig, DatabaseManager

database = DatabaseManager(DatabaseConfig.sqlite("storage/app.db"))
database.register_models("database.models")
database.set_migrations("database.migrations")

await database.init()
try:
    ...
finally:
    await database.shutdown()
```

Which is what a script or a standalone [console](/v0.x/cli/standalone-consoles/)
needs. Nothing has started an application there, so nothing has connected.

## Migrations

`set_migrations` names the package migrations are written to and read from.
`setup_record` defaults it to the conventional location; override it when your
project puts them elsewhere.

```python
database.set_migrations("database.migrations")
```

See [Migrations](/v0.x/orm/migrations/).

## Schema generation

`DB_GENERATE_SCHEMAS` (default `true`) creates tables from the models at
startup when they do not exist.

That is right for tests and for a first run, and wrong for anything with data
in it. It creates missing tables and does nothing about the ones whose shape
has changed, which is exactly the divergence migrations exist to prevent.

Turn it off wherever you run migrations:

```bash
DB_GENERATE_SCHEMAS=false
```

## See also

- [Configuration](/v0.x/orm/configuration/): every setting and its environment
  variable.
- [Database commands](/v0.x/cli/database/): the CLI this setup unlocks.
