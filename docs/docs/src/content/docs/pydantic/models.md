---
title: Models
description: "BaseModel in Pydantic v2: declaring, constructing, validating, mutating and comparing models, plus what changed from v1 and why it matters."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Pydantic Models in Sillo
  - tag: meta
    attrs:
      property: og:description
      content: BaseModel, construction, validation, and the v1 to v2 changes.
---

```python
from pydantic import BaseModel


class PostCreate(BaseModel):
    title: str
    body: str
    published: bool = False
```

A class attribute with a type annotation is a field. An annotation with no
value is **required**; one with a value is optional with that default.

## Constructing

```python
post = PostCreate(title="Hello", body="…")
post = PostCreate(title="Hello", body="…", published=True)
```

Validation happens in the constructor. There is no separate `.validate()` call
and no way to hold an invalid model. If the object exists, it passed.

```python
PostCreate(title="Hello")
# ValidationError: 1 validation error for PostCreate
# body
#   Field required [type=missing, input_value={'title': 'Hello'}, input_type=dict]
```

### From a dict or JSON

```python
PostCreate.model_validate({"title": "Hello", "body": "…"})
PostCreate.model_validate_json('{"title": "Hello", "body": "…"}')
```

`model_validate_json` parses and validates in one pass, which is faster than
`json.loads` followed by `model_validate` and gives better error positions.

This is what Sillo calls for a [request body](/pydantic/request-models/).

### Skipping validation

```python
post = PostCreate.model_construct(title="Hello", body="…")
```

Builds the object without validating. Fast, and unsafe. It will happily hold
data that does not match its own annotations.

Only for data you have *already* validated, in a hot path where the second pass
is measurable. Reaching for it to work around a validation failure is how an
invalid model ends up three layers deeper.

## Accessing

```python
post.title
post.model_fields_set        # which fields were explicitly provided
```

`model_fields_set` is the one worth remembering. It distinguishes "the client
sent `published=False`" from "the client did not mention `published`", which is
exactly what a PATCH endpoint needs:

```python
await post.update_from_dict(payload.model_dump(exclude_unset=True))
```

Without it, an unmentioned field is written as its default, and a partial
update silently resets everything the caller left out.

## Mutating

Models are mutable by default, and assignment is **not** validated unless you
ask:

```python
post.title = 123      # allowed by default
```

```python
from pydantic import ConfigDict


class PostCreate(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    title: str


post.title = 123      # now raises
```

Or make them immutable, which is usually better for a request model. Nothing
downstream should be editing what the client sent:

```python
model_config = ConfigDict(frozen=True)
```

`frozen=True` also makes the model hashable, so it can be a dict key or go in a
set.

### Copying

```python
updated = post.model_copy(update={"title": "New title"})
deep = post.model_copy(deep=True)
```

`model_copy` does **not** validate the update. For a validated change, go
through the constructor:

```python
updated = PostCreate(**post.model_dump(), title="New title")
```

## Comparing

```python
PostCreate(title="a", body="b") == PostCreate(title="a", body="b")   # True
```

Field-by-field equality, and models of different classes are never equal even
with identical fields. Useful in tests, assert on a whole model rather than
field by field.

## Inheritance

```python
class PostBase(BaseModel):
    title: str
    body: str


class PostCreate(PostBase):
    published: bool = False


class PostUpdate(PostBase):
    title: str | None = None
    body: str | None = None
```

Fields are inherited; a subclass can add, and can override an annotation to
widen or narrow it.

This is the standard shape for an API: a base with the shared fields, a
`Create` that requires them, an `Update` that makes them optional, and an `Out`
for the response. See [Patterns](/pydantic/patterns/).

`model_config` is inherited and merged, so a base can set the policy for a
family of models.

## Generic models

```python
from typing import Generic, TypeVar

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
```

```python
Page[PostOut](items=[...], total=130, page=1)
```

Each parameterisation validates its own item type, and each gets its own
OpenAPI schema (`PagePostOut`, `PageUserOut`) so a paginated envelope is
declared once and documented correctly everywhere.

## Field order

Fields are validated in declaration order, which matters when a
[model validator](/pydantic/validators/) or a defaulted field depends on an
earlier one. Declare the things others rely on first.

## v1 to v2

Sillo uses Pydantic v2. Snippets written for v1 look almost identical and
behave differently, so it is worth knowing the renames:

| v1 | v2 |
| --- | --- |
| `.dict()` | `.model_dump()` |
| `.json()` | `.model_dump_json()` |
| `.parse_obj()` | `.model_validate()` |
| `.parse_raw()` | `.model_validate_json()` |
| `.copy()` | `.model_copy()` |
| `.construct()` | `.model_construct()` |
| `.schema()` | `.model_json_schema()` |
| `class Config:` | `model_config = ConfigDict(...)` |
| `@validator` | `@field_validator` |
| `@root_validator` | `@model_validator` |
| `__fields_set__` | `model_fields_set` |
| `allow_mutation = False` | `frozen=True` |
| `orm_mode = True` | `from_attributes=True` |
| `regex=` | `pattern=` |
| `const=` | `Literal[...]` |
| `min_items` / `max_items` | `min_length` / `max_length` |

Three behavioural changes catch people out:

**Optional no longer implies a default.** In v1, `x: int | None` was optional
and defaulted to `None`. In v2 it is **required** and merely allows `None`. To
make it optional, give it one:

```python
x: int | None = None
```

**Coercion is stricter.** v2 will not turn `"abc"` into a float or accept an
arbitrary object where a `str` is annotated. See
[Types](/pydantic/types/#coercion).

**`@validator` ran after the field's own validation; `@field_validator`
defaults to the same, but the `pre=True` flag is now `mode="before"`.** See
[Validators](/pydantic/validators/).

## Introspection

```python
PostCreate.model_fields               # name -> FieldInfo
PostCreate.model_json_schema()        # JSON Schema
```

`model_json_schema()` is what [OpenAPI generation](/pydantic/openapi/) is built
on, the schema in your API documentation is this dict, embedded.
