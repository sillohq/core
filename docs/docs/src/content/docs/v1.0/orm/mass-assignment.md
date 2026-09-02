---
title: Mass Assignment
description: "Applying a dict of updates to a model safely: update_from_dict, fillable and guarded, the resolution order, and why the default is not safe for a request body."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Sillo Record Mass Assignment
  - tag: meta
    attrs:
      property: og:description
      content: update_from_dict, fillable, guarded, and the privilege-escalation they exist to stop.
---

```python
await user.update_from_dict(payload)
```

One call applies a dict of field updates and saves. Keys that do not name a
field are ignored, so a payload with extra keys is not an error.

That convenience is also the classic web vulnerability, so read the next
section before using it on anything a user sent.

## The problem

```python
from sillo import HttpContext, json

@app.patch("/me")
async def update_me(ctx: HttpContext):
    await ctx.user.update_from_dict(await ctx.json())
    return ctx.user.to_dict()
```

Looks fine. Now someone posts:

```json
{ "name": "Ada", "is_staff": true }
```

`is_staff` is a field. It is in the dict. It is written. The account now has
staff access to everything that gates on it.

The same shape reaches `is_superuser`, `email_verified_at`, `balance`,
`organisation_id`. Anything the model happens to have.

## The fix

Two class attributes, both unset by default:

```python
class User(Model):
    fillable = ("name", "bio", "avatar_url")     # a whitelist
```

```python
class User(Model):
    guarded = ("is_staff", "is_superuser", "email_verified_at")   # a blacklist
```

Or restrict a single call:

```python
await user.update_from_dict(payload, only=["name", "bio"])
```

## Resolution order

Most specific instruction wins:

1. **`only=`** on the call, if given.
2. **`fillable`**, if the model set it.
3. **Everything the model has, minus `guarded`.**

Note that `guarded` is consulted **only when `fillable` is unset**. Naming what
is allowed already says what is not, and honouring both would make it unclear
which of two lists a missing field belongs to.

```python
User.mass_assignable_fields()                 # what would be writable
User.mass_assignable_fields(only=["name"])    # for that call
```

Each result is intersected with the model's real fields, so naming something
that is not a field is harmless.

## Which to reach for

**`fillable`.** A whitelist fails closed: a field added next year is not
writable until somebody says it should be.

A blacklist fails open. The field added next year *is* writable, and the person
who added it had no reason to think about this file. `guarded` is the right
choice only when the writable set is genuinely "nearly everything" and the
sensitive columns are few and stable.

```python
class User(Model):
    fillable = ()      # nothing is mass-assignable
```

An empty tuple is meaningful and different from `None`. `None` means "not
stated", which is what makes everything writable.

## Better still: validate first

`update_from_dict` is right for a dict you already trust. The way to trust one
is to validate it:

```python
from pydantic import BaseModel


from sillo import HttpContext

class ProfileUpdate(BaseModel):
    name: str
    bio: str | None = None


@app.patch("/me")
async def update_me(ctx: HttpContext, payload: ProfileUpdate):
    await ctx.user.update_from_dict(payload.model_dump(exclude_unset=True))
    return ctx.user.to_dict()
```

Now the shape is declared once, enforced before the handler runs, and
[documented in OpenAPI](/v1.0/guides/validation/openapi/) for free. `fillable`
becomes a second line of defence rather than the only one, which is where you
want it, because the schema lives next to the endpoint and the model does not.

`exclude_unset=True` is what makes this a genuine PATCH: fields the caller did
not send are not written, rather than being written as their defaults.

## What it does not do

- **No validation.** Values are set as given. A `str` into an `IntField`
  surfaces at the database.
- **It always saves.** There is no "apply but do not persist" mode; set
  attributes directly for that.
- **No relations.** Foreign key *ids* are ordinary fields and work;
  related objects do not.

## See also

- [Models](/v1.0/orm/models/): the base class.
- [Validation](/v1.0/guides/validation/): the layer this should sit behind.
