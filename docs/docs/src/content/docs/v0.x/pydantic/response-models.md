---
title: Response Models
description: "Declaring what an endpoint returns with response_model: enforcement rather than documentation, list responses, the serialisation options, and why a failure is a 500."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Sillo Response Models
  - tag: meta
    attrs:
      property: og:description
      content: response_model, field filtering, list responses and the serialisation flags.
---

```python
class PostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    published_at: datetime | None


@app.get("/posts/{id:int}", response_model=PostOut)
async def get_post(request, response, id=Path(type=int)):
    return await Post.get(id=id)
```

The return value is validated against `PostOut`, fields the model does not
declare are **dropped**, and the OpenAPI response schema is generated from the
same object.

## Enforced, not documented

This is the distinction worth internalising. A response model is not a comment
about what the endpoint returns. It is a filter the value passes through.

```python
class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    username: str


@app.get("/users/{id:int}", response_model=UserOut)
async def get_user(request, response, id=Path(type=int)):
    return await User.get(id=id)      # has password, is_staff, internal_notes
```

The user row carries a hashed password. `UserOut` does not declare it, so it
never reaches the client, and the same is true of every column added to that
table next year.

Compare with returning `user.to_dict()`, which publishes
[every field the model has](/v0.x/orm/models/#serialisation) and quietly starts
publishing the new one too.

That is the argument for declaring `response_model` on every endpoint that
returns data derived from a database row.

## Lists

```python
@app.get("/posts", response_model=PostOut, response_model_many=True)
async def list_posts(request, response):
    return await Post.filter(status="published").limit(20)
```

`response_model_many=True` says the handler returns a list of the model rather
than one. Each item is validated and shaped.

For an envelope, use a [generic model](/v0.x/pydantic/models/#generic-models)
instead:

```python
from typing import Generic, TypeVar

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int


@app.get("/posts", response_model=Page[PostOut])
async def list_posts(request, response, page=Query(1, type=int, ge=1)):
    result = await paginate(Post.filter(status="published"), page=page)
    return {"items": result.items, "total": result.total, "page": result.page}
```

Which documents the envelope properly (`PagePostOut` appears in your schema
list) rather than describing it as an untyped object.

## `from_attributes`

```python
model_config = ConfigDict(from_attributes=True)
```

Required on any model built from an ORM instance: it lets Pydantic read
attributes instead of dict keys. Without it, returning a `Post` raises because
the model expects a mapping.

v1 called this `orm_mode`.

:::caution[Fetch relations before returning]
```python
class PostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    author: AuthorOut
```

`PostOut` naming `author` means validation reads `post.author`. If it was never
fetched, that raises, **inside the response serialiser**, where the traceback
is least helpful and the client gets a 500.

```python
return await Post.get(id=id).prefetch_related("author")
return await Post.all().select_related("author").limit(20)
```

On a list endpoint this is also the difference between 2 queries and 21. See
[Eager loading](/v0.x/orm/eager-loading/).
:::

## Serialisation options

```python
@app.get(
    "/posts",
    response_model=PostOut,
    response_model_exclude_none=True,
    response_model_exclude_unset=False,
    response_model_exclude_defaults=False,
    response_model_by_alias=True,
)
```

| Option | Default | Effect |
| --- | --- | --- |
| `response_model_many` | `False` | The handler returns a list |
| `response_model_exclude_none` | `False` | Omit fields whose value is `None` |
| `response_model_exclude_unset` | `False` | Omit fields never explicitly set |
| `response_model_exclude_defaults` | `False` | Omit fields still at their default |
| `response_model_by_alias` | `True` | Serialise using field aliases |

`response_model_by_alias` defaults to **`True`**, so a model with
[aliases](/v0.x/pydantic/fields/#aliases) emits the alias without further
configuration. That is the opposite of Pydantic's own default, and it is the
right one for an API. The alias is the wire name.

`exclude_none=True` is tempting for tidy output and usually wrong: it makes
"absent" and "explicitly null" indistinguishable to the client, and it makes
the response shape vary per row, which a typed client cannot model.

## When the handler returns something else

```python
@app.get("/posts/{id:int}", response_model=PostOut)
async def get_post(request, response, id=Path(type=int)):
    return {"id": 1, "title": "Hello", "published_at": None}
```

A dict works, as does a `PostOut` instance, as does an ORM object with
`from_attributes=True`. All three are validated against the model.

## A failure is a 500

```json
{"error": "Internal Server Error", "detail": "Response validation failed"}
```

Not a 422. The client sent a valid request; your application produced a
response that does not match the contract it published. That is a server-side
bug, and returning a 4xx would blame the caller and mislead clients that retry
on 4xx.

The offending value is deliberately **not** echoed to the client. It may
contain exactly the data the response model existed to filter out. It is logged
with the method and path instead.

## Status codes

`response_model` describes the success response. Document the others with
`responses`:

```python
@app.post(
    "/posts",
    request_model=PostCreate,
    response_model=PostOut,
    responses={
        201: {"description": "Created"},
        409: {"description": "A post with that slug already exists"},
        422: {"description": "Validation failed"},
    },
)
```

## Several output shapes

A list endpoint rarely wants the same fields as a detail endpoint:

```python
class PostSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str


class PostDetail(PostSummary):
    body: str
    author: AuthorOut
    tags: list[TagOut]
```

```python
@app.get("/posts", response_model=PostSummary, response_model_many=True)
@app.get("/posts/{id:int}", response_model=PostDetail)
```

Two models, two schemas in your documentation, and a list endpoint that does
not transfer every post body. See [Patterns](/v0.x/pydantic/patterns/).

## Testing

```python
def test_never_returns_the_password(client):
    response = client.get("/users/1")
    assert response.status_code == 200
    assert "password" not in response.json()
```

Worth writing once per sensitive model. It is the test that fails when somebody
swaps `response_model` for `to_dict()` in a hurry.
