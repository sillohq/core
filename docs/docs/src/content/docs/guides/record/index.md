---
title: Record Overview
description: sillo.record — Eloquent-level database toolkit wrapping Tortoise ORM with mixins, scopes, events, casting, collections, transactions, factories, and pagination.
---

# Record (`sillo.record`)

`sillo.record` wraps [Tortoise ORM](https://tortoise.github.io/) with a
Laravel Eloquent-style developer experience.  It does **not** fork
Tortoise — every Tortoise feature (fields, querysets, relations, raw
SQL, schema generation, migration tooling) works exactly as documented
at tortoise.github.io.  What sillo.record adds is a convenience layer:
mixins for common patterns, lifecycle events, attribute casting,
chainable collections, context-manager transactions, model factories for
testing, cursor pagination, and a Pydantic schema bridge.

## Why Tortoise ORM?

Tortoise ORM is an async-first ORM for Python, inspired by Django's ORM.
It uses `asyncpg` for PostgreSQL, `aiomysql` for MySQL/MariaDB, and
`aiosqlite` for SQLite — all native async drivers with connection
pooling.  Unlike SQLAlchemy (synchronous core with async extension),
Tortoise was designed from the ground up for `asyncio`.  Its query
builder and relationship management are battle-tested across thousands of
projects.

Sillo chooses Tortoise because:

1. **Async-native.**  No thread pools, no `run_in_executor`.  Every query
   is a native `await`.
2. **Django-like API.**  Developers familiar with Django's ORM can use
   Tortoise immediately.  The queryset API is nearly identical.
3. **Schema generation.**  Tortoise can create tables from model
   definitions (`generate_schemas`), making it zero-config for
   development.
4. **Migration support** via [aerich](https://github.com/tortoise/aerich),
   which is deeply integrated into sillo.record's CLI.

## Architecture

```
sillo.record
├── Models (extends Tortoise Model)
│   ├── Mixins (SoftDeletes, Timestamps, HasUlid, SerializesToDict, etc.)
│   ├── Scopes (local/global query scopes)
│   ├── Events (lifecycle: before_create, after_save, etc.)
│   └── Casting (json, datetime, encrypted, bool, int, float)
├── Queries (pagination via TortoiseDataHandler, iter_all, explain)
├── Transactions (context-manager, savepoints, manual begin/commit/rollback)
├── Factories (Laravel-style model factories for testing)
├── Collection (map, filter, pluck, group_by, sum, avg, chunk, etc.)
├── Pydantic Bridge (auto-generate Pydantic schemas from Tortoise fields)
├── Exception Handlers (DoesNotExist→404, IntegrityError→409, etc.)
├── CLI (sillo record init/migrate/upgrade/downgrade/history)
└── Helpers (Seeder, FixtureLoader, MigrationHelper)
```

## Quick Start

```python
from sillo import silloApp
from sillo.record import setup_record, DatabaseConfig, Model, register_db_exception_handlers
from tortoise import fields

app = silloApp()
db = setup_record(app, DatabaseConfig.sqlite("myapp.db"),
                  model_modules=["myapp.models"])
register_db_exception_handlers(app)

class User(Model):
    id = fields.IntField(pk=True)
    email = fields.CharField(max_length=255, unique=True)
    name = fields.CharField(max_length=100)

# Create:
user = await User.create(email="a@b.com", name="Alice")

# Query:
users = await User.active().filter(name__icontains="ali").all()

# Serialize:
user.to_dict()

# Soft delete:
await user.soft_delete()
```

## Guides

- [Models & Mixins](/guides/record/models/) — base model, soft-deletes, timestamps, ULID, serialization, validation, cascading deletes
- [Scopes & Events](/guides/record/scopes-events/) — local/global query scopes, lifecycle events, observers
- [Casting & Collections](/guides/record/casting-collections/) — attribute casting, chainable result collections
- [Pagination](/guides/record/pagination/) — page-number, limit-offset, cursor strategies via Tortoise data handlers
- [Transactions & Factories](/guides/record/transactions-factories/) — context-manager transactions, savepoints, model factories
- [Exception Handlers & Pydantic](/guides/record/exceptions-pydantic/) — DB error → HTTP mapping, auto-generated Pydantic schemas
- [Migrations & Seeding](/guides/record/migrations/) — aerich integration, seeders, fixtures
