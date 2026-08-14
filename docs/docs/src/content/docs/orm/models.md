---
title: Models
description: "The Record base model — automatic timestamps and soft deletes, Meta options, serialisation with to_dict and to_json, and the get_or_none and get_or_create shortcuts."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Sillo Record Models
  - tag: meta
    attrs:
      property: og:description
      content: The base model, its automatic fields, Meta options and serialisation.
---

```python
from sillo.record import Model
from tortoise import fields


class Post(Model):
    id = fields.IntField(pk=True)
    title = fields.CharField(max_length=200)
    body = fields.TextField()
    author = fields.ForeignKeyField("models.User", related_name="posts")

    class Meta:
        table = "posts"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
```

`Model` is Tortoise's `Model` with three mixins already applied. Fields,
relations, querysets and `Meta` all work as the
[Tortoise documentation](https://tortoise.github.io/) describes.

## What you get for free

Three fields are declared on the base class, so every model has them without
saying so:

| Field | Behaviour |
| --- | --- |
| `created_at` | Set to UTC now on insert. Never updated. |
| `updated_at` | Set to UTC now on every save. |
| `deleted_at` | Nullable. `None` means active. |

```python
post = await Post.create(title="Hello", body="…")
post.created_at        # datetime, UTC
post.deleted_at        # None
```

They are real columns and appear in your migrations. If you do not want them,
inherit from Tortoise's `Model` directly — there is no way to switch them off
individually, because a base class that sometimes has a column is a base class
whose migrations are unpredictable.

## `__str__` is worth writing

The [admin panel](/orm/admin/) uses it as a row's default label, and so does
every debugging session. A model without one shows as `Post object (4)`.

## Serialisation

```python
post.to_dict()
post.to_dict(exclude=["body"])
post.to_dict(include=["id", "title"])

post.to_json()
post.to_json(indent=2)
```

`include` wins when both are given: it is a whitelist, and a whitelist that
also honoured a blacklist would be ambiguous about which one was the mistake.

Relations are not followed by default. Fetch them first:

```python
await post.fetch_related("author")
```

:::caution[Exclude what should not leave the process]
`to_dict()` returns every field it can see, including a hashed password if the
model has one. Naming an exclusion at each call site means one call site
eventually forgets.

Prefer a [Pydantic response model](/orm/pydantic/), which states the shape once
and is also what the OpenAPI schema is generated from.
:::

## Fetch shortcuts

```python
post = await Post.get_or_none(id=4)
```

`None` instead of raising `DoesNotExist`. The right shape when absence is an
expected answer — a lookup by a user-supplied id, say.

```python
tag, created = await Post.get_or_create(
    slug="python",
    defaults={"title": "Python"},
)
```

Returns the instance and whether it was created. `defaults` supplies the fields
used only on creation; the rest are the lookup.

:::note[`get_or_create` is not atomic]
It is a `SELECT` followed by an `INSERT`. Two concurrent callers can both find
nothing and both insert. Put a unique constraint on the lookup fields so the
loser gets an `IntegrityError` rather than a duplicate row, and handle it — or
use [`upsert`](/orm/bulk/#upsert), which is one statement.
:::

## Soft deletes

```python
await post.soft_delete()      # sets deleted_at
await post.restore()          # clears it
await post.delete()           # actually deletes the row

await Post.active()           # deleted_at IS NULL
await Post.deleted()          # deleted_at IS NOT NULL
await Post.count_active()
```

`active()` and `deleted()` return querysets, so they chain:

```python
recent = await Post.active().order_by("-created_at").limit(10)
```

:::caution[The default queryset includes soft-deleted rows]
`Post.all()` and `Post.filter(...)` return everything, deleted included.
`active()` is opt-in.

That is the opposite of Django's convention, and it is the mistake to watch
for. To make it automatic, add a [global scope](/orm/scopes/#global-scopes).
:::

More in [Mixins](/orm/mixins/#softdeletesmixin).

## `Meta`

Tortoise's `Meta` options all apply — `table`, `ordering`, `unique_together`,
`indexes`, `abstract`, `table_description`.

```python
class Meta:
    table = "posts"
    ordering = ["-created_at"]
    unique_together = (("author", "slug"),)
```

The base class sets `manager = RecordManager()`, which is what applies
[global scopes](/orm/scopes/). If you set your own `manager`, subclass
`RecordManager` or global scopes stop being applied.

:::caution[A docstring is a schema change]
A model's docstring becomes its `table_description`. Editing one produces a
migration — which is why [`sillo-start` does not rewrite model
files](/start/personalisation/#model-files) when it renames a project.
:::

## The rest

- [Fields](/orm/fields/) — the field types Record adds
- [Mass assignment](/orm/mass-assignment/) — `fillable` and `guarded`
- [Mixins](/orm/mixins/) — the composable behaviours
- [Bulk operations](/orm/bulk/) — `bulk_create`, `upsert`, `bulk_upsert`
