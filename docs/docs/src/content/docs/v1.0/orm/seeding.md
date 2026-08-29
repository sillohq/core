---
title: Seeding & Fixtures
description: "Populating a database with known rows: the Seeder for code-defined data, the FixtureLoader for JSON and JSONL files, ordering, and making seeds re-runnable."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Sillo Record Seeding and Fixtures
  - tag: meta
    attrs:
      property: og:description
      content: Seeder and FixtureLoader, code-defined seeds and JSON/JSONL fixtures.
---

Two ways to put known rows into a database: in code, or in files.

```python
from sillo.record.helpers import Seeder, FixtureLoader
```

## `Seeder`

```python
seeder = Seeder(database)
seeder.seed(User, [
    {"email": "ada@example.com", "username": "ada", "is_staff": True},
    {"email": "bob@example.com", "username": "bob"},
])
seeder.seed(Post, [
    {"title": "Hello", "body": "…", "author_id": 1},
])

created = await seeder.run()
```

`seed()` registers rows and returns the seeder, so calls chain. Nothing is
written until `run()`, which returns the number of rows created.

Order is registration order, `User` rows before `Post` rows above, which is
what lets the post reference an author.

:::note[`batch_size` is accepted and not used]
`run()` takes a `batch_size` parameter, but the implementation creates rows one
at a time regardless.

That is fine for what seeding is for: tens of rows, once. For thousands, use
[`bulk_create`](/v1.0/orm/bulk/) directly.
:::

Each row goes through `create()`, so [model events](/v1.0/orm/events/),
[casts](/v1.0/orm/casting/) and [validation](/v1.0/orm/mixins/#validatesbeforesavemixin)
all apply. Seeded data is real data, written the same way the application would
write it.

## `FixtureLoader`

For data that belongs in files rather than in Python: reference data, a demo
dataset, something a non-developer maintains.

```
fixtures/
  01_users.json
  02_posts.jsonl
```

```json
[
  { "email": "ada@example.com", "username": "ada" },
  { "email": "bob@example.com", "username": "bob" }
]
```

```jsonl
{"title": "Hello", "body": "…", "author_id": 1}
{"title": "World", "body": "…", "author_id": 2}
```

```python
loader = FixtureLoader("fixtures/")
count = await loader.load_all()
```

`.json` holds an array of objects; `.jsonl` holds one object per line. Use
JSONL for anything large. It streams, and a diff shows one changed row rather
than a reindented file.

### Ordering

`load_all()` reads files in **sorted filename order**, which is why the example
numbers them. Fixtures that reference each other need the referenced rows
first, and `01_`/`02_` is how you say so.

Files whose suffix is not `.json` or `.jsonl` are skipped, so a README in the
directory is harmless.

### Naming

The filename stem resolves to a model through Tortoise's registry. When the
name does not match, map it:

```python
loader = FixtureLoader("fixtures/", models={"01_users": User, "02_posts": Post})
```

Which you will need whenever you use numeric prefixes, since `01_users` is not
a model name.

### One file

```python
await loader.load("01_users")
```

Without the extension.

## Where seeding belongs

**A console command.** It runs when you ask, in the environment you ask, and
`sillo` puts it beside every other command:

```python
# app/commands.py
from sillo.console import Command, Flag


class Seed(Command):
    name = "db:seed"
    help = "Load the development dataset"

    arguments = [Flag("force", short="f", help="Run outside development")]

    async def handle(self):
        from app.config import config

        if config.app_env != "local" and not self.flag("force"):
            self.fail("Refusing to seed outside development. Use --force.")

        loader = FixtureLoader("fixtures/")
        count = await loader.load_all()
        self.success(f"Loaded {count} rows.")
```

```python
app.add_command(Seed)
```

```bash
sillo db:seed
```

The environment guard is worth the three lines. Seeding is a write, and the
command that populates your development database looks exactly like the one
that would overwrite production.

## Not in a migration

A migration is applied once per environment, in order, and is expected to be
deterministic. Demo data is none of those things: you want to re-run it, you
want it in development and not in production, and you want to change it without
writing a new migration.

Reference data that the application genuinely requires (currencies, country
codes, a default role) is the exception, and belongs in a migration precisely
because it must exist everywhere the schema does.

## Making seeds re-runnable

`create()` raises on the second run when a unique constraint is involved. To
make a seed idempotent, upsert:

```python
for row in rows:
    await User.upsert(**row, conflict_fields=["email"])
```

Or clear first, deliberately and with the same guard as above:

```python
await Post.all().delete()
await User.all().delete()
```

An idempotent seed is worth the effort. A development database gets reset far
more often than you expect.

## See also

- [Factories](/v1.0/orm/factories/): for test data, generated per test.
- [Bulk operations](/v1.0/orm/bulk/): for large volumes.
- [Migrations](/v1.0/orm/migrations/): for data that must exist everywhere.
