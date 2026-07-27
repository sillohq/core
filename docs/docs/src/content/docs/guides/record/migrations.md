---
title: Migrations & Seeding
description: Schema migrations with aerich, why the bundled MigrationHelper and RecordCLI wrappers do not work as documented, and the state of the Seeder and FixtureLoader helpers.
head:
  - tag: meta
    attrs:
      property: og:title
      content: Migrations & Seeding
  - tag: meta
    attrs:
      property: og:description
      content: Schema migrations with aerich, why the bundled MigrationHelper and RecordCLI wrappers do not work as documented, and the state of the Seeder and FixtureLoader helpers.
---

#  Migrations & Seeding

Changing a model changes the shape your code expects. Changing a table
changes the shape the database has. A migration is the recorded, ordered,
reviewable step that moves the second to match the first.

`sillo.record` does not implement migrations. It depends on
[aerich](https://github.com/tortoise/aerich), Tortoise ORM's official
migration tool, and ships two thin wrappers around it — `MigrationHelper`
and `RecordCLI`. This page covers aerich directly, because the wrappers
have defects that make them unusable as documented, and says exactly what
those defects are.

##  Why you need migrations at all

`DatabaseManager.init()` calls `Tortoise.generate_schemas(safe=True)` on
every startup. `safe=True` means "create tables that do not exist". It
issues no `ALTER TABLE`, ever.

So adding a field to a model and restarting gives you a running
application whose code expects a column the table does not have. The
failure appears at query time, as an `OperationalError` naming a column
you can plainly see in your model file. That is the moment most people
discover they needed migrations two weeks ago.

Use `generate_schemas` for tests and throwaway SQLite files. Use
migrations for anything holding data you would be sad to lose.

##  aerich, used directly

aerich needs a Tortoise config it can import. Put it in its own module so
both your application and the CLI can read it.

```python title="myapp/db.py"
import os

TORTOISE_ORM = {
    "connections": {"default": os.environ["DATABASE_URL"]},
    "apps": {
        "models": {
            "models": ["myapp.models", "aerich.models"],
            "default_connection": "default",
        },
    },
}
```

Two details decide whether this works.

`"aerich.models"` must appear in the models list. That is where aerich's
own version-tracking table is defined; leave it out and aerich cannot
record what it has applied.

`"myapp.models"` must list every module containing models. Tortoise
discovers by module scan, so a model in a file nobody imports is invisible
to the migration generator, and its table silently never gets created.

Then the workflow:

```bash title="the four commands you will actually use"
# once per project — creates ./migrations and the aerich table
aerich init -t myapp.db.TORTOISE_ORM
aerich init-db

# every time a model changes
aerich migrate --name add_article_slug
aerich upgrade

# when you need to look or go back
aerich history
aerich downgrade -v 3
```

`aerich migrate` diffs your models against the recorded migration state
and writes a Python file to `migrations/models/` with `upgrade()` and
`downgrade()` functions. `aerich upgrade` runs the pending ones in order
and records each.

###  Always read the generated migration

The generated file is ordinary Python containing raw SQL strings. Open it
before applying it. The diff engine is good at additive changes and
unreliable at others:

A renamed column is usually detected as a drop plus an add, which is a
data-destroying operation dressed as a rename. Edit it into an `ALTER
TABLE ... RENAME COLUMN` by hand.

A changed column type is emitted as a type change with no `USING` clause,
which fails on PostgreSQL when the conversion is not implicit.

A new non-null column without a default fails on any table with existing
rows. Add it nullable, backfill, then add the constraint — three
migrations, not one.

:::caution[SQLite cannot do most `ALTER TABLE` operations]
SQLite supports adding a column and renaming a table. It cannot drop a
column, change a type, or add a constraint. aerich works around this by
recreating the table and copying data, which is slow, locks the table,
and drops anything the recreation script did not know to preserve.

If you develop on SQLite and deploy on PostgreSQL, your migrations are
being tested against the wrong engine. Run them against a real PostgreSQL
instance in CI before they reach production.
:::

###  Migrations in a deployment

Run `aerich upgrade` as a separate step before the new application
version starts, not from application startup code. Starting three
replicas that each try to migrate produces three concurrent schema
changes and, on a good day, two failures.

```bash title="a deployment step"
aerich upgrade && exec uvicorn myapp.app:app --host 0.0.0.0 --port 8000
```

That is fine for a single-instance deployment. For rolling deployments,
make the step a job that runs once and gates the rollout, and keep each
migration compatible with both the old and new application version — add
columns before the code that writes them, drop them a release after the
code that read them is gone.

##  The bundled wrappers

:::danger[`MigrationHelper` does not do what its signature says]
The constructor's first parameter is named `app_module` and documented as
"Dotted path to the Tortoise config or app". It is used as the database
connection URL:

```python
tortoise_config={
    "connections": {"default": self._app},
    "apps": {"models": {"models": ["aerich.models"]}},
}
```

Passing a module path fails immediately:

```python
await MigrationHelper("myapp.models").init()
# ConfigurationError: Unknown DB scheme:
```

Passing a database URL gets past that — `MigrationHelper("sqlite:///tmp/m.db").init()`
succeeds and creates the migrations directory — but the second problem
remains: the `apps.models.models` list contains **only** `"aerich.models"`.
Your models are never registered, so the diff engine sees no tables of
yours and generates migrations that do not contain them.

There is no argument you can pass to fix this; the models list is
hard-coded. Use the `aerich` CLI or `aerich.Command` directly.
:::

:::caution[`sillo record ...` is not a command]
The commands `sillo record init`, `sillo record migrate`, and the rest do
not exist. sillo's CLI ships `new`, `ping`, `run`, `shell`, and `urls`.

`RecordCLI` is a class that *registers* those subcommands onto a Click
group you own:

```python
import click
from sillo.record import RecordCLI

@click.group()
def cli():
    pass

RecordCLI("sqlite://app.db", location="migrations").register(cli)
```

That gives *your* CLI a `record` group. It still delegates to
`MigrationHelper`, so it inherits the defect above. There is also a type
mismatch in `downgrade`: `RecordCLI` passes Click's string argument
through to `aerich.Command.downgrade`, whose signature is
`downgrade(version: int, delete: bool)`.
:::

If you want a project-local wrapper, call `aerich.Command` yourself with
a config that includes your models:

```python title="myapp/migrations_cli.py"
import asyncio

import click
from aerich import Command

from myapp.db import TORTOISE_ORM


def _command() -> Command:
    return Command(tortoise_config=TORTOISE_ORM, app="models", location="migrations")


@click.group()
def record():
    """Database migration commands."""


@record.command()
@click.option("--name", "-n", default="update")
def migrate(name):
    async def run():
        cmd = _command()
        await cmd.init()
        click.echo(await cmd.migrate(name=name))
    asyncio.run(run())


@record.command()
def upgrade():
    async def run():
        cmd = _command()
        await cmd.init()
        for migration in await cmd.upgrade():
            click.echo(f"applied {migration}")
    asyncio.run(run())
```

`Command.init()` loads the config and must be awaited before `migrate`,
`upgrade`, `downgrade`, or `history`.

##  Seeders

`Seeder` collects rows and inserts them. It works.

```python title="seeding"
from sillo.record import Seeder

seeder = Seeder(db_manager)
seeder.seed(User, [
    {"email": "admin@example.com", "name": "Admin"},
    {"email": "user@example.com", "name": "User"},
])
seeder.seed(Post, [
    {"title": "Hello World", "body": "First post", "user_id": 1},
])

count = await seeder.run()
```

`seed()` returns the seeder, so calls chain. `run()` inserts in the order
the calls were made — which is how you satisfy foreign keys, by seeding
parents before children — and returns the number of rows created.

Rows are created with `Model.create()`, so casts, mutators, and
`ValidatesBeforeSaveMixin` all apply. Note that lifecycle events do
**not** fire, for the reason described in
[Scopes & Events](/guides/record/scopes-events/).

Two limitations worth knowing:

`run(batch_size=100)` accepts `batch_size` and ignores it. The
implementation is one `create()` per record. Seeding ten thousand rows is
ten thousand round trips; use `Model.bulk_create` for that.

`Seeder` is not idempotent. Running it twice inserts everything twice, or
fails on a unique constraint. Make production seeds safe to re-run:

```python title="an idempotent seed"
async def seed_defaults():
    await Role.get_or_create({"label": "Administrator"}, slug="admin")
    await Role.get_or_create({"label": "Member"}, slug="member")
```

The `db_manager` argument is stored and never used, so passing `None`
works. Pass the manager anyway — the parameter may become meaningful.

##  Fixtures

:::danger[`FixtureLoader` reads files and inserts nothing]
`_load_file` opens the file, parses the JSON or JSONL, assigns
`model_name = path.stem`, never uses it, and returns `len(records)`.
There is no database call anywhere in the class.

The return value makes it look like it worked:

```python
loader = FixtureLoader("fixtures/")
await loader.load_all()          # returns 2
await Article.filter(title__startswith="fixture").count()   # 0
```

A test suite that seeds through `FixtureLoader` and then asserts on the
count it returned will pass while the database stays empty.

Load fixtures yourself; it is a dozen lines and it works:

```python title="a fixture loader that inserts"
import json
from pathlib import Path


async def load_fixtures(directory: str, models: dict[str, type]) -> int:
    total = 0
    for path in sorted(Path(directory).glob("*")):
        model = models[path.stem]
        text = path.read_text()
        if path.suffix == ".jsonl":
            records = [json.loads(line) for line in text.splitlines() if line.strip()]
        else:
            records = json.loads(text)
        if not isinstance(records, list):
            records = [records]
        await model.bulk_create(records)
        total += len(records)
    return total


await load_fixtures("fixtures/", {"users": User, "articles": Article})
```

The explicit `models` mapping is deliberate. Resolving a model class from
a filename means a file dropped into the directory decides which table
gets written to.
:::

The directory layout the loader expects is still a reasonable convention:

```text
fixtures/
  01_users.json     [{"email": "a@b.com", "name": "Alice"}, ...]
  02_articles.jsonl {"title": "First"}
                    {"title": "Second"}
```

Files load in sorted order, so a numeric prefix is how you make parents
load before children.

##  Choosing between the three

| Tool | Use for | Runs when |
|---|---|---|
| Migrations | Schema changes | Deployment, once |
| `Seeder` / fixtures | Reference data — roles, plans, countries | Deployment or first boot |
| [`Factory`](/guides/record/transactions-factories/) | Randomised test data | Test setup |

The distinction that matters: reference data is part of the application's
definition and belongs in version control next to the migrations. Test
data is disposable and belongs in the test suite. Mixing them gives you
production databases full of "Test User".

##  What not to do

**Do not rely on `generate_schemas` to evolve a schema.** It creates and
never alters.

**Do not use `MigrationHelper`.** Its first argument is a database URL,
and it registers only aerich's own models.

**Do not expect `sillo record` to exist.** It is not a built-in command.

**Do not apply a generated migration unread.** Renames appear as
drop-plus-add.

**Do not run migrations from application startup.** Multiple replicas
will race.

**Do not test migrations only on SQLite** if you deploy on PostgreSQL.

**Do not trust `FixtureLoader`'s return value.** It counts parsed
records, not inserted rows.

**Do not make production seeds non-idempotent.** Use `get_or_create`.

##  Performance notes

`Seeder.run()` is one `INSERT` per record with a full round trip each.
At ten milliseconds of latency, ten thousand rows takes a hundred
seconds. `bulk_create` with `batch_size=500` takes about twenty
statements.

`aerich upgrade` runs inside a transaction by default
(`run_in_transaction=True`). On PostgreSQL that means DDL is atomic and a
failed migration leaves nothing behind. On MySQL, DDL causes an implicit
commit, so a migration that fails halfway leaves the schema partially
changed — write MySQL migrations so each step is independently safe.

Adding an index on a large PostgreSQL table locks it for writes for the
duration. Use `CREATE INDEX CONCURRENTLY` in a hand-edited migration, and
note that it cannot run inside a transaction — that migration needs
`run_in_transaction=False`.

##  API reference

| Name | Signature | Status |
|---|---|---|
| `MigrationHelper` | `(app_module: str, *, location="migrations")` | First argument is a DB URL; registers only `aerich.models` |
| `MigrationHelper.init` / `.migrate` / `.upgrade` / `.downgrade` / `.history` | async | Inherit the above |
| `RecordCLI` | `(app_module: str, *, location="migrations")` | `.register(click_group)`; wraps `MigrationHelper` |
| `Seeder` | `(db_manager)` | `.seed(model, records)`, `await .run()` — works |
| `Seeder.run` | `(*, batch_size=100) -> int` | `batch_size` is ignored |
| `FixtureLoader` | `(directory: str)` | `.load_all()`, `.load(name)` — **inserts nothing** |
| `aerich.Command` | `(tortoise_config, app="models", location="./migrations")` | The one to use |

##  Related

- [Record Overview](/guides/record/) — configuration, and why `generate_schemas` is not enough
- [Models & Mixins](/guides/record/models/) — `bulk_create` for fast seeding
- [Transactions & Factories](/guides/record/transactions-factories/) — factories for test data
- [Scopes & Events](/guides/record/scopes-events/) — why seeding does not fire lifecycle events
- [CLI](/guides/cli/) — what sillo's command line actually provides
- [Startup & Shutdown](/guides/startups-and-shutdowns/) — why migrations do not belong in a startup hook
