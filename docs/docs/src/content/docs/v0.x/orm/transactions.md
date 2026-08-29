---
title: Transactions
description: "Running work atomically: the transaction context manager, nested savepoints, manual begin/commit/rollback, and the concurrency rules that decide where a transaction belongs."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Sillo Record Transactions
  - tag: meta
    attrs:
      property: og:description
      content: The transaction context manager, savepoints, and manual control.
---

```python
from sillo.record.transactions import transaction

async with transaction():
    await account.save()
    await ledger_entry.save()
```

Commits on a clean exit, rolls back on any exception. The exception propagates.
Rolling back is not the same as swallowing.

## Savepoints

A savepoint is a rollback point *inside* a transaction. Work in the block is
undone; the enclosing transaction survives.

```python
async with transaction() as tx:
    await order.save()

    async with tx.savepoint():
        await charge_card(order)      # may fail

    await receipt.save()
```

If `charge_card` raises, only its work is undone, but the exception still
propagates, so the enclosing `async with` rolls back too unless you catch it:

```python
async with transaction() as tx:
    await order.save()

    try:
        async with tx.savepoint():
            await charge_card(order)
    except PaymentDeclined:
        order.status = "payment_failed"
        await order.save()

    await notify(order)
```

That is the shape savepoints are for: one step is allowed to fail without
losing the rest.

They nest, and each gets a driver-generated name, so two open at once do not
collide:

```python
async with transaction() as tx:
    async with tx.savepoint() as sp:
        async with sp.savepoint():
            ...
```

## Multiple connections

```python
async with transaction("replica"):
    ...
```

The name is a Tortoise connection name, defaulting to `"default"`.

A transaction covers **one** connection. Two `async with transaction(...)`
blocks on different connections are two transactions, and one can commit while
the other rolls back. Distributed atomicity is not something this (or any
single-database transaction) provides.

## Manual control

```python
from sillo.record.transactions import begin, commit, rollback

await begin()
try:
    await account.save()
    await commit()
except Exception:
    await rollback()
    raise
```

For a transaction whose boundaries are not a block, spanning a callback, or
driven by a state machine.

:::caution[The context manager is safer]
These three issue raw `BEGIN`, `COMMIT` and `ROLLBACK` on the connection. They
do not participate in the driver's transaction tracking, so mixing them with
`transaction()` (or forgetting the `rollback()` on one path) leaves the
connection in a state later queries inherit.

Use the context manager unless you genuinely cannot.
:::

## Where a transaction belongs

**Around a unit of business meaning**, not around every save.

```python
# too fine — each save is already atomic on its own
async with transaction():
    await post.save()

# right — these two must both happen or neither
async with transaction():
    await account.save()
    await ledger_entry.save()
```

**As short as possible.** A transaction holds locks. An HTTP call inside one
holds them for the length of somebody else's outage:

```python
# wrong
async with transaction():
    await order.save()
    await payment_gateway.charge(order)     # holds locks for seconds

# better
charge = await payment_gateway.charge(order)
async with transaction():
    order.charge_id = charge.id
    await order.save()
```

**Not around a queue dispatch.** A job can be picked up before the transaction
commits, and will then not find the row:

```python
async with transaction():
    await order.save()
    await queue.dispatch(ProcessOrder(order.id))   # racy

# instead
async with transaction():
    await order.save()
await queue.dispatch(ProcessOrder(order.id))
```

## Concurrency

Two transactions touching the same rows will conflict. What happens depends on
the database:

- **PostgreSQL** raises a serialisation failure at `REPEATABLE READ` and above.
  Retry the whole transaction, not part of it.
- **MySQL** may deadlock; it picks a victim and raises.
- **SQLite** locks the whole database for a write. Concurrent writers get
  `database is locked`.

Retry on the transaction as a unit:

```python
from sillo.helpers.retry import retry


@retry(attempts=3, exceptions=(OperationalError,))
async def transfer(source, target, amount):
    async with transaction():
        ...
```

Only retry when the work is idempotent, or the retry re-reads the state it
depends on. Retrying a transaction that computed a value from a stale read
recomputes it from the same stale read.

## In tests

Wrapping each test in a transaction and rolling back is a fast reset, no
truncation, no fixtures reloaded.

It has one catch: code under test that opens its own transaction, or that
depends on a commit having happened, behaves differently inside one. Where that
bites, use a fresh in-memory SQLite database per test instead. See
[Factories](/v0.x/orm/factories/).

## Interaction with the rest

- [`bulk_create` and friends](/v0.x/orm/bulk/) write in batches. Without a
  transaction, a failure halfway leaves earlier batches committed.
- [`after_*` model events](/v0.x/orm/events/#failure-semantics) fire inside the
  transaction when the save is inside one, so a failing hook rolls the write
  back.
- [`ensure_context`](/v0.x/orm/setup/#ensure_context) is what makes the connection
  available per request; a transaction opened in a task that escaped the
  request may not see it.
