---
title: Pydantic in Sillo
description: "Pydantic is the validation engine underneath every Sillo route. What it does, where it appears, and a map of this section."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Pydantic in Sillo
  - tag: meta
    attrs:
      property: og:description
      content: The validation engine underneath every Sillo route, documented end to end.
---

Pydantic is not an optional add-on in Sillo. It is the engine underneath every
request that gets validated, every response model, every query parameter with a
type, and the OpenAPI document generated from all of them.

```python
from pydantic import BaseModel, Field


from sillo import HttpContext, json

class PostCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str
    tags: list[str] = []


@app.post("/posts", request_model=PostCreate)
async def create_post(ctx: HttpContext, payload):
    post = await Post.create(**payload.model_dump())
    return json(post.to_dict(), status_code=201)
```

That declaration does four things at once: it parses the body, coerces the
types, rejects bad input with a 422 naming each failure, and puts the shape in
your OpenAPI schema. One statement, and the published contract cannot drift
from the runtime behaviour because they are generated from the same object.

## Why it is worth learning properly

Most Sillo applications spend more time in Pydantic than they expect. The
validation layer is where a surprising amount of correctness lives: a
`min_length` on a slug, a `Decimal` instead of a `float` on money, a validator
that normalises an email before it reaches the database.

This section covers Pydantic itself in enough depth that you should not need to
leave for its own documentation, and covers it **as Sillo uses it**, so the
examples are handlers and models rather than standalone scripts.

Sillo uses **Pydantic v2**. The v1 API (`@validator`, `.dict()`,
`class Config`) is deprecated and behaves differently; if you find a snippet
online using it, [the migration notes](/v1.0/pydantic/models/#v1-to-v2) say what
changed.

## Where Pydantic shows up

| In Sillo | Page |
| --- | --- |
| `request_model=` on a route | [Request models](/v1.0/pydantic/request-models/) |
| `response_model=` on a route | [Response models](/v1.0/pydantic/response-models/) |
| `Query`, `Path`, `Header`, `Cookie`, `Form`, `File` | [Parameters](/v1.0/pydantic/parameters/) |
| The generated OpenAPI document | [OpenAPI](/v1.0/pydantic/openapi/) |
| Schemas generated from ORM models | [The ORM bridge](/v1.0/pydantic/orm-bridge/) |
| The 422 body a client receives | [Validation errors](/v1.0/pydantic/errors/) |

## The section

### Pydantic itself

- [Models](/v1.0/pydantic/models/): `BaseModel`, construction, the v1 to v2 changes
- [Types](/v1.0/pydantic/types/): what Pydantic understands, and coercion rules
- [Fields](/v1.0/pydantic/fields/): `Field()`, defaults, constraints, aliases
- [Validators](/v1.0/pydantic/validators/): field and model validators, modes
- [Nested models](/v1.0/pydantic/nested/): composition, unions, recursion
- [Serialisation](/v1.0/pydantic/serialization/): `model_dump`, computed fields
- [Configuration](/v1.0/pydantic/config/): `model_config` and what each option does
- [Validation errors](/v1.0/pydantic/errors/): the error structure, and messages

### In a Sillo application

- [Request models](/v1.0/pydantic/request-models/): validating a body
- [Parameters](/v1.0/pydantic/parameters/): the markers, and their constraints
- [Response models](/v1.0/pydantic/response-models/): shaping what goes out
- [OpenAPI](/v1.0/pydantic/openapi/): how schemas become documentation
- [The ORM bridge](/v1.0/pydantic/orm-bridge/): models from models
- [Patterns](/v1.0/pydantic/patterns/): the shapes that come up repeatedly

## A note on where validation belongs

Sillo has three layers that can reject bad data, and they are not
interchangeable:

| Layer | Catches | Produces |
| --- | --- | --- |
| **Pydantic**, before the handler | Wrong shape, wrong type, out of range | `422` with field-level detail |
| **[Model validation](/v1.0/orm/mixins/#validatesbeforesavemixin)** | Invariants, however the row was written | An exception |
| **[Database constraints](/v1.0/orm/meta/#constraints)** | What must be true for every writer | An `IntegrityError` |

Pydantic is the outermost and the only one that can produce a decent error
message for a client: it knows which field, in which location, and why. Use it
for everything about the *request*.

Use the layers underneath for what must hold regardless of who wrote the row:
including a console command, a migration, or another service.
