---
title: Serialisation
description: "Turning a model back into data: model_dump and model_dump_json, include and exclude, aliases, computed fields, custom serialisers and the round-trip guarantees."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Pydantic Serialisation in Sillo
  - tag: meta
    attrs:
      property: og:description
      content: model_dump, exclude_unset, computed fields and custom serialisers.
---

```python
post.model_dump()          # dict of Python objects
post.model_dump_json()     # JSON string
```

## `model_dump` versus `model_dump_json`

```python
class Event(BaseModel):
    id: UUID
    at: datetime


event.model_dump()
# {"id": UUID('...'), "at": datetime(2026, 8, 15, ...)}

event.model_dump_json()
# '{"id":"...","at":"2026-08-15T10:30:00Z"}'
```

`model_dump()` gives Python objects. `model_dump_json()` gives JSON, converting
`UUID`, `datetime`, `Decimal` and `Enum` along the way.

For a dict that is JSON-safe without going through a string:

```python
event.model_dump(mode="json")
# {"id": "...", "at": "2026-08-15T10:30:00Z"}
```

Which is what you want when handing a dict to `response.json()`. The default
`mode="python"` leaves a `datetime` in place, and the encoder then has to deal
with it.

## Choosing fields

```python
post.model_dump(include={"id", "title"})
post.model_dump(exclude={"body"})
```

Nested, with a dict:

```python
order.model_dump(exclude={"customer": {"address"}})
order.model_dump(include={"lines": {"__all__": {"sku", "quantity"}}})
```

`__all__` applies to every item in a collection.

Prefer a **separate model** over `exclude` for anything leaving the process.
An exclusion is a per-call-site decision, and one call site eventually forgets;
a `PostOut` model states the shape once. See [Patterns](/v1.0/pydantic/patterns/).

## `exclude_unset`

```python
post.model_dump(exclude_unset=True)
```

Only the fields the caller actually provided. This is what makes a PATCH
endpoint correct:

```python
from sillo import HttpContext, json

class PostUpdate(BaseModel):
    title: str | None = None
    body: str | None = None
    published: bool | None = None


@app.patch("/posts/{id:int}", request_model=PostUpdate)
async def update_post(ctx: HttpContext, payload, id=Path(type=int)):
    post = await Post.get(id=id)
    await post.update_from_dict(payload.model_dump(exclude_unset=True))
    return json(post.to_dict())
```

Without it, a client sending only `{"title": "New"}` also writes
`body = None` and `published = None`, because those are the model's defaults.
That is a data-loss bug, and it looks like a working endpoint until someone
patches one field.

Two related options:

```python
post.model_dump(exclude_defaults=True)   # omit anything equal to its default
post.model_dump(exclude_none=True)       # omit anything that is None
```

`exclude_none` is tempting for tidy responses and is usually wrong. It makes
"absent" and "explicitly null" indistinguishable to the client.

## Aliases

```python
webhook.model_dump(by_alias=True)
```

Emits the serialisation aliases rather than the field names. The camelCase
form, when you have set one. See [Fields](/v1.0/pydantic/fields/#aliases).

Sillo's [response models](/v1.0/pydantic/response-models/) do not set this for you,
so a model with aliases needs it explicitly, or an
[alias generator](/v1.0/pydantic/config/) plus `serialize_by_alias`.

## Computed fields

A value derived from others, included in the output:

```python
from pydantic import computed_field


class OrderOut(BaseModel):
    subtotal: Decimal
    tax: Decimal

    @computed_field
    @property
    def total(self) -> Decimal:
        return self.subtotal + self.tax
```

```json
{"subtotal": "100.00", "tax": "20.00", "total": "120.00"}
```

Computed fields are **output only**: they appear in `model_dump()` and in the
response schema, and are not accepted on input. Which is exactly right for a
derived value. A client should not be able to send a total that disagrees with
its parts.

The return annotation is required; it is what the schema is generated from.

## Custom serialisers

Per field:

```python
from pydantic import field_serializer


class PostOut(BaseModel):
    published_at: datetime | None

    @field_serializer("published_at")
    def serialize_date(self, value: datetime | None) -> str | None:
        return value.strftime("%Y-%m-%d") if value else None
```

Whole model:

```python
from pydantic import model_serializer


class Money(BaseModel):
    amount: Decimal
    currency: str

    @model_serializer
    def to_string(self) -> str:
        return f"{self.amount} {self.currency}"
```

Use these sparingly. A custom serialiser makes the output diverge from the
schema Pydantic generates, so your OpenAPI document can end up describing
something you no longer send. Where the shape genuinely differs, a separate
model is more honest.

## Secrets

```python
class Credentials(BaseModel):
    username: str
    password: SecretStr
```

```python
creds.model_dump()
# {"username": "ada", "password": SecretStr('**********')}
```

[`SecretStr`](/v1.0/pydantic/types/#pydantics-own-types) keeps the value out of
`repr`, tracebacks and logs. Getting it requires saying so:

```python
creds.password.get_secret_value()
```

Which is greppable. You can audit every place a secret is actually read.

## Warnings on mismatch

```python
post.model_dump(warnings="error")
```

By default, serialising a value that does not match its annotation emits a
warning and proceeds. `warnings="error"` makes it raise instead.

Worth turning on in tests. A response model quietly serialising the wrong type
is how a client's generated code breaks against a schema that says otherwise.

## Round-tripping

```python
PostCreate.model_validate(post.model_dump()) == post
```

Holds for plain models. It does **not** hold when:

- a field has a custom serialiser that is not the inverse of its validator;
- `exclude` or `exclude_unset` dropped something required;
- a computed field is present, since it cannot be validated back in.

Where a round trip matters (caching a model, queueing one as a job payload) use
`model_dump_json()` and `model_validate_json()`, and keep the model plain.

## In a Sillo handler

```python
from sillo import HttpContext, json

@app.get("/posts/{id:int}", response_model=PostOut)
async def get_post(ctx: HttpContext, id=Path(type=int)):
    post = await Post.get(id=id)
    return json(PostOut.model_validate(post).model_dump(mode="json"))
```

With `response_model=` declared, Sillo validates and shapes the return value
for you. See [Response models](/v1.0/pydantic/response-models/), which is the
shorter and safer form of the above.
