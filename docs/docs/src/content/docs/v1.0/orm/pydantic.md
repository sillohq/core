---
title: Pydantic Schemas
description: "Generating Pydantic models from Tortoise models: pydantic_model_from_tortoise, its include/exclude/optional options, the type mapping, and when a hand-written schema is better."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Sillo Record Pydantic Schemas
  - tag: meta
    attrs:
      property: og:description
      content: Generating request and response schemas from model fields.
---

```python
from sillo.record.pydantic import pydantic_model_from_tortoise

UserCreate = pydantic_model_from_tortoise(
    User,
    name="UserCreate",
    exclude=["id", "created_at", "updated_at", "deleted_at", "password"],
    optional_fields=["bio"],
)
```

```python
from sillo import HttpContext, json

@app.post("/users", request_model=UserCreate)
async def create_user(ctx: HttpContext):
    user = await User.create(**ctx.validated_data.model_dump())
    return json(user.to_dict(), status_code=201)
```

The generated schema validates the body, produces field-level errors, and
[appears in the OpenAPI document](/v1.0/guides/validation/openapi/).

## Options

| Parameter | Meaning |
| --- | --- |
| `name` | The generated class name. Defaults to `<Model>Schema`. |
| `exclude` | Field names to leave out |
| `include` | If set, **only** these fields |
| `optional_fields` | Fields the caller may omit |

`name` matters more than it looks: it is what appears in the OpenAPI schema
list, so two unnamed schemas from the same model collide as `UserSchema`.

## What becomes optional

A field is optional (typed `Optional[T]`, defaulting to `None`) when any of
these is true:

1. it is named in `optional_fields`;
2. the column is nullable;
3. it is the **primary key**.

The primary key rule is the useful one. A create schema that demanded an `id`
would be asking the caller to invent a row identifier the database is about to
supply.

The annotation and the default follow from that single answer, so they cannot
disagree. Deciding them separately is how a field ends up typed `Optional` but
still required, satisfiable only by passing `None` explicitly, which is
nobody's intent.

## The type mapping

| Tortoise field | Python type |
| --- | --- |
| `IntField`, `SmallIntField`, `BigIntField` | `int` |
| `FloatField`, `DecimalField` | `float` |
| `BooleanField` | `bool` |
| `CharField`, `TextField` | `str` |
| `DatetimeField`, `DateField` | `str` |
| `TimeDeltaField` | `float` |
| `JSONField` | `dict` |
| anything else | `str` |

Three of those are worth pausing on.

**Dates and datetimes become `str`.** No parsing, no format validation, any
string is accepted, and you get a string in `validated_data`. Parse it
yourself, or declare the field in a hand-written schema as `datetime` and let
Pydantic do it properly.

**`DecimalField` becomes `float`.** For money, that is the wrong type: it
introduces binary rounding into a value you chose `Decimal` to keep exact.
Declare those by hand as `condecimal(...)`.

**Unknown fields fall back to `str`.** Including relations and every custom
field type. The fallback means generation never fails, at the cost of a wrong
type where the mapping has no entry, so read what you generated for any model
with unusual fields.

## Relations are not handled

Foreign key *columns* appear if the field map exposes them; related objects and
reverse relations do not become nested schemas.

For a nested response, write the schema:

```python
from pydantic import BaseModel


class AuthorOut(BaseModel):
    id: int
    username: str


class PostOut(BaseModel):
    id: int
    title: str
    author: AuthorOut
```

## Generated versus hand-written

Generate when the schema really is "the model, minus a few fields": an admin
create form, an internal endpoint, a prototype. It stays in step with the model
for free.

Write it by hand when the schema is a **contract**. A public API's request
shape should not change because somebody added a column, and that is exactly
what a generated schema does. Constraints (`min_length`, `ge`, a regex), real
`datetime` and `Decimal` types, nested objects and examples all need the
explicit form anyway.

The rule of thumb: generated schemas are convenient *inputs*; response schemas
that leave your system are worth writing out.

## Excluding secrets

```python
exclude=["password", "password_hash", "api_key"]
```

A generated schema includes every field it can see. On a *response* model that
is how a hashed password ends up in a JSON body.

Prefer `include` for responses. A whitelist means a column added next year is
not published by default:

```python
UserOut = pydantic_model_from_tortoise(User, name="UserOut",
                                       include=["id", "username", "created_at"])
```

Same reasoning as [`fillable` over `guarded`](/v1.0/orm/mass-assignment/#which-to-reach-for).

## See also

- [Validation](/v1.0/guides/validation/): how request models are used.
- [Response models](/v1.0/guides/validation/response-models/).
- [Exception handlers](/v1.0/orm/exceptions/): turning database errors into
  responses.
