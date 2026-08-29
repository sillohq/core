---
title: Field Reference
description: "Every field type available on a Sillo model (numbers, text, dates, binary, JSON, UUID and enums) with the arguments each accepts and what they map to per backend."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Sillo Record Field Reference
  - tag: meta
    attrs:
      property: og:description
      content: Every field type, its arguments, and its column type per backend.
---

```python
from tortoise import fields
from sillo.record import Model


class Post(Model):
    id = fields.IntField(primary_key=True)
    title = fields.CharField(max_length=200)
    body = fields.TextField()
    views = fields.IntField(default=0)
    published_at = fields.DatetimeField(null=True)
```

Plus the [six Record adds](/v0.x/orm/fields/): `PasswordField`, `SlugField`,
`ULIDField` and the three timestamp fields.

## Arguments every field takes

| Argument | Default | Meaning |
| --- | --- | --- |
| `primary_key` | `False` | This is the primary key |
| `null` | `False` | The column accepts `NULL` |
| `default` |  | Value when none is given. A callable is called per row. |
| `unique` | `False` | Adds a unique constraint |
| `db_index` | `False` | Adds an index |
| `description` |  | Becomes the column comment |
| `source_field` |  | The column name, when it differs from the attribute |
| `validators` | `[]` | Validators run before write |
| `generated` | `False` | The database supplies it |

```python
slug = fields.CharField(max_length=200, unique=True, db_index=True)
uuid = fields.UUIDField(primary_key=True, default=uuid4)
legacy = fields.CharField(max_length=50, source_field="legacy_col")
```

:::caution[A mutable default is shared]
```python
tags = fields.JSONField(default=[])       # wrong — one list, every row
tags = fields.JSONField(default=list)     # right — a new list per row
```
Pass the callable, not the value. This is the same trap as a mutable default
argument in Python, with the same fix.
:::

### `null` versus `default`

They answer different questions. `null=True` says the column may hold `NULL`;
`default=` says what to write when you do not supply a value. A field can have
both, either, or neither.

For text, prefer an empty string over `NULL` unless "unset" and "empty" are
genuinely different states. Otherwise every query needs to handle both.

## Numbers

| Field | Range | Notes |
| --- | --- | --- |
| `IntField` | 32-bit | The default choice |
| `SmallIntField` | 16-bit | ±32,767 |
| `BigIntField` | 64-bit | For ids that will exceed 2 billion |
| `FloatField` | double | Binary floating point |
| `DecimalField` | exact | Requires `max_digits` and `decimal_places` |

```python
quantity = fields.IntField(default=0)
weight = fields.FloatField()
price = fields.DecimalField(max_digits=10, decimal_places=2)
```

**Use `DecimalField` for money.** `FloatField` is binary floating point:
`0.1 + 0.2` is not `0.3`, and a ledger built on it will not balance.
`max_digits=10, decimal_places=2` gives you up to 99,999,999.99.

`max_digits` counts *all* digits, not the ones before the point.

:::note[Decimal on SQLite]
SQLite has no decimal type; Tortoise stores it as `VARCHAR` and converts.
Comparisons still work, but arithmetic in raw SQL will not behave the way it
does on PostgreSQL. Something to know when your development database is SQLite
and production is not.
:::

An auto-incrementing primary key is `IntField(primary_key=True)`. The
`generated` flag follows from being an integer primary key.

## Text

| Field | Notes |
| --- | --- |
| `CharField` | `max_length` is **required** |
| `TextField` | Unbounded. Cannot be indexed on MySQL without a prefix length. |

```python
title = fields.CharField(max_length=200)
body = fields.TextField()
```

Pick `CharField` when there is a real bound: an email, a slug, a status. The
length is a constraint the database enforces, and it is what lets the column be
indexed everywhere.

Pick `TextField` for prose. Do not reach for `CharField(max_length=65535)` to
avoid choosing.

## Booleans

```python
is_active = fields.BooleanField(default=True)
```

Stored as a real boolean on PostgreSQL, as `TINYINT(1)` on MySQL, and as an
integer on SQLite. All three round-trip as Python `bool`.

Give it a default. A nullable boolean has three states, and almost no domain
actually wants that.

## Dates and times

| Field | Python type |
| --- | --- |
| `DatetimeField` | `datetime` |
| `DateField` | `date` |
| `TimeField` | `time` |
| `TimeDeltaField` | `timedelta` |

```python
published_at = fields.DatetimeField(null=True)
birth_date = fields.DateField()
duration = fields.TimeDeltaField()
```

Two automatic modes:

```python
created = fields.DatetimeField(auto_now_add=True)   # set on insert only
updated = fields.DatetimeField(auto_now=True)       # set on every save
```

Which is exactly what [`CreatedAtField` and
`UpdatedAtField`](/v0.x/orm/fields/#the-timestamp-fields) wrap, and why you rarely
write these yourself. The [base model](/v0.x/orm/models/) already has both.

:::caution[Store UTC]
`DB_TIMEZONE` defaults to `UTC` and should stay there. A database in local time
either loses an hour or repeats one every year, and the bug arrives at 2am on a
Sunday in October.

Convert at the edges. When rendering, not when storing.
:::

## UUID

```python
from uuid import uuid4

id = fields.UUIDField(primary_key=True, default=uuid4)
```

Native `uuid` on PostgreSQL, `CHAR(36)` elsewhere.

A UUID primary key does not leak a row count and can be generated before the
insert, useful when a client needs the id up front. The cost is index locality:
random UUIDs scatter writes across the index.
[`ULIDField`](/v0.x/orm/fields/#ulidfield) is the middle ground, sorting by creation
time while staying opaque.

## Binary

```python
thumbnail = fields.BinaryField()
```

`BYTEA` on PostgreSQL, `BLOB` elsewhere. For small binary values: a hash, a
signature, an icon.

Not for uploads. Files belong on disk or in object storage, with the path in a
`CharField`: a row with a 5MB column in it makes every query that touches the
table slower, including the ones that do not select the column.

## JSON

```python
metadata = fields.JSONField(default=dict)
```

Native `JSONB` on PostgreSQL, `JSON` on MySQL, `TEXT` on SQLite.

It has its own lookups (`contains`, `contained_by`, `filter`) rather than the
usual set. See [Lookups](/v0.x/orm/lookups/#json-fields).

```python
await Post.filter(metadata__filter={"theme": "dark"})
```

JSON is right for genuinely open-ended data: a webhook payload, per-tenant
settings, an audit snapshot. It is wrong as a way to avoid deciding on columns:
you lose type checking, defaults, constraints and most index options, and every
consumer has to handle a shape that is not enforced anywhere.

If you find yourself querying inside the same key repeatedly, that key wants to
be a column.

Related: the [`json` cast](/v0.x/orm/casting/) does the same conversion over a
`TextField`, for when you cannot change the column type.

## Enums

Two, depending on how you want the value stored:

```python
from enum import Enum, IntEnum


class Status(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class Priority(IntEnum):
    LOW = 1
    NORMAL = 2
    HIGH = 3


class Post(Model):
    status = fields.CharEnumField(Status, default=Status.DRAFT)
    priority = fields.IntEnumField(Priority, default=Priority.NORMAL)
```

`CharEnumField` stores the string; `IntEnumField` stores the integer. Both
return real enum members, so `post.status is Status.DRAFT` works.

`CharEnumField` sizes the column from the longest member unless you pass
`max_length`. Adding a longer member later is therefore a migration, worth
setting `max_length` up front with room to spare.

**Prefer `CharEnumField`.** A `status` column reading `published` is
self-describing in a database console, a CSV export and a log line;
`priority = 2` is not. Take `IntEnumField` when the values are genuinely
ordinal and you want to compare them with `<`.

Adding a member is not a schema change for either. The constraint is in Python,
not the database. Which is also the caveat: nothing stops another writer
putting an unknown value in the column.

## Server-side defaults

```python
from tortoise.fields import Now, SqlDefault

created_at = fields.DatetimeField(db_default=Now())
count = fields.IntField(db_default=SqlDefault("0"))
```

A `default=` is applied by Python, so a row inserted by anything else (a
migration, another service, a `psql` session) does not get it. `db_default`
puts it in the schema, where it applies to every writer.

## Choosing between the two column-level options

| You want | Use |
| --- | --- |
| A value the application decides | `default=` |
| A value every writer should get | `db_default=` |
| A value derived from other fields | A [model event](/v0.x/orm/events/) |
| A value that must always hold | A [check constraint](/v0.x/orm/meta/#constraints) |

## Custom fields

Subclass and override the two conversion hooks:

```python
class UpperCharField(fields.CharField):
    def to_db_value(self, value, instance, *args, **kwargs):
        return value.upper() if isinstance(value, str) else value

    def to_python_value(self, value, *args, **kwargs):
        return value
```

For a conversion that needs no new column type, [casting](/v0.x/orm/casting/) is
lighter. It is configured per model rather than declared as a type.

## See also

- [Record's own fields](/v0.x/orm/fields/): `PasswordField`, `SlugField`,
  `ULIDField`
- [Relationships](/v0.x/orm/relationships/): the relational field types
- [Meta and indexes](/v0.x/orm/meta/): constraints, indexes, table options
