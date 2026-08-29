---
title: Nested Models
description: "Composing models: nesting, lists of models, dicts of models, unions and discriminated unions, recursive models, and the depth limits worth setting."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Nested Pydantic Models in Sillo
  - tag: meta
    attrs:
      property: og:description
      content: Nesting, collections of models, discriminated unions and recursion.
---

A model is a type, so a model can be a field.

```python
class Address(BaseModel):
    line1: str
    city: str
    postcode: str


class Customer(BaseModel):
    name: str
    address: Address
```

```python
Customer.model_validate({
    "name": "Ada",
    "address": {"line1": "1 High St", "city": "Cambridge", "postcode": "CB1 1AA"},
})
```

The nested dict is validated as an `Address`, and `customer.address` is a real
`Address` instance with its own validators applied.

## Collections of models

```python
class Order(BaseModel):
    lines: list[OrderLine]
    metadata: dict[str, Tag]
    coordinates: tuple[Point, Point]
```

Each item is validated. Errors carry the index, so a bad third line reports
`["body", "lines", 2, "quantity"]` rather than "something in lines is wrong",
which is the difference between a client fixing it and a client guessing.

Bound the length of anything a client controls:

```python
lines: list[OrderLine] = Field(min_length=1, max_length=500)
```

Without an upper bound, a request can contain a hundred thousand lines, and
your handler will loyally validate and insert every one.

## Optional nesting

```python
class Customer(BaseModel):
    address: Address | None = None
```

Both parts are needed: `| None` allows null, `= None` makes it optional. See
[Types](/v0.x/pydantic/types/#unions-and-optionals).

## Unions

```python
class Payment(BaseModel):
    method: Card | BankTransfer | Wallet
```

Pydantic tries each member in **smart mode**: an exact type match wins,
otherwise it tries each in order and keeps the first success.

The problem shows up in the errors. When none matches, you get the failures for
*every* member (three sets of field errors for one bad object) and the client
has to work out which one you meant.

## Discriminated unions

```python
from typing import Literal
from pydantic import Field


class Card(BaseModel):
    kind: Literal["card"]
    number: str
    expiry: str


class BankTransfer(BaseModel):
    kind: Literal["bank"]
    iban: str


class Payment(BaseModel):
    method: Card | BankTransfer = Field(discriminator="kind")
```

Now one field decides which model applies. Three things get better:

- **Validation is one attempt**, not *n*: faster, and O(1) in the number of
  members.
- **Errors are the right ones.** A `kind: "card"` with a bad expiry reports the
  expiry, not every field of every variant.
- **The OpenAPI schema** carries a proper `discriminator`, so generated clients
  produce a real tagged union instead of an untyped `oneOf`.

An unknown tag gives one clear error naming the allowed values.

Use this for anything polymorphic that crosses the wire: payment methods, event
payloads, notification channels, block types in a document.

## Recursive models

```python
class Category(BaseModel):
    name: str
    children: list["Category"] = []
```

The string annotation is what lets a class refer to itself. In modern Python
this resolves automatically; if it does not, rebuild explicitly:

```python
Category.model_rebuild()
```

Same for two models that reference each other.

:::caution[Bound the depth]
A recursive model has no natural limit, and a hostile payload nested ten
thousand deep will happily exhaust the stack during validation.

Where the input comes from a client, cap it. Either with a [model
validator](/v0.x/pydantic/validators/#model_validator) that walks and counts, or by
rejecting oversized bodies before parsing.
:::

## Building from ORM objects

```python
class PostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    author: AuthorOut
```

```python
post = await Post.get(id=1).prefetch_related("author")
PostOut.model_validate(post)
```

`from_attributes=True` (v1's `orm_mode`) lets a model read attributes instead
of dict keys, so an ORM instance can be validated directly.

:::caution[Fetch the relations first]
`PostOut` naming `author` means `model_validate` reads `post.author`. If it was
never fetched, that raises, inside the serialiser, where the traceback is least
helpful.

Ask for it in the query:

```python
await Post.all().select_related("author")
```

See [Eager loading](/v0.x/orm/eager-loading/). This is the single most common cause
of a response model blowing up in a list endpoint.
:::

## Flattening

When the wire shape is flat and your model is not, reshape in a
[`before` model validator](/v0.x/pydantic/validators/#modebefore):

```python
class Customer(BaseModel):
    name: str
    city: str

    @model_validator(mode="before")
    @classmethod
    def flatten(cls, data):
        if isinstance(data, dict) and isinstance(data.get("address"), dict):
            data = {**data, "city": data["address"].get("city")}
        return data
```

Better still, keep the model matching the wire and do the flattening in your
own code. A model whose shape does not match its JSON is a model every reader
has to decode twice.

## Schema names

Nested models appear in your OpenAPI document under `components/schemas`, keyed
by class name. Two classes with the same name in different modules collide, and
the second wins.

Give them distinct names (`PostOut`, `PostSummary`, `PostAdminOut`) rather than
reusing `Post` across modules. See [OpenAPI](/v0.x/pydantic/openapi/).

## When not to nest

Nesting is right when the inner object is a real thing with its own identity
and rules. It is wrong as a way of grouping fields for tidiness. Every level is
another dict a client has to construct and another level of error paths to
read.

For a response, prefer a flat model close to what the consumer actually wants.
For a request, prefer whatever shape the client naturally sends.
