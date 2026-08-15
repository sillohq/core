---
title: Model Configuration
description: "model_config and ConfigDict — every option worth knowing, what each one changes, and the settings a Sillo request or response model usually wants."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Pydantic Model Configuration in Sillo
  - tag: meta
    attrs:
      property: og:description
      content: ConfigDict options, and sensible defaults for request and response models.
---

```python
from pydantic import BaseModel, ConfigDict


class PostCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        frozen=True,
    )

    title: str
    body: str
```

`model_config` replaces v1's `class Config`. It is inherited and merged, so a
base class can set policy for a whole family of models.

## Extra fields

```python
extra="ignore"    # default — drop unknown keys
extra="forbid"    # reject them
extra="allow"     # keep them as attributes
```

The default silently discards anything you did not declare. That is forgiving,
and it hides typos: a client sending `publish` instead of `published` gets a
`200` and no effect.

**`extra="forbid"` on request models** turns that into a clear error:

```json
{"loc": ["body", "publish"], "msg": "Extra inputs are not permitted"}
```

The trade-off is compatibility — a client sending a field your newer version
removed now fails. For an internal API, forbid. For a public one consumed by
clients you do not control, `ignore` is the kinder default.

`extra="allow"` keeps unknown keys as attributes. Occasionally right for a
passthrough payload; usually a sign the shape has not been decided.

## Strings

```python
str_strip_whitespace=True
str_to_lower=True
str_to_upper=True
str_min_length=1
str_max_length=1000
```

Applied to every `str` field in the model.

`str_strip_whitespace=True` is worth setting on almost every request model.
A title of `"  "` passes a bare `str` annotation and is not a title;
stripping first means `min_length=1` catches it.

## Validation behaviour

```python
strict=True                 # no type coercion anywhere
validate_assignment=True    # validate on attribute assignment
validate_default=True       # validate defaults too
revalidate_instances="always"
```

`strict=True` is right for a JSON body, where the client controls the types.
It is wrong for anything derived from a URL or a form, which is strings by
definition — see [Types](/pydantic/types/#strict-mode).

`validate_assignment=True` closes the gap where a model is valid at
construction and invalid a line later:

```python
post.title = 123      # raises, with this on
```

`validate_default=True` catches a default that does not satisfy its own
constraints — a mistake that otherwise only surfaces when someone omits the
field.

## Immutability

```python
frozen=True
```

No assignment after construction, and the model becomes hashable.

A good default for **request** models: nothing downstream should be editing
what the client sent, and a frozen model makes that structural rather than a
convention.

## Aliases

```python
from pydantic.alias_generators import to_camel

model_config = ConfigDict(
    alias_generator=to_camel,
    populate_by_name=True,
    serialize_by_alias=True,
)
```

Every field becomes `camelCase` on the wire and stays `snake_case` in Python.
`populate_by_name=True` accepts either spelling on input;
`serialize_by_alias=True` emits the alias without needing `by_alias=True` at
each call site.

This is the tidy way to serve a JavaScript client without writing Python that
looks like JavaScript. See [Fields](/pydantic/fields/#aliases).

## From attributes

```python
from_attributes=True
```

Lets `model_validate()` read attributes instead of dict keys — which is what
makes an ORM instance validate directly:

```python
PostOut.model_validate(post)
```

v1 called this `orm_mode`. Set it on every output model that is built from a
[Record model](/orm/models/), and remember to
[fetch the relations first](/pydantic/nested/#building-from-orm-objects).

## Schema metadata

```python
model_config = ConfigDict(
    title="Create a post",
    json_schema_extra={
        "examples": [{"title": "Async Python", "body": "…"}],
    },
)
```

Both flow into the [OpenAPI document](/pydantic/openapi/). A worked example at
the model level is the single most useful thing you can add to an API
reference — more useful than per-field descriptions, because it shows a whole
valid request.

## Arbitrary types

```python
arbitrary_types_allowed=True
```

Permits a field annotated with a class Pydantic knows nothing about. It is then
validated only by `isinstance`, and has no JSON schema — so a model using it
cannot be a request or response model.

Fine for an internal model that never crosses the wire; a dead end for anything
in your API.

## Populating and protecting names

```python
protected_namespaces=("model_",)     # the default
```

Pydantic warns when a field name collides with its own `model_*` methods. If
your domain genuinely has a `model_number`, widen it:

```python
model_config = ConfigDict(protected_namespaces=())
```

## Defaults worth adopting

For a **request** model:

```python
model_config = ConfigDict(
    extra="forbid",
    str_strip_whitespace=True,
    frozen=True,
    validate_default=True,
)
```

Reject typos, normalise whitespace, prevent downstream mutation, and catch a
bad default at import time rather than at request time.

For a **response** model built from the ORM:

```python
model_config = ConfigDict(
    from_attributes=True,
    validate_assignment=True,
)
```

Set them once on a base and inherit:

```python
class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)


class PostCreate(RequestModel):
    title: str
    body: str
```

Which also gives you one place to change the policy when you decide `forbid`
was too strict.

## Reading it back

```python
PostCreate.model_config
```

A plain dict, merged across the inheritance chain — useful when a base class
several levels up is setting something surprising.
