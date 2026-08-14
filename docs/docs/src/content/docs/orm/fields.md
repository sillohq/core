---
title: Fields
description: "The field types sillo.record adds on top of Tortoise — PasswordField, the timestamp fields, SlugField and ULIDField — and exactly what each does and does not do."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Sillo Record Fields
  - tag: meta
    attrs:
      property: og:description
      content: PasswordField, CreatedAtField, UpdatedAtField, SoftDeleteField, SlugField and ULIDField.
---

Every [Tortoise field type](https://tortoise.github.io/fields.html) works —
`IntField`, `CharField`, `TextField`, `JSONField`, `ForeignKeyField` and the
rest. Record adds six.

```python
from sillo.record.fields import (
    PasswordField, CreatedAtField, UpdatedAtField,
    SoftDeleteField, SlugField, ULIDField,
)
```

## `PasswordField`

```python
from sillo.record import Model
from sillo.record.fields import PasswordField


class Account(Model):
    email = fields.CharField(max_length=255, unique=True)
    password = PasswordField()
```

A `CharField` that hashes on the way into the database:

```python
account.password = "correct horse battery staple"
await account.save()
# stored: $2b$12$…
```

Assigning plaintext through the ORM stores a hash. There is no separate step to
forget, which is the point.

Verify with the helper, never by comparison:

```python
from sillo.helpers.hashing import verify_password

if verify_password(submitted, account.password):
    ...
```

The [admin panel](/orm/admin/) detects `PasswordField` and renders a password
widget — reveal toggle, strength meter, confirmation — rather than a text
input.

### Two things to know

**It hashes with bcrypt.** `hash_password` defaults to bcrypt, and this field
uses the default. Install the extra:

```bash
uv add "sillo-framework[hashing-bcrypt]"
```

**Its "already hashed" check is bcrypt-specific.** A value starting `$2b$`,
`$2a$` or `$2y$` is passed through untouched; anything else is hashed. So a
hash produced by another scheme — argon2, scrypt — assigned to this field would
be hashed *again*, as if it were a plaintext password, and would never verify.

If your project standardises on argon2, do not mix it with this field. Hash
explicitly and store in a plain `CharField`, so there is one place deciding the
scheme:

```python
from sillo.helpers.hashing import hash_password

class Account(Model):
    password = fields.CharField(max_length=255)

account.password = hash_password(plaintext, scheme="argon2")
```

## The timestamp fields

Declared on [the base model](/orm/models/), so you rarely write them yourself.

| Field | Wraps | Behaviour |
| --- | --- | --- |
| `CreatedAtField` | `DatetimeField(auto_now_add=True)` | Set on insert, never updated |
| `UpdatedAtField` | `DatetimeField(auto_now=True)` | Set on every save |
| `SoftDeleteField` | `DatetimeField(null=True, default=None)` | `None` means active |

They are thin: each sets one Tortoise default and adds nothing else. The value
is that the intent is in the name — `deleted_at = SoftDeleteField()` says what
a nullable datetime is for.

Use them directly when a model needs a second one:

```python
class Invoice(Model):
    approved_at = SoftDeleteField()   # nullable datetime, defaults to None
```

## `ULIDField`

```python
from sillo.record.fields import ULIDField
from sillo.record.mixins import HasUlidMixin


class Event(Model, HasUlidMixin):
    id = ULIDField()
```

A 26-character `CharField`, primary key by default. A
[ULID](https://github.com/ulid/spec) sorts by creation time as a string, which
gives you a sortable identifier that does not leak a row count the way an
auto-increment integer does.

:::caution[The field does not generate the value]
`ULIDField` declares the column. Generating the identifier is
[`HasUlidMixin`](/orm/mixins/#hasulidmixin), which needs the `python-ulid`
package:

```bash
uv add python-ulid
```

Use the field without the mixin and you must set `id` yourself; every insert
that does not will fail on a null primary key.
:::

## `SlugField`

```python
class Post(Model):
    slug = SlugField(max_length=200)
```

A `CharField` sized for a slug, with the intent in the name.

:::caution[`source_field` does nothing]
The constructor accepts `source_field=` and stores it, but nothing in the
framework reads it. There is no automatic slug generation.

```python
slug = SlugField(source_field="title")   # has no effect
```

Generate the slug yourself — a [model event](/orm/events/) is the tidy place,
because it applies however the row was created:

```python
from sillo.helpers.strings import slugify


class Post(Model, HasEvents):
    title = fields.CharField(max_length=200)
    slug = SlugField()


@Post.on("before_create")
async def fill_slug(post):
    if not post.slug:
        post.slug = slugify(post.title)
```

Add `unique=True` and decide what happens on a collision — usually a numeric
suffix.
:::

## Writing your own

Subclass a Tortoise field and override the two conversion hooks:

```python
from tortoise import fields


class UpperCharField(fields.CharField):
    def to_db_value(self, value, instance, *args, **kwargs):
        return value.upper() if isinstance(value, str) else value

    def to_python_value(self, value, *args, **kwargs):
        return value
```

For converting values without a custom column type,
[casting](/orm/casting/) is usually the lighter answer — it is configured per
model rather than declared as a type.
