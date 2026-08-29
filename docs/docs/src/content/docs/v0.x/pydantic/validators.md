---
title: Validators
description: "Custom validation in Pydantic v2: field validators and their modes, model validators, reusable Annotated validators, and serialisation validators."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Pydantic Validators in Sillo
  - tag: meta
    attrs:
      property: og:description
      content: field_validator, model_validator, modes, and reusable Annotated validators.
---

[`Field()` constraints](/v0.x/pydantic/fields/) cover bounds, lengths and patterns.
Validators cover everything else: normalisation, cross-field rules, and checks
that need code.

## `field_validator`

```python
from pydantic import BaseModel, field_validator


class PostCreate(BaseModel):
    title: str
    slug: str

    @field_validator("slug")
    @classmethod
    def slug_is_url_safe(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z0-9-]+", value):
            raise ValueError("must be lowercase letters, digits and hyphens")
        return value
```

Three rules:

- **Return the value.** A validator that returns `None` sets the field to
  `None`. This is the most common mistake.
- **Raise `ValueError`** (or `AssertionError`) to fail. Pydantic wraps it into
  a `ValidationError` with the field's location attached.
- **Decorate with `@classmethod`**, under `@field_validator`. That order
  matters.

### Several fields at once

```python
@field_validator("title", "summary")
@classmethod
def not_blank(cls, value: str) -> str:
    if not value.strip():
        raise ValueError("cannot be blank")
    return value.strip()
```

```python
@field_validator("*")
@classmethod
def strip_strings(cls, value):
    return value.strip() if isinstance(value, str) else value
```

`"*"` applies to every field, which is how you normalise across a whole model.

### Modes

```python
@field_validator("tags", mode="before")
```

| Mode | Runs | Receives |
| --- | --- | --- |
| `"after"` *(default)* | After Pydantic's own validation | The parsed, correctly typed value |
| `"before"` | Before it | The raw input, of any type |
| `"wrap"` | Around it | The value and a handler to call |

**`after`** is what you want almost always. The value is already the right
type, so the validator only expresses your rule.

**`before`** is for reshaping input that would otherwise fail:

```python
@field_validator("tags", mode="before")
@classmethod
def split_tags(cls, value):
    if isinstance(value, str):
        return [t.strip() for t in value.split(",") if t.strip()]
    return value
```

Now `"python, async"` and `["python", "async"]` both validate as a `list[str]`.
Note the `isinstance` guard. A `before` validator receives whatever arrived,
including types you did not anticipate.

**`wrap`** lets you catch and substitute:

```python
from pydantic import ValidatorFunctionWrapHandler


@field_validator("published_at", mode="wrap")
@classmethod
def default_on_bad_date(cls, value, handler: ValidatorFunctionWrapHandler):
    try:
        return handler(value)
    except ValueError:
        return None
```

Rare, and worth a comment when you use it, silently accepting invalid input is
usually the wrong call for an API.

### Seeing other fields

```python
from pydantic import ValidationInfo


class Booking(BaseModel):
    start: datetime
    end: datetime

    @field_validator("end")
    @classmethod
    def after_start(cls, value: datetime, info: ValidationInfo) -> datetime:
        start = info.data.get("start")
        if start and value <= start:
            raise ValueError("must be after start")
        return value
```

`info.data` holds the fields validated **so far**, which means declaration
order matters, and a field cannot see one declared after it.

When a rule involves two fields, a [model validator](#model_validator) is
usually clearer, because it does not depend on ordering.

## `model_validator`

```python
from pydantic import model_validator


class Booking(BaseModel):
    start: datetime
    end: datetime
    attendees: int

    @model_validator(mode="after")
    def check_window(self):
        if self.end <= self.start:
            raise ValueError("end must be after start")
        return self
```

`mode="after"` runs once every field has validated, receives the **instance**,
and must return it (or another instance).

Use it for anything spanning fields: a date range, a discount that cannot
exceed a total, exactly one of two optional fields being present.

### `mode="before"`

```python
@model_validator(mode="before")
@classmethod
def unwrap_envelope(cls, data):
    if isinstance(data, dict) and "data" in data:
        return data["data"]
    return data
```

Receives the raw input (usually a dict) before any field is looked at. For
reshaping a payload whose structure differs from your model: unwrapping an
envelope, renaming a legacy key, flattening a nested object.

Guard the type. A `before` model validator can receive something that is not a
dict.

### Errors from a model validator

An error raised in a model validator has no field location, so it appears
against the model as a whole:

```json
{"loc": ["body"], "msg": "Value error, end must be after start"}
```

To attach it to a specific field, raise a `PydanticCustomError` or restructure
as a field validator. For most cases the model-level message is fine, the
message names the fields.

## Reusable `Annotated` validators

```python
from typing import Annotated
from pydantic import AfterValidator, BeforeValidator


def must_be_slug(value: str) -> str:
    if not re.fullmatch(r"[a-z0-9-]+", value):
        raise ValueError("must be lowercase letters, digits and hyphens")
    return value


Slug = Annotated[str, AfterValidator(must_be_slug)]


class PostCreate(BaseModel):
    slug: Slug


class CategoryCreate(BaseModel):
    slug: Slug
```

The rule is written once and applied by annotation. This is the better shape
whenever a rule belongs to a *type* rather than to one model, and it composes
with [`Field()`](/v0.x/pydantic/fields/):

```python
Slug = Annotated[str, Field(max_length=200), AfterValidator(must_be_slug)]
```

Validators run in the order they appear.

`BeforeValidator` and `WrapValidator` are the equivalents of the other two
modes.

## Serialisation validators

Running on the way **out** rather than in:

```python
from pydantic import field_serializer, model_serializer


class PostOut(BaseModel):
    id: int
    published_at: datetime | None

    @field_serializer("published_at")
    def serialize_published_at(self, value: datetime | None) -> str | None:
        return value.isoformat() if value else None
```

Covered in [Serialisation](/v0.x/pydantic/serialization/).

## Where validation belongs

A validator can do anything, including query a database. It usually should not.

```python
@field_validator("email")
@classmethod
async def unique(cls, value):        # not supported — validators are sync
    ...
```

Pydantic validators are **synchronous**. There is no async validator, so a
uniqueness check cannot happen here at all.

That constraint is a useful one. It pushes the layers apart:

| Rule | Where |
| --- | --- |
| Shape, type, range, format | A Pydantic validator |
| "This email is already registered" | The handler, or a unique constraint |
| An invariant of the row | [`ValidatesBeforeSaveMixin`](/v0.x/orm/mixins/#validatesbeforesavemixin) |
| What must hold for every writer | A [database constraint](/v0.x/orm/meta/#constraints) |

A uniqueness check in a validator would also race: between the check and the
insert, another request can take the value. The reliable version is a unique
constraint plus a caught `IntegrityError`, which the [exception
handlers](/v0.x/orm/exceptions/) already turn into a 409.

## Error messages

The message you raise is what the client sees:

```python
raise ValueError("must be lowercase letters, digits and hyphens")
```

```json
{
  "loc": ["body", "slug"],
  "msg": "Value error, must be lowercase letters, digits and hyphens",
  "type": "value_error"
}
```

Write it for whoever has to fix the request. "invalid" tells them nothing;
naming the rule tells them what to send. See
[Validation errors](/v0.x/pydantic/errors/).
