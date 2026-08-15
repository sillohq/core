---
title: OpenAPI
description: "How Pydantic models become your API documentation — where each schema comes from, what each Field argument produces, naming collisions, and customising the output."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Pydantic and OpenAPI in Sillo
  - tag: meta
    attrs:
      property: og:description
      content: How models become schemas, what each Field argument produces, and how to customise it.
---

Your OpenAPI document is generated from the same objects that do the
validating. There is no second declaration to keep in step, which is the whole
argument for declaring constraints on models rather than checking them in
handlers.

```python
class PostCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200, description="Shown in listings.")
    published: bool = False
```

becomes

```json
{
  "PostCreate": {
    "type": "object",
    "properties": {
      "title": {
        "type": "string",
        "minLength": 1,
        "maxLength": 200,
        "description": "Shown in listings."
      },
      "published": {"type": "boolean", "default": false}
    },
    "required": ["title"]
  }
}
```

## What ends up where

| Declaration | In the document |
| --- | --- |
| `request_model=` | `requestBody` schema |
| `response_model=` | The success response schema |
| `Query`, `Path`, `Header`, `Cookie` | `parameters` entries |
| `Form`, `File` | `requestBody` as form or multipart |
| `responses={...}` | The other status codes |
| `tags`, `summary`, `description` | Operation metadata |

## Field arguments to schema keywords

| `Field()` | Schema |
| --- | --- |
| `default` | `default` |
| `title` | `title` |
| `description` | `description` |
| `examples` | `examples` |
| `gt` / `ge` | `exclusiveMinimum` / `minimum` |
| `lt` / `le` | `exclusiveMaximum` / `maximum` |
| `multiple_of` | `multipleOf` |
| `min_length` / `max_length` on a string | `minLength` / `maxLength` |
| `min_length` / `max_length` on a list | `minItems` / `maxItems` |
| `pattern` | `pattern` |
| `deprecated` | `deprecated` |
| `exclude=True` | *(omitted)* |
| no default | listed in `required` |

The [parameter markers](/pydantic/parameters/) take the same constraint
arguments and produce the same keywords, so `Query(1, type=int, ge=1)` is
documented as `minimum: 1`.

## Types to schema types

| Python | Schema |
| --- | --- |
| `str` | `string` |
| `int` | `integer` |
| `float` | `number` |
| `bool` | `boolean` |
| `Decimal` | `string` with `format: decimal` |
| `datetime` | `string`, `format: date-time` |
| `date` | `string`, `format: date` |
| `UUID` | `string`, `format: uuid` |
| `EmailStr` | `string`, `format: email` |
| `HttpUrl` | `string`, `format: uri` |
| `list[T]` | `array` of `T` |
| `dict[str, T]` | `object` with `additionalProperties` |
| `Literal["a", "b"]` | `enum` |
| An `Enum` class | `enum`, as a named component |
| A nested model | `$ref` to a component |
| `T \| None` | `anyOf` with `null` |
| `Any` | `{}` — anything |

`Any` is the one to avoid. It becomes an empty schema, and a generated client
produces `unknown` or `object`. If the shape is known, declare it.

## Naming and collisions

Every model becomes a component keyed by its **class name**.

```python
# app/schemas/posts.py
class PostOut(BaseModel): ...

# app/schemas/admin.py
class PostOut(BaseModel): ...     # collides
```

Same name, different modules, and the second overwrites the first in your
document. Nothing warns you.

Name them for what they are: `PostOut`, `PostSummary`, `PostAdminOut`,
`PostCreate`. Reusing `Post` across modules is the reliable way to publish a
schema that describes the wrong thing.

[Generic models](/pydantic/models/#generic-models) get generated names —
`Page[PostOut]` becomes `PagePostOut` — which are unique by construction.

## Discriminated unions

```python
class Payment(BaseModel):
    method: Card | BankTransfer = Field(discriminator="kind")
```

produces a proper `discriminator` with a mapping, so a generated client builds
a real tagged union instead of an untyped `oneOf` it has to try in turn.

Worth the `Literal` tag for anything polymorphic that crosses the wire. See
[Nested models](/pydantic/nested/#discriminated-unions).

## Examples

At the field level:

```python
title: str = Field(examples=["Async Python in practice"])
```

At the model level, which is more useful:

```python
class PostCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"title": "Async Python in practice", "body": "…", "tags": ["python"]}
            ]
        }
    )
```

A whole valid request beats a set of per-field placeholders — it is what
someone will copy into a terminal, and it demonstrates the fields' relationship
to each other.

Per response:

```python
@app.post(
    "/posts",
    response_model=PostOut,
    responses={
        201: {
            "description": "Created",
            "content": {
                "application/json": {
                    "example": {"id": 1, "title": "Async Python in practice"}
                }
            },
        }
    },
)
```

## Escape hatches

For a schema keyword Pydantic does not generate:

```python
class Coordinates(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"externalDocs": {"url": "https://example.com/geo"}}
    )
```

Per field:

```python
value: str = Field(json_schema_extra={"x-internal": True})
```

`x-` extensions are how you carry information for your own tooling — a
code generator, a documentation theme — without inventing keywords the spec
does not have.

## Generating it yourself

```python
PostCreate.model_json_schema()
```

The dict Sillo embeds. Useful in a test:

```python
def test_title_is_documented_as_bounded():
    schema = PostCreate.model_json_schema()
    assert schema["properties"]["title"]["maxLength"] == 200
```

Which is a reasonable thing to assert for a published contract — it fails if
someone removes the constraint, and the constraint *is* the contract.

## Excluding a route

```python
@app.get("/internal/metrics", exclude_from_schema=True)
```

Keeps an operation out of the document entirely. For health checks, internal
tooling, anything that is not part of the public surface.

It does not make the route private. Use [auth](/guides/protecting-routes/) for
that — an undocumented endpoint is still an endpoint.

## Viewing it

The [documentation UI](/guides/openapi/documentation-ui/) renders it, and the
raw document is served alongside. See
[the OpenAPI guides](/guides/openapi/) for configuring the title, version,
servers and security schemes.

## Keeping it honest

The document is generated, so it cannot describe a shape your code does not
enforce — with two exceptions worth knowing:

- **A [custom serialiser](/pydantic/serialization/#custom-serialisers)** can
  make the output diverge from the declared schema.
- **A handler returning a raw `response.json(...)`** with no `response_model`
  is undocumented and unenforced.

Both are avoidable. Declare `response_model` on everything that returns data,
and keep custom serialisers for cases where you have checked the schema still
matches.
