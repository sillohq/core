---
title: Models & Mixins
description: Enhanced Tortoise base model with composable mixins — every method, parameter, and integration point explained in production depth.
---

# Models & Mixins

## The Model Base

`sillo.record.Model` extends Tortoise's `Model` class.  It does not fork
or override Tortoise internals — every Tortoise feature (fields, querysets,
relations, aggregation, raw SQL, schema generation) works exactly as
documented at [tortoise.github.io](https://tortoise.github.io/).

What the base class adds:
- Three auto-fields: `created_at`, `updated_at`, `deleted_at`
- Serialization: `to_dict()`, `to_json()`
- Bulk updates: `update_from_dict()`
- Soft-delete: `soft_delete()`, `restore()`, `force_delete()`
- Query shortcuts: `get_or_none()`, `get_or_create()`, `bulk_create()`, `upsert()`, `bulk_upsert()`

### Auto-Fields

Every subclass of Model automatically gets three datetime fields.
You never need to declare them:

| Field | Type | Tortoise Config | Behavior |
|---|---|---|---|
| `created_at` | `DatetimeField` | `auto_now_add=True` | Set to UTC now on INSERT. Never changes. |
| `updated_at` | `DatetimeField` | `auto_now=True` | Set to UTC now on every `.save()`. |
| `deleted_at` | `DatetimeField` | `null=True, default=None` | `None` means active. Non-null means soft-deleted. |

These are implemented as `sillo.record.fields.CreatedAtField`,
`sillo.record.fields.UpdatedAtField`, and `sillo.record.fields.SoftDeleteField` —
thin subclasses of `tortoise.fields.DatetimeField` with appropriate defaults.
The actual timestamp generation is handled by Tortoise's database driver
layer (`asyncpg` for Postgres, `aiomysql` for MySQL, `aiosqlite` for SQLite)
— it is NOT Python-side logic.  This means timestamps are consistent even
if you bypass the ORM and execute raw SQL.

### `to_dict()` — Serialization to Python Dict

Serializes a model instance to a plain `dict`.  Datetime values become
ISO 8601 strings.  Related model instances (ForeignKey, OneToOne) are
recursively serialized via their own `to_dict()` methods.

Parameters:
- `exclude: List[str] | None` — field names to omit.  Use for sensitive
  fields like `password_hash`.
- `include: List[str] | None` — if provided, ONLY these fields are
  returned.  More restrictive than exclude.
- `max_depth: int` (default 3, via SerializesToDictMixin) — how many
  levels of related models to recurse into.  Prevents infinite recursion.

```python
user = await User.get(id=1)
user.to_dict()
# {"id": 1, "email": "a@b.com", "name": "Alice", "created_at": "2025-01-01T00:00:00", "updated_at": "2025-01-01T00:00:00", "deleted_at": null}

# Exclude sensitive fields:
user.to_dict(exclude=["password_hash", "deleted_at"])

# Include only specific fields:
user.to_dict(include=["id", "email", "name"])
```

### `to_json()` — JSON String

Wraps `to_dict()` and calls `json.dumps()` with `default=str` for
unserializable types:

```python
json_str = user.to_json(indent=2)
# {
#   "id": 1,
#   "email": "a@b.com",
#   ...
# }
```

### `update_from_dict()` — Bulk Field Update

Iterates over a dict, calls `setattr` for each key that matches a
model field, then calls `await self.save()`.  Primary integration
point with Pydantic:

```python
from pydantic import BaseModel

class UserUpdate(BaseModel):
    name: str | None = None
    email: str | None = None

@app.patch("/users/{user_id}", request_model=UserUpdate)
async def update_user(request, response, user_id: str):
    user = await User.get_or_none(id=user_id)
    if not user:
        return response.json({"error": "Not found"}, status_code=404)
    await user.update_from_dict(request.validated_data.model_dump(exclude_unset=True))
    return response.json(user.to_dict())
```

Pydantic's `exclude_unset=True` means only fields the client explicitly
sent are included — partial updates work correctly.

### Soft-Delete Methods

```python
await user.soft_delete()    # UPDATE users SET deleted_at = NOW() WHERE id = ?
await user.restore()        # UPDATE users SET deleted_at = NULL WHERE id = ?
await user.force_delete()   # DELETE FROM users WHERE id = ?
user.is_trashed             # True if deleted_at is not None
```

### Query Shortcuts

```python
user = await User.get_or_none(id=42)        # None instead of DoesNotExist
user, created = await User.get_or_create(    # (instance, bool)
    email="a@b.com",
    defaults={"name": "New User"},
)
users = await User.bulk_create([...])       # multi-row INSERT
count = await User.count_active()            # WHERE deleted_at IS NULL
```

### Native Upserts

`upsert()` and `bulk_upsert()` delegate to Tortoise ORM's native conflict
support (`ON CONFLICT` / backend equivalent) instead of doing a read-then-write
loop in Python.

```python
user = await User.upsert(
    {"email": "a@b.com", "name": "Alice"},
    conflict_fields=["email"],
    update_fields=["name"],
)

await User.bulk_upsert(
    [
        {"email": "a@b.com", "name": "Alice"},
        {"email": "c@d.com", "name": "Chris"},
    ],
    conflict_fields=["email"],
    update_fields=["name"],
)
```

`conflict_fields` must identify a unique constraint or primary key supported
by your database. `update_fields` defaults to every non-primary-key field that
is not part of the conflict target.

## Mixins — Composable Behaviors

Mixins are opt-in.  Import the ones you need and compose them into
your model class.  Because Python's MRO is left-to-right, mixins
listed FIRST take precedence.

```python
from sillo.record import (
    Model, SoftDeletesMixin, TimestampsMixin,
    HasUlidMixin, SerializesToDictMixin,
    ValidatesBeforeSaveMixin, CascadesDeletesMixin,
)

class Post(Model, SoftDeletesMixin, SerializesToDictMixin):
    title = fields.CharField(max_length=200)
    body = fields.TextField()
```

### SoftDeletesMixin

Same capability as the Model base's soft-delete, but as an explicit
opt-in.  Methods: `soft_delete()`, `restore()`, `force_delete()`.
Class methods: `active()`, `only_trashed()`, `with_trashed()`.
Property: `is_trashed`.

### TimestampsMixin

Adds `touch()` (set `updated_at` and save) and `set_created_at()`.
Useful when you need programmatic timestamp control outside Tortoise's
auto-population.

### HasUlidMixin

Adds `generate_ulid()` returning a 26-char time-sortable identifier.
[ULID spec](https://github.com/ulid/spec).  Requires `python-ulid`.

### SerializesToDictMixin

Overrides `to_dict()` with configurable `max_depth` to prevent
infinite recursion when serializing deeply nested related models.

### ValidatesBeforeSaveMixin

Overrides `save()` to call `self.validate()` first.  Raise any
exception to prevent the write:

```python
class User(Model, ValidatesBeforeSaveMixin):
    async def validate(self):
        if "@" not in self.email:
            raise ValueError("Invalid email")
```

### CascadesDeletesMixin

Define `_cascade_deletes: List[str]` — when `delete()` is called,
related models are deleted first, in list order.  Wrap in a transaction
for atomicity.

## How Tortoise ORM Handles What sillo Adds

| Feature | Handled By |
|---|---|
| Timestamp auto-population | Tortoise driver layer (asyncpg, aiomysql, aiosqlite) |
| Field validation | Tortoise field validators |
| Relationship management | Tortoise FK/O2O/M2M fields |
| Schema generation | Tortoise `generate_schemas()` |
| Migrations | aerich (Tortoise official) |
| Connection pooling | Tortoise connection pool config |
| Soft-delete flag | sillo record (deleted_at column + query filters) |
| Lifecycle events | sillo record (before/after hooks in Python) |
| Attribute casting | sillo record (encode/decode in Python) |
| to_dict/to_json | sillo record (Python serialization) |
