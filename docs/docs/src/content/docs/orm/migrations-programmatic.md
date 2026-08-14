---
title: Migrations Programmatically
description: "Running migrations without the CLI — the command functions, MigrationHelper, what a Database argument accepts, and running them from tests or a deployment script."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Running Sillo Migrations Programmatically
  - tag: meta
    attrs:
      property: og:description
      content: The command functions, MigrationHelper, and running migrations from code.
---

The `db:*` commands are a thin layer over plain functions. Call them directly
from a script, a test, or a console of your own.

```python
from sillo.record.commands import init, make, migrate, plan, rollback, sql
```

## The functions

```python
await init(database, app="models")
await make(database, "add_posts", app="models")
await migrate(database, target=None, fake=False, app="models")
await rollback(database, "0003_add_posts", fake=False, app="models")
await plan(database, target=None, app="models")
await sql(database, "0003_add_posts", backward=False, app="models")
```

Each takes the database first and the app label as a keyword. They are the same
operations the [CLI](/cli/database/) exposes, without the argument parsing or
the output.

### What `database` accepts

Three forms:

- a **`DatabaseManager`** — the usual one;
- a **config mapping** — the dict Tortoise wants;
- a **dotted path** to either.

```python
await migrate(app.state["record"])
await migrate("app.database:manager")
```

Taking all three means calling code never has to convert. The
[CLI](/cli/database/) additionally accepts a *callable* returning one, resolved
per command.

### Return values

`plan()` returns display lines — and includes a connection header alongside the
migrations, so counting the raw list reports one migration too many. Filter it:

```python
lines = await plan(database)
pending = [line for line in lines if line.strip() and not line.lstrip().startswith("#")]
print(f"{len(pending)} pending")
```

That is exactly what the CLI does before printing a count.

`sql()` returns a list of statements. The rest return `None`.

### `make` writes nothing when there is nothing

`make()` reports "no changes" only on the engine's own stdout. To know whether
a file was written, compare the plan before and after:

```python
before = len(await plan(database))
await make(database, "add_posts")
after = len(await plan(database))

if after == before:
    print("No model changes to record.")
```

The CLI does this so it can avoid printing *"Migration written"* for a file
that does not exist.

## `MigrationHelper`

The same operations, with the database bound once:

```python
from sillo.record.helpers import MigrationHelper

helper = MigrationHelper(database, app="models")

await helper.init()
await helper.make("add_posts")
await helper.upgrade()
await helper.upgrade(target="0003_add_posts")
await helper.downgrade("0002_add_users")
await helper.plan()
await helper.sql("0003_add_posts", backward=True)
```

Note the naming: `upgrade`/`downgrade` here, `migrate`/`rollback` in the
functions and the CLI. They are the same operations.

`app=None` manages every app label rather than one.

## Running migrations in tests

```python
import pytest
from sillo.record import DatabaseConfig, DatabaseManager
from sillo.record.commands import migrate


@pytest.fixture
async def database(tmp_path):
    manager = DatabaseManager(DatabaseConfig.sqlite(str(tmp_path / "test.db")))
    manager.register_models("database.models")
    manager.set_migrations("database.migrations")
    await manager.init()

    await migrate(manager)

    yield manager
    await manager.shutdown()
```

This tests the migrations as well as the code — the schema under test is the
one your deployments will produce, not one generated from the models.

The faster alternative is `DB_GENERATE_SCHEMAS=true` against `:memory:`, which
builds the schema from the models directly. It is quicker and it does not
exercise your migrations, so it cannot catch a migration that fails on a fresh
database. Many projects do both: generated schemas for the unit suite, real
migrations in CI.

## In a deployment script

```python
import asyncio
from sillo.record import DatabaseConfig, DatabaseManager
from sillo.record.commands import migrate, plan


async def main() -> int:
    manager = DatabaseManager(DatabaseConfig.from_env())
    manager.register_models("database.models")
    manager.set_migrations("database.migrations")
    await manager.init()
    try:
        pending = [
            line for line in await plan(manager)
            if line.strip() and not line.lstrip().startswith("#")
        ]
        if not pending:
            print("Nothing pending.")
            return 0

        for line in pending:
            print(f"  {line}")
        await migrate(manager)
        print(f"Applied {len(pending)}.")
        return 0
    finally:
        await manager.shutdown()


raise SystemExit(asyncio.run(main()))
```

Worth writing only when you need something around the migration — a lock, a
snapshot, a notification. Otherwise `sillo db:migrate` is the same thing and
already handles the output and the exit code.

## Why a bridge module exists

Two operations — creating the migration package, and writing a migration —
exist only behind the migration engine's own command line, which reads its
configuration by **importing a dotted path** rather than by taking a value.

Left exposed, that would become a rule every project has to follow: export a
module-level config mapping, under a particular name, at an import path you
then repeat in your tooling.

So `sillo.record._bridge` supplies the module. It publishes the configuration,
yields the path to it, and restores the previous value on the way out — so a
migration command running inside another one leaves the outer configuration in
place.

It is private, and nothing outside `sillo.record.helpers` should touch it. It
is documented here because it explains why `init` and `make` take a
configuration the same way the other four do, when the engine underneath does
not.

## See also

- [How migrations work](/orm/migrations/)
- [Building a console](/cli/standalone-consoles/#record_commands) — binding
  these as commands
