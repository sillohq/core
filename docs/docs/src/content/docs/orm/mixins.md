---
title: Mixins
description: "The composable model behaviours in sillo.record.mixins — soft deletes, timestamps, ULIDs, serialisation, validation before save, and cascading deletes."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Sillo Record Mixins
  - tag: meta
    attrs:
      property: og:description
      content: SoftDeletesMixin, TimestampsMixin, HasUlidMixin, SerializesToDictMixin, ValidatesBeforeSaveMixin and CascadesDeletesMixin.
---

```python
from sillo.record.mixins import (
    SoftDeletesMixin, TimestampsMixin, HasUlidMixin,
    SerializesToDictMixin, ValidatesBeforeSaveMixin, CascadesDeletesMixin,
)
```

Six behaviours you compose onto a model. Two of them —
soft deletes and serialisation — are already on
[the base model](/orm/models/); the mixins exist so a model inheriting from
Tortoise's `Model` directly can have them, and so the behaviour has a name.

```python
class Invoice(Model, ValidatesBeforeSaveMixin, CascadesDeletesMixin):
    _cascade_deletes = ["line_items"]

    async def validate(self):
        if self.total < 0:
            raise ValueError("total cannot be negative")
```

## `SoftDeletesMixin`

Deleting a row is usually the wrong thing. The posts it authored, the orders it
placed and the audit trail it appears in all still have to resolve to
something.

```python
await invoice.soft_delete()      # sets deleted_at
await invoice.restore()          # clears it
await invoice.force_delete()     # actually deletes the row

Invoice.active()                 # deleted_at IS NULL
Invoice.only_trashed()           # deleted_at IS NOT NULL
Invoice.with_trashed()           # everything

invoice.is_trashed               # bool
```

:::caution[The default queryset includes trashed rows]
`Invoice.all()` and `Invoice.filter(...)` return everything. `active()` is
opt-in, which is the opposite of Django's convention and the mistake to watch
for.

To flip it, add a [global scope](/orm/scopes/#global-scopes):

```python
Invoice.add_global_scope(lambda qs: qs.filter(deleted_at__isnull=True))
```

Then `all()` excludes them and `without_global_scopes()` is how you see
everything.
:::

A soft delete does not cascade, and does not release a unique constraint. A
soft-deleted account still occupies its email address — usually correct, and
worth knowing before someone tries to re-register.

## `TimestampsMixin`

```python
await post.touch()          # updated_at = now, saved
post.set_created_at()       # created_at = now, not saved
```

`touch()` is for recording activity that changed nothing else — a "last seen"
without another column.

The fields themselves are on [the base model](/orm/models/#what-you-get-for-free);
this adds the two methods.

## `HasUlidMixin`

```python
from sillo.record.fields import ULIDField
from sillo.record.mixins import HasUlidMixin


class Event(Model, HasUlidMixin):
    id = ULIDField()
```

Generates a [ULID](https://github.com/ulid/spec) primary key before insert. A
26-character identifier that sorts by creation time as a string, so it is
usable as a clustered key without leaking a row count the way an
auto-increment does.

Needs the `python-ulid` package:

```bash
uv add python-ulid
```

Without it, the mixin raises with that instruction rather than an
`AttributeError` deep in a save.

:::note[Two packages spell it differently]
`ulid-py` and `python-ulid` are different distributions with the same import
name. This mixin expects **`python-ulid`**. Installing the other produces an
`AttributeError` on every insert.
:::

## `SerializesToDictMixin`

```python
post.to_dict(exclude=["body"])
post.to_dict(include=["id", "title"])
post.to_dict(max_depth=1)
post.to_json(indent=2)
```

The same `to_dict`/`to_json` as the base model, plus `max_depth` (default `3`)
for how far into fetched relations to descend.

Depth exists because a serialiser that follows relations without a limit turns
one row into the whole graph, and a cycle turns it into a hang. Cap it at what
the response actually needs.

For anything leaving the process, prefer a
[Pydantic response model](/orm/pydantic/) — see the caution under
[Serialisation](/orm/models/#serialisation).

## `ValidatesBeforeSaveMixin`

```python
class Invoice(Model, ValidatesBeforeSaveMixin):
    async def validate(self):
        if self.total < 0:
            raise ValueError("total cannot be negative")
        if self.due_at and self.due_at < self.issued_at:
            raise ValueError("due date precedes the issue date")
```

`validate()` runs before every `save()`. Raise to stop it.

This is the invariant layer: rules that must hold **however** the row was
written, including from a console command, a migration or a test. Request-shape
validation belongs [in front of the handler](/guides/validation/), where it can
produce a 422 with field-level detail.

It is `async`, so a uniqueness check that has to query is allowed:

```python
async def validate(self):
    if await Invoice.filter(number=self.number).exclude(id=self.id).exists():
        raise ValueError(f"invoice number {self.number} is already used")
```

Although a unique constraint is the reliable version of that — the query above
still races. Use both: the constraint for correctness, the check for a decent
error message.

## `CascadesDeletesMixin`

```python
class Order(Model, CascadesDeletesMixin):
    _cascade_deletes = ["line_items", "shipments"]
```

Deleting an order deletes the related rows named in `_cascade_deletes` first.

Each name is a related-name on this model. They are deleted in the order
listed, then the row itself.

:::note[Prefer the database's own cascade]
`on_delete=fields.CASCADE` on the foreign key is enforced by the database, in
one statement, for every writer — including a migration, a console session, and
another service.

This mixin is application-level: it only applies to a delete that goes through
this model's `delete()`. Reach for it when you need something the database
cannot express, such as deleting rows in a second database or firing
[events](/orm/events/) per child.
:::

Wrap it in a [transaction](/orm/transactions/) — a cascade that fails halfway
has already deleted the children.

```python
async with transaction():
    await order.delete()
```
