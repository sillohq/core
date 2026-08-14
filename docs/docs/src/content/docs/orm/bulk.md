---
title: Bulk Operations
description: "Inserting and updating many rows at once — bulk_create, upsert and bulk_upsert, their batching, conflict handling, and what they skip."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Sillo Record Bulk Operations
  - tag: meta
    attrs:
      property: og:description
      content: bulk_create, upsert and bulk_upsert — batching, conflict handling and the trade-offs.
---

A loop of `create()` calls is one round trip per row. These are one per batch.

```python
await Post.bulk_create([
    {"title": "First",  "body": "…"},
    {"title": "Second", "body": "…"},
])
```

## `bulk_create`

```python
await Post.bulk_create(
    items,
    batch_size=100,
    ignore_conflicts=False,
    update_fields=None,
    on_conflict=None,
)
```

`items` may be dicts or model instances, mixed freely — dicts are turned into
instances first.

| Parameter | Meaning |
| --- | --- |
| `batch_size` | Rows per statement. Default `100`. |
| `ignore_conflicts` | Skip rows that violate a constraint instead of raising |
| `on_conflict` | The fields whose conflict triggers an update |
| `update_fields` | What to update when one does |

Returns the instances. [Casts](/orm/casting/) are applied — each instance is
encoded before its batch is written.

### Batching

`batch_size` bounds the size of a single statement, not the operation. 10,000
rows at the default is 100 statements.

Raise it for throughput; lower it if you hit a parameter limit (SQLite's is
999 by default, and a wide model reaches it quickly) or if long statements are
holding locks longer than you want.

### `ignore_conflicts`

```python
await Tag.bulk_create(rows, ignore_conflicts=True)
```

Rows that would violate a unique constraint are skipped. The others are
written.

You do not find out which were skipped — the return value is the instances you
passed, not what landed. When you need to know, query afterwards, or use
`upsert` so every row ends up in a known state.

## `upsert`

Insert, or update if it is already there. One statement, using the database's
native `ON CONFLICT` support.

```python
setting = await Setting.upsert(
    key="theme",
    value="dark",
    conflict_fields=["key"],
)
```

| Parameter | Meaning |
| --- | --- |
| `conflict_fields` | The unique key that decides insert vs update. Required. |
| `update_fields` | What to write on a conflict. Defaults to every field except the conflict fields and the primary key. |

Returns the row, re-fetched — and fetched through
[`without_global_scopes()`](/orm/scopes/#escaping-them), so upserting a
soft-deleted row still returns it rather than raising `DoesNotExist`.

:::note[The conflict fields need a real constraint]
`ON CONFLICT` needs a unique index on those columns. Without one the database
has nothing to detect a conflict against, and you get an error or a duplicate
depending on the backend.

```python
class Setting(Model):
    key = fields.CharField(max_length=100, unique=True)
```
:::

### Why not `get_or_create`

[`get_or_create`](/orm/models/#fetch-shortcuts) is a `SELECT` then an `INSERT`,
and two concurrent callers can both find nothing and both insert.

`upsert` is one statement, so the database resolves the race. Prefer it
whenever the row might be written concurrently — a webhook handler, a job that
can be retried, anything idempotent by design.

## `bulk_upsert`

The same, for many rows:

```python
await Setting.bulk_upsert(
    [
        {"key": "theme", "value": "dark"},
        {"key": "locale", "value": "en"},
    ],
    conflict_fields=["key"],
    update_fields=["value"],
    batch_size=100,
)
```

This is the shape for syncing from an external source: pull the current state,
upsert the lot, and let the database decide row by row what was new.

## What bulk operations skip

| | Applied? |
| --- | --- |
| [Casts](/orm/casting/) | Yes |
| [Model events](/orm/events/) | **No** |
| [`ValidatesBeforeSaveMixin`](/orm/mixins/#validatesbeforesavemixin) | **No** |
| Auto `updated_at` on a conflict update | Depends on `update_fields` |

Events and validation are skipped because they are per-instance hooks and these
paths do not call `save()`. That is the deliberate trade — loading and hooking
every row would defeat the point — but it means:

- validate the input yourself before a bulk write;
- fire any follow-on work explicitly afterwards;
- include `updated_at` in `update_fields` if you want it to move.

## Wrap it

```python
from sillo.record.transactions import transaction

async with transaction():
    await Post.bulk_create(batch_one)
    await Tag.bulk_create(batch_two)
```

A multi-batch write that fails halfway has already committed the earlier
batches. A [transaction](/orm/transactions/) makes the whole thing one unit.

## When not to

For a handful of rows, `create()` in a loop is clearer, fires events, and runs
validation. The cost of ten round trips is not worth the loss of all three.

Bulk operations are for hundreds and up: an import, a backfill, a sync.
