---
title: Transactions & Factories
description: Context-manager database transactions with savepoints, manual begin/commit/rollback, and Laravel-style model factories for testing.
---

# Transactions & Factories

## Transactions

`sillo.record.transactions` provides a context-manager API over Tortoise's
database connections.  It supports PostgreSQL, MySQL, MariaDB, and SQLite
via their respective async drivers (asyncpg, aiomysql, aiosqlite).

### Context Manager

The simplest way to use transactions — wrap your operations in an
`async with` block.  On clean exit, the transaction commits.  On
exception, it rolls back automatically.

```python
from sillo.record import transaction

async with transaction():
    user = await User.create(email="a@b.com")
    profile = await Profile.create(user=user, bio="Hello")
    order = await Order.create(user=user, total=99.99)
    # All three committed together

async with transaction():
    user = await User.create(email="b@c.com")
    raise ValueError("something went wrong")
    # User is NOT created — transaction was rolled back
```

### Savepoints

Nested transactions via savepoints.  A savepoint lets you roll back a
subset of operations without affecting the outer transaction:

```python
async with transaction() as tx:
    # Outer transaction
    user = await User.create(email="a@b.com")

    async with tx.savepoint():
        try:
            await call_external_api(user)
            await user.save()
        except Exception:
            pass  # Only the API call is rolled back — user is preserved

    order = await Order.create(user=user)
    # Both user and order are committed
```

Savepoints use `SAVEPOINT sp` / `RELEASE SAVEPOINT sp` / `ROLLBACK TO
SAVEPOINT sp` SQL commands.  Supported by PostgreSQL, MySQL 8.0+,
MariaDB 10.3+.  Not supported by SQLite.

### Manual Control

For scenarios where a context manager doesn't fit:

```python
from sillo.record import begin, commit, rollback

await begin()
try:
    await user.save()
    await order.save()
    await commit()
except Exception:
    await rollback()
    raise
```

### Connection Handling

The `transaction()` context manager calls `connections.get("default")`
from Tortoise's connection pool.  This returns the active connection
for the "default" database.  If you have multiple databases, pass
`connection_name`:

```python
async with transaction(connection_name="analytics"):
    await analytics_event.save()
```

### Tortoise Integration

Tortoise ORM manages connection pools via `asyncpg` (Postgres),
`aiomysql` (MySQL), and `aiosqlite` (SQLite).  Each driver implements
its own transaction protocol.  Tortoise abstracts this with an internal
`_in_transaction()` context manager.  sillo.record wraps this with
additional savepoint support and a cleaner API.

For reference: [Tortoise Transactions](https://tortoise.github.io/transactions.html)

## Factories

Model factories generate test data with sensible defaults.  Inspired by
Laravel's model factories.

```python
from sillo.record import Factory
from uuid import uuid4

class UserFactory(Factory):
    model = User
    definition = lambda: {
        "email": f"user{uuid4().hex[:8]}@test.com",
        "name": "Test User",
    }

# Create and persist:
user = await UserFactory.create()
admin = await UserFactory.create(overrides={"name": "Admin"})

# Create many:
users = await UserFactory.create_many(5)

# Make without saving (for unit tests):
unsaved = UserFactory.make()
assert unsaved.id is None  # Not persisted

# State modifiers:
class UserFactory(Factory):
    @classmethod
    def admin(cls):
        return cls.state(name="Admin", email="admin@test.com")

    @classmethod
    def with_email(cls, email: str):
        return cls.state(email=email)
```

Factories use your model's `.create()` method, which fires all lifecycle
events, validators, and auto-fields.  `.make()` constructs an instance
without saving — perfect for unit tests that don't need a database.

The `FactoryBuilder` registry lets you manage multiple factories:

```python
from sillo.record import FactoryBuilder

builder = FactoryBuilder()
builder.register("user", UserFactory)
builder.register("post", PostFactory)

factory = builder.get("user")
user = await factory.create()
```
