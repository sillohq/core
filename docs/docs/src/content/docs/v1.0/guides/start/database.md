---
title: Database & Migrations
description: How a Sillo project connects, where models live, the migration workflow, switching to PostgreSQL or MySQL, and the failure modes worth knowing before they happen.
head:
  - tag: meta
    attrs:
      property: og:title
      content: Database & Migrations in a Sillo Project
  - tag: meta
    attrs:
      property: og:description
      content: How a Sillo project connects, where models live, and the migration workflow.
---

#  Database & Migrations

A new project uses SQLite at `storage/myapp.db` and needs nothing
installed. Changing that is one environment variable.

```bash
sillo db:migrate                   # create the database, apply what is pending
sillo db:make add_posts --apply   # write a migration from your models, and apply it
sillo db:plan                      # what would run
sillo db:rollback 0001_initial  # go back
```

##  One definition of the connection

`database/config.py` describes how the project connects, once. The running
application, the migration commands and any script of yours all read it.

```python
MODEL_MODULES = ["database.models"]
MIGRATIONS_MODULE = "database.migrations"


def database_config() -> DatabaseConfig:
    """The connection settings for this project."""
    return DatabaseConfig(
        url=config.database_url,
        pool_size=config.db_pool_size,
        echo=config.db_echo,
        generate_schemas=config.db_generate_schemas,
    )


def database() -> DatabaseManager:
    """A manager for this project's database."""
    manager = DatabaseManager(database_config())
    manager.register_models(*MODEL_MODULES).set_migrations(MIGRATIONS_MODULE)
    return manager
```

There is **no separate migration configuration**, no second file declaring the
same connection in a different shape. Change the URL here and migrations
follow.

It sits in `database/` rather than `app/` because it belongs with the
models it registers and the migrations it points at. The whole data layer
is one directory.

###  Opening it yourself

```python
from database.config import database

async with database():
    await User.all()
```

The manager is an async context manager: it opens the connection and closes it
again. Closing matters. An open connection keeps the event loop alive, and a
script that finishes its work and then hangs at exit is usually this rather
than a deadlock.

The application does not call `database()`; `setup_record` in
`app/bootstrap.py` builds its own manager from the same
`database_config()` and ties it to startup and shutdown.

##  Models

One model per file in `database/models/`, imported in `__init__.py`:

```python
# database/models/post.py
from sillo.record import Model
from tortoise import fields


class Post(Model):
    """Something someone wrote."""

    title = fields.CharField(max_length=200)
    body = fields.TextField()
    published_at = fields.DatetimeField(null=True)

    class Meta:
        table = "posts"

    def __str__(self) -> str:
        return self.title
```

```python
# database/models/__init__.py
from database.models.post import Post
from database.models.user import User

__all__ = ["Post", "User"]
```

:::caution
**A model not imported there is invisible.** The ORM discovers by module scan,
so a model in a file nobody imports never gets a table, and the first query
against it fails with `default_connection cannot be None`, which points at the
database rather than at the missing import. It is the most confusing error a
new project can produce, and it always means this.
:::

###  A model's docstring is not just documentation

It becomes the table's `table_description` in the database. Change it and
the next `sillo db:make` writes a migration whose only content is a
changed comment.

That is harmless but noisy, and it is why project renaming deliberately
skips model files.

##  The migration workflow

###  Changing a model

```bash
# edit database/models/post.py
sillo db:make add post slug --apply
```

That writes a migration **and applies it**. To write without applying:

```bash
uv run sillo db:make add_post_slug
uv run sillo db:plan          # look at what would run
uv run sillo db:migrate       # apply it
```

###  After pulling someone else's work

```bash
sillo db:migrate
```

Applies anything new. Safe when there is nothing to do.

###  Always read the generated migration

The generated file is ordinary Python. Open it before applying it. The
diff engine is good at additive changes and unreliable at others:

**A renamed column is detected as a drop plus an add.** That is a
data-destroying operation dressed as a rename. Edit it into an
`ALTER TABLE ... RENAME COLUMN` by hand.

**A changed column type is emitted with no `USING` clause**, which fails
on PostgreSQL whenever the conversion is not implicit.

**A new non-null column without a default fails on any table with rows.** Add
it nullable, backfill, then add the constraint, three migrations, not one.

To see the SQL without running it:

```python
from sillo.record.commands import sql
from database.config import database

for statement in await sql(database(), "0003_add_post_slug"):
    print(statement)
```

###  Rolling back

```bash
sillo db:rollback 0002_add_tags   # back to this migration
sillo db:rollback zero            # unapply everything
```

There is no "one step back". You name where to stop. That is deliberate: "one
step" is ambiguous the moment two people have merged migrations, and naming the
target is unambiguous always.

##  Schema generation is off, on purpose

```python
db_generate_schemas: bool = False
```

Turning it on makes the ORM create any missing tables from your models at
every startup. Convenient for a scratch database; wrong once you have
migrations, for two reasons.

**It creates tables outside the migration history.** A later
`sillo db:make` sees them as new and writes a migration that then fails
to apply against tables that already exist.

**Every process does it at once.** An application, a worker and a
scheduler sharing one SQLite file will race to issue DDL on boot and raise
`database is locked`.

Set `DB_GENERATE_SCHEMAS=true` if you want it for a throwaway database (tests
do exactly that) but leave it off in anything that keeps data.

##  Another database

```bash
# PostgreSQL
DATABASE_URL=postgres://user:password@localhost:5432/myapp
uv add asyncpg

# MySQL
DATABASE_URL=mysql://user:password@localhost:3306/myapp
uv add aiomysql
```

Nothing else changes. The driver is resolved from the URL scheme, and
`postgresql://` and `mariadb://` are accepted as aliases.

Pool settings and TLS come from the same config:

```bash
DB_POOL_SIZE=10
DB_ECHO=false        # log every query — useful locally, never in production
DB_SSL=true
DB_SSL_CA=/path/to/ca.pem
```

`pool_size` and `max_overflow` map to the driver's own connection pool;
`pool_recycle` becomes `pool_recycle` on MySQL and
`max_inactive_connection_lifetime` on PostgreSQL, which are the same idea
under different names.

:::danger
**If you develop on SQLite and deploy on PostgreSQL, your migrations are
being tested against the wrong engine.** SQLite cannot drop a column,
change a type, or add a constraint; the engine works around that by
recreating the table and copying data, which is slow, locks the table, and
drops anything the recreation did not know to preserve.

Run migrations against a real PostgreSQL instance in CI before they reach
production.
:::

##  What lives in the database

A new project has two tables:

| Table | |
| --- | --- |
| `users` | Your user model. Everyone: including administrators |
| `tortoise_migrations` | Which migrations have been applied |

`MODEL_MODULES` is what decides this:

```python
MODEL_MODULES = ["database.models"]
```

A package that brings models of its own goes in the same list.
[Warder](/packages/warder/), the admin panel, keeps an activity log in
`warder.models`; installing it means one more entry here and one more
migration.

What a project should not add is a second user table. One `User`, and
everything authenticates against it — two sets of accounts is two things to
keep in step, or to forget about.

##  Migrations in a deployment

Run them as a **separate step before the new version starts**, not from
application startup code. Three replicas that each migrate on boot produce
three concurrent schema changes and, on a good day, two failures.

```bash
uv run sillo db:migrate && exec uvicorn app.main:app --host 0.0.0.0 --port 8000
```

That is fine for a single instance. For rolling deployments, make it a job that
runs once and gates the rollout, and keep each migration compatible with both
the old and the new application version. Add columns before the code that
writes them, drop them a release after the code that read them is gone.

##  Seeding

For reference data (roles, plans, countries) make it idempotent, because it
will run more than once:

```python
async def seed_defaults():
    await Role.get_or_create({"label": "Administrator"}, slug="admin")
    await Role.get_or_create({"label": "Member"}, slug="member")
```

A console command is the natural home:

```python
async def seed(args) -> int:
    """Insert the reference data this application assumes exists."""
    await seed_defaults()
    print("Seeded.")
    return 0
```

```python
seed_cmd = commands.add_parser("seed", help="Insert reference data.")
seed_cmd.set_defaults(run=seed, needs_database=True)
```

Reference data belongs in version control next to the migrations. Test
data belongs in the test suite. Mixing them gives you production databases
full of "Test User".

##  Under the hood

The migration commands are functions in `sillo.record.commands`, and they
take the manager:

```python
from sillo.record.commands import init, make, migrate, plan, rollback, sql
from database.config import database

await init(database())              # create the migrations package
await make(database(), "add_slug")  # write a migration
await migrate(database())           # apply what is pending
await plan(database())              # list without running
await rollback(database(), "0003_add_slug")
```

Two of them (`init` and `make`) exist only behind the engine's own command
line, which reads its configuration by *importing a dotted path* rather than
taking a value. Sillo handles that internally, publishing the configuration on
a module it owns and handing over the path to that.

The result is that a project needs no module written for the migration
engine's benefit: no `TORTOISE_ORM` at module level, no dotted path
repeated in your tooling. That plumbing is why `database/config.py` can be
an ordinary Python module shaped the way your project wants.

##  Things that will bite you

1. **A model not imported in `database/models/__init__.py` has no table**,
   and says `default_connection cannot be None`.

2. **Commit `database/migrations/`.** The database file is gitignored
   precisely so the migrations have to be the source of truth.

3. **Never commit `*.db-wal` or `*.db-shm`.** A clone with a stale
   write-ahead log reports `disk I/O error`, which sounds like hardware
   and is not.

4. **`sillo db:make` with no `m=` writes a migration called `update`.**
   Harmless, uninformative, and permanent.

5. **Two people adding migrations in parallel** produce two `0002_` files.
   Rename one and reorder before merging. The engine orders by name.

##  Related

- [Project Structure](/v1.0/guides/start/structure/): where the data layer sits
- [The Console](/v1.0/guides/start/console/): the `db` commands in detail
- [Models & Mixins](/v1.0/guides/record/models/): what you can put in a model
- [Migrations & Seeding](/v1.0/guides/record/migrations/): the framework-level
  reference
- [Deployment](/v1.0/guides/start/deployment/): migrating on deploy
