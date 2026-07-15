---
title: Migrations & Seeding
description: Aerich-powered schema migrations with sillo-native CLI, programmatic API, database seeders, and fixture loaders.
---

# Migrations & Seeding

## Migrations (via aerich)

`sillo.record` uses [aerich](https://github.com/tortoise/aerich) —
Tortoise ORM's official migration tool — as its migration engine.  It
provides a sillo-native CLI wrapper with cleaner command names and a
programmatic API for use in deployment scripts.

### CLI Commands

```bash
sillo record init                    # Create aerich migration tracking table
sillo record migrate -n "add users"   # Generate a migration from model changes
sillo record upgrade                  # Apply all pending migrations
sillo record downgrade abc12345       # Roll back to a specific migration
sillo record history                  # Show migration history
```

These commands are registered via `RecordCLI` which wraps aerich's
internal command class.  The commands are designed to be used with
Click-based CLI tools.

### Programmatic API

```python
from sillo.record.helpers import MigrationHelper

m = MigrationHelper("myapp.models", location="migrations")

await m.init()                          # first-time setup
await m.migrate("add users table")      # generate migration file
await m.upgrade()                       # apply to database
await m.downgrade("abc12345")           # roll back
history = await m.history()             # list applied migrations
```

### How aerich Works

aerich works in four steps:

1. **Init** — Creates an `aerich` table in your database to track
   migration state, plus a `migrations/` directory on disk.

2. **Migrate** — Inspects your Tortoise model classes, compares them
   against the current database schema, and generates a Python migration
   file with `upgrade()` and `downgrade()` functions.  These files are
   stored in `migrations/models/`.

3. **Upgrade** — Executes the `upgrade()` function of each pending
   migration in order, recording each one in the `aerich` tracking table.

4. **Downgrade** — Executes `downgrade()` functions in reverse order
   to roll back to a specific migration.

The migration files are regular Python.  You can inspect, modify, and
version-control them.  aerich uses Tortoise's schema generation under the
hood — the same `generate_schemas()` call used in development.

For more details on aerich's capabilities (merging migrations, squashing,
custom migration operations), see the
[aerich documentation](https://github.com/tortoise/aerich).

### Configuration

The `MigrationHelper` takes an `app_module` — the dotted path to your
Tortoise ORM configuration.  This is typically the same module where
you define your models or where you call `setup_record()`.

The `location` parameter controls where migration files are stored on
disk (default: `migrations/`).

## Seeders

The `Seeder` class populates your database with initial or test data.

```python
from sillo.record.helpers import Seeder

seeder = Seeder(db_manager)

seeder.seed(User, [
    {"email": "admin@example.com", "name": "Admin"},
    {"email": "user@example.com", "name": "User"},
])

seeder.seed(Post, [
    {"title": "Hello World", "content": "First post!", "user_id": 1},
    {"title": "Getting Started", "content": "Welcome to sillo", "user_id": 1},
])

count = await seeder.run()
print(f"Seeded {count} rows")
```

Seeders call `Model.create()` for each record, which triggers lifecycle
events, validators, and auto-timestamps.

### Seeding in Order

Seeders respect the order of `seeder.seed()` calls.  In the example
above, Users are seeded first, then Posts.  This matters when Posts
have a ForeignKey to Users.

### Production Seeding vs Test Seeding

For production, seed only essential data (admin users, default settings).
For tests, seed whatever your test scenarios need.  Use `Factory` for
tests that need randomized data and `Seeder` for tests that need
specific, predictable data.

## Fixture Loader

Load JSON or JSONL files from a directory:

```python
from sillo.record.helpers import FixtureLoader

loader = FixtureLoader("fixtures/")
total = await loader.load_all()      # load everything
count = await loader.load("users")    # load specific file
```

Directory structure:

```
fixtures/
  users.json     → [{"email": "...", "name": "..."}, ...]
  posts.jsonl    → {"title": "..."}\n{"title": "..."}\n...
```

JSON files are parsed as `json.loads()` — they must contain a JSON array.
JSONL files are line-delimited — each line is a separate JSON object.
