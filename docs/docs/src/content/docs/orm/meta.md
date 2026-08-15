---
title: Meta, Indexes & Constraints
description: "The model Meta class in full (table naming, default ordering, unique_together, indexes, check constraints, schemas, abstract bases) and how each reaches the database."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Sillo Record Meta, Indexes and Constraints
  - tag: meta
    attrs:
      property: og:description
      content: table, ordering, unique_together, indexes, constraints, schema and abstract.
---

```python
from tortoise import fields
from tortoise.indexes import Index
from sillo.record import Model


class Post(Model):
    id = fields.IntField(primary_key=True)
    slug = fields.CharField(max_length=200)
    author = fields.ForeignKeyField("models.Author", related_name="posts")
    status = fields.CharField(max_length=20)
    published_at = fields.DatetimeField(null=True)

    class Meta:
        table = "posts"
        ordering = ["-published_at"]
        unique_together = (("author", "slug"),)
        indexes = (Index(fields=("status", "published_at")),)
        table_description = "Published and draft articles."
```

## The options

| Option | Default | Meaning |
| --- | --- | --- |
| `table` | derived | The table name |
| `schema` |  | The database schema (PostgreSQL) |
| `app` | `models` | The app label |
| `abstract` | `False` | A base class with no table of its own |
| `ordering` |  | Default sort for every query |
| `unique_together` | `()` | Multi-column unique constraints |
| `indexes` | `()` | Multi-column indexes |
| `constraints` | `()` | Check constraints |
| `table_description` | `""` | The table comment |
| `manager` | `RecordManager()` | The default manager |
| `pk_attr` | derived | Which field is the primary key |

## `table`

Without it, the table name is derived from the class name. Set it explicitly
for anything long-lived. A renamed class then costs no migration, and the
schema stops depending on a Python identifier.

```python
class BlogPost(Model):
    class Meta:
        table = "posts"
```

## `ordering`

```python
ordering = ["-published_at", "id"]
```

Applied to every query that does not specify its own. `order_by()` replaces it
rather than adding to it.

**Include a tiebreaker.** `-published_at` alone is not a stable order if two
rows share a timestamp, and unstable ordering means rows appear on two pages of
a paginated list or on none. See
[Pagination](/orm/pagination/#ordering-is-not-optional).

An ordering the database cannot satisfy from an index is a sort on every query.
If the model is large and always read in one order, index that order
(`Index(fields=("published_at",))`) and check it with
[`explain()`](/orm/queries/#explain).

## `unique_together`

```python
unique_together = (("author", "slug"),)
unique_together = (("author", "slug"), ("tenant", "external_id"))
```

A tuple of tuples, even for one. `(("author", "slug"))` without the trailing
comma is a tuple of strings and does not mean what it looks like.

This is a real constraint, enforced by the database for every writer. It is
what makes [`get_or_create`](/orm/models/#fetch-shortcuts) and
[`upsert`](/orm/bulk/#upsert) safe under concurrency, without it, two
simultaneous callers both insert.

A unique constraint creates an index, so a separate `indexes` entry on the same
columns in the same order is redundant.

:::note[NULL is not equal to NULL]
A unique constraint over a nullable column does not stop two rows both having
`NULL` there. That is standard SQL, and it surprises people every time.

For "at most one active row per author", a partial unique index is the answer,
and that needs a hand-written migration.
:::

## `indexes`

```python
from tortoise.indexes import Index

indexes = (
    Index(fields=("status", "published_at")),
    Index(fields=("author", "status")),
)
```

For single columns, `db_index=True` on the field is the same thing more locally:

```python
slug = fields.CharField(max_length=200, db_index=True)
```

### Column order matters

An index on `(status, published_at)` serves:

- `WHERE status = ?`
- `WHERE status = ? ORDER BY published_at`
- `WHERE status = ? AND published_at > ?`

and **not** `WHERE published_at > ?` on its own. An index is usable left to
right, like a phone book sorted by surname then first name.

So order the columns by how you actually query: equality filters first, then
the range or sort column.

### What to index

- Every foreign key you filter or join on. Tortoise does **not** index them
  automatically.
- Columns in a `WHERE` on a table big enough to notice.
- The column you sort by, when combined with the filter column.

### What not to

Indexes are not free: every insert, update and delete maintains them, and they
take space. An index nothing uses is pure cost.

Two specific cases that do not work the way people hope:

- **Low-cardinality columns.** An index on a boolean rarely helps; the database
  will scan anyway.
- **`LIKE '%term%'`**, which is what [`icontains`](/orm/lookups/) compiles to.
  A leading wildcard cannot use a B-tree index. For real search, use a trigram
  index on PostgreSQL or a search service.

Verify with [`explain()`](/orm/queries/#explain) rather than assuming.

## `constraints`

Check constraints, expressed in the database:

```python
from pypika_tortoise.terms import Criterion

class Product(Model):
    price = fields.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        constraints = (Criterion.any([...]),)
```

In practice most projects write these in a hand-edited migration, where the SQL
is plain and reviewable:

```python
ops.RunSQL(
    "ALTER TABLE products ADD CONSTRAINT price_non_negative CHECK (price >= 0)",
    reverse_sql="ALTER TABLE products DROP CONSTRAINT price_non_negative",
)
```

A check constraint holds for **every** writer: a migration, a console session,
another service. That is the difference from
[`ValidatesBeforeSaveMixin`](/orm/mixins/#validatesbeforesavemixin), which only
applies to writes going through the model.

Use both: the constraint for correctness, the model-level check for a decent
error message.

Not supported on MySQL before 8.0.16, where check constraints are parsed and
ignored.

## `abstract`

```python
class Tenanted(Model):
    tenant = fields.ForeignKeyField("models.Tenant")

    class Meta:
        abstract = True


class Invoice(Tenanted):
    total = fields.DecimalField(max_digits=10, decimal_places=2)
```

An abstract model has no table. Its fields are copied into each subclass, and
each subclass gets its own table with its own copy of the column.

This is how [`sillo.record.Model`](/orm/models/) itself supplies `created_at`,
`updated_at` and `deleted_at`.

`Meta` is **not** inherited. A subclass that needs `ordering` or `indexes`
declares its own, and to keep a parent's options, inherit its `Meta`
explicitly:

```python
class Invoice(Tenanted):
    class Meta(Tenanted.Meta):
        abstract = False
        table = "invoices"
```

## `schema`

```python
class AuditEntry(Model):
    class Meta:
        schema = "audit"
        table = "entries"
```

PostgreSQL schemas. For separating an audit or reporting namespace inside one
database. Ignored on backends without the concept.

## `table_description`

```python
class Meta:
    table_description = "Published and draft articles."
```

Becomes the table comment.

:::caution[The docstring is the default]
A model's docstring becomes `table_description` when `Meta` does not set one,
so **editing a model's docstring produces a migration**.

That is why [`sillo-start` does not rewrite model
files](/start/personalisation/#model-files) when it renames a project. Setting
`table_description` explicitly pins it and makes the docstring free to edit.
:::

## `manager`

```python
class Meta:
    manager = RecordManager()
```

The base model sets this, and it is what applies [global
scopes](/orm/scopes/#global-scopes). Replacing it with a manager that does not
subclass `RecordManager` silently switches global scopes off, a quiet failure,
and worth knowing before you write a custom manager.

## `app`

```python
class Meta:
    app = "reporting"
```

The migration app label. Most projects have one, `models`. A second one means
a second set of [migration commands](/cli/standalone-consoles/#record_commands).

## Reading it back

```python
Post._meta.db_table          # "posts"
Post._meta.fields            # every field name
Post._meta.fields_map        # name -> Field instance
Post._meta.pk_attr           # "id"
Post._meta.fk_fields         # forward foreign keys
Post._meta.m2m_fields
Post._meta.backward_fk_fields
```

Private, and stable enough that the framework itself uses it. The
[admin](/orm/admin/) builds its forms from `fields_map`, and
[`mass_assignable_fields`](/orm/mass-assignment/) reads `fields`. Useful for
your own generic tooling; treat it as an internal API when upgrading.
