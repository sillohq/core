---
title: Fields
description: "Field in full: defaults and factories, numeric and string constraints, aliases, documentation metadata, exclusion, and how each one reaches your OpenAPI schema."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Pydantic Field() in Sillo
  - tag: meta
    attrs:
      property: og:description
      content: Defaults, constraints, aliases, metadata and exclusion.
---

```python
from pydantic import BaseModel, Field


class PostCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    views: int = Field(default=0, ge=0)
    tags: list[str] = Field(default_factory=list, max_length=10)
```

`Field()` attaches constraints and metadata to an annotation. Everything it
takes ends up in two places: the validator, and your
[OpenAPI schema](/v0.x/pydantic/openapi/).

## Defaults

```python
title: str                                   # required
published: bool = False                      # optional
views: int = Field(default=0)                # the same
tags: list[str] = Field(default_factory=list)
created: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

Use `default_factory` when the default must be computed per instance: a
timestamp, a UUID, a fresh container.

`Field(...)` with a literal ellipsis means required, and is the way to make a
field required while still attaching constraints:

```python
title: str = Field(..., min_length=1)
```

Though in v2 you can simply omit the default, which reads better:

```python
title: str = Field(min_length=1)
```

## Numeric constraints

| Argument | Meaning |
| --- | --- |
| `gt` | Greater than |
| `ge` | Greater than or equal |
| `lt` | Less than |
| `le` | Less than or equal |
| `multiple_of` | Divisible by |
| `allow_inf_nan` | Permit `inf` and `nan` on floats |

```python
age: int = Field(ge=0, le=150)
price: Decimal = Field(gt=0, decimal_places=2, max_digits=10)
quantity: int = Field(gt=0, multiple_of=5)
rating: float = Field(ge=0, le=5, allow_inf_nan=False)
```

`allow_inf_nan=False` is worth setting on any float that reaches a database.
`float("nan")` is valid JSON in some encoders and will happily be stored, where
it compares equal to nothing including itself.

## String constraints

| Argument | Meaning |
| --- | --- |
| `min_length`, `max_length` | Bounds |
| `pattern` | A regular expression the value must match |
| `strip_whitespace` | Trim before validating |
| `to_lower`, `to_upper` | Case-fold before validating |

```python
title: str = Field(min_length=1, max_length=200)
slug: str = Field(pattern=r"^[a-z0-9-]+$", max_length=200)
email: str = Field(to_lower=True, strip_whitespace=True)
```

`min_length=1` is the one most models are missing. Without it, `""` passes a
`str` annotation, and an empty title is almost never what the endpoint means by
"a title".

`pattern` is a full match, not a search, so no anchors are needed.

The transforms happen **before** validation, so `to_lower=True` with
`pattern=r"^[a-z]+$"` accepts `"ABC"` and stores `"abc"`. That ordering is
usually what you want for normalising user input.

## Collection constraints

```python
tags: list[str] = Field(min_length=1, max_length=10)
```

`min_length` and `max_length` apply to the number of items. These replace v1's
`min_items` and `max_items`.

Set an upper bound on any list a client controls. Without one, a request can
contain a hundred thousand tags and your handler will loyally try to insert
them.

## Aliases

When the wire name differs from the Python name:

```python
class Webhook(BaseModel):
    event_type: str = Field(alias="eventType")
    created_at: datetime = Field(alias="createdAt")
```

```python
Webhook.model_validate({"eventType": "post.created", "createdAt": "..."})
```

By default the alias is what is **accepted** and the field name is what is
**emitted**. To control each direction:

```python
event_type: str = Field(
    validation_alias="eventType",     # what comes in
    serialization_alias="event_type", # what goes out
)
```

To accept both spellings:

```python
model_config = ConfigDict(populate_by_name=True)
```

Then either `eventType` or `event_type` validates, useful while a client is
migrating.

For a whole model, generate them:

```python
from pydantic.alias_generators import to_camel


class Base(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
```

Every field is now `camelCase` on the wire and `snake_case` in Python, with no
per-field annotation. This is the tidy way to serve a JavaScript client without
writing Python that looks like JavaScript.

## Documentation metadata

```python
title: str = Field(
    description="The post's headline, shown in listings.",
    examples=["Async Python in practice"],
    title="Post title",
)
```

These do not affect validation at all. They go straight into the [OpenAPI
schema](/v0.x/pydantic/openapi/), which is what an API reference and a generated
client read.

`examples` is worth filling in for anything whose format is not obvious.
Someone reading your API docs learns more from one real value than from
`"string"`.

```python
deprecated: bool = Field(deprecated=True)
```

Marks the field deprecated in the schema, so clients see it before it goes.

## Exclusion

```python
class UserOut(BaseModel):
    id: int
    email: str
    internal_notes: str = Field(exclude=True)
```

`exclude=True` keeps the field out of every `model_dump()`. For a value the
model needs internally but which must never leave.

Prefer a separate output model where you can. See
[Patterns](/v0.x/pydantic/patterns/). A field that is excluded is still a field
somebody can un-exclude by adding an argument at a call site.

## `Annotated` instead

Everything above can be attached with `Annotated`, which makes the constrained
type reusable:

```python
from typing import Annotated

Title = Annotated[str, Field(min_length=1, max_length=200)]


class PostCreate(BaseModel):
    title: Title


class PostUpdate(BaseModel):
    title: Title | None = None
```

The constraint is declared once. In the `Field()` form it would be repeated in
both models, and would eventually disagree.

`Annotated` is also the only way to attach a constraint to an item inside a
collection:

```python
tags: list[Annotated[str, Field(min_length=1, max_length=30)]]
```

## Frozen fields

```python
id: int = Field(frozen=True)
```

Assignment to that field raises after construction, while the rest of the model
stays mutable. For an identifier that should never change under an object
someone else holds.

## What ends up in OpenAPI

| `Field()` argument | Schema keyword |
| --- | --- |
| `default` | `default` |
| `description` | `description` |
| `title` | `title` |
| `examples` | `examples` |
| `gt`, `ge`, `lt`, `le` | `exclusiveMinimum`, `minimum`, … |
| `min_length`, `max_length` | `minLength`/`maxLength`, or `minItems`/`maxItems` |
| `pattern` | `pattern` |
| `deprecated` | `deprecated` |
| `exclude` | *(omitted from the schema)* |

Which is the real argument for putting constraints on fields rather than
checking them in the handler: the check and the published contract come from
the same declaration and cannot drift apart.
