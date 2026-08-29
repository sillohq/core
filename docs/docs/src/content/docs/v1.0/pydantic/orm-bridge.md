---
title: The ORM Bridge
description: "Pydantic models and Record models together: generating schemas from models, from_attributes, the relation trap, and where a hand-written schema is the right call."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Pydantic and the Sillo ORM
  - tag: meta
    attrs:
      property: og:description
      content: Generating schemas from models, from_attributes, and where to hand-write.
---

Two model systems, doing different jobs.

| | [Record model](/v1.0/orm/models/) | Pydantic model |
| --- | --- | --- |
| Describes | A table | A message |
| Validates | On save | On construction |
| Changes when | The schema changes | The API contract changes |

Keeping them separate is the point. A column added to a table should not
silently change what your API accepts or publishes.

## Reading a model into a schema

```python
from pydantic import BaseModel, ConfigDict


class PostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    published_at: datetime | None
```

```python
post = await Post.get(id=1)
PostOut.model_validate(post)
```

`from_attributes=True` lets Pydantic read attributes rather than dict keys, so
an ORM instance validates directly. This is v1's `orm_mode`.

With [`response_model=`](/v1.0/pydantic/response-models/) declared, Sillo does the
validation for you. You return the ORM object and the model shapes it.

## Relations

```python
class AuthorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str


class PostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    author: AuthorOut
    tags: list[TagOut]
```

:::caution[Fetch them first, or this raises]
Naming `author` means validation reads `post.author`. An unfetched relation
raises, inside the serialiser, producing a 500 for what is really a missing
`select_related`.

```python
await Post.get(id=id).prefetch_related("author", "tags")
await Post.all().select_related("author").prefetch_related("tags").limit(20)
```

On a list endpoint this is also 2 queries instead of 41. See
[Eager loading](/v1.0/orm/eager-loading/).
:::

The safe habit: whenever you add a relation to an output model, change the
query in the same commit.

## Generating a schema from a model

```python
from sillo.record.pydantic import pydantic_model_from_tortoise

UserCreate = pydantic_model_from_tortoise(
    User,
    name="UserCreate",
    exclude=["id", "created_at", "updated_at", "deleted_at", "password"],
    optional_fields=["bio"],
)
```

Reads the model's fields and builds a Pydantic model from them. Covered in full
at [Pydantic schemas](/v1.0/orm/pydantic/) on the ORM side.

### Where it earns its place

An internal admin endpoint, a prototype, a form that really is "the model minus
a few fields". It stays in step with the model for free.

### Where it does not

Anything that is a **contract**. A generated schema changes when the table
changes, which is precisely what a published API must not do.

Three specific limitations, all documented on
[that page](/v1.0/orm/pydantic/#the-type-mapping):

- `DatetimeField` and `DateField` become **`str`**: no parsing, no format
  validation, any string accepted.
- `DecimalField` becomes **`float`**, which reintroduces binary rounding into a
  value you chose `Decimal` to keep exact.
- Unknown field types fall back to `str`, including relations.

For a public API, write the schema.

## Whitelist for output

```python
UserOut = pydantic_model_from_tortoise(
    User, name="UserOut", include=["id", "username", "created_at"],
)
```

`include` over `exclude` for anything leaving the process. A whitelist fails
closed: a column added next year is not published until somebody says it should
be.

Same reasoning as [`fillable` over `guarded`](/v1.0/orm/mass-assignment/#which-to-reach-for)
on the write side.

## The four-model shape

For a resource with a real API surface:

```python
class PostBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1)


class PostCreate(PostBase):
    model_config = ConfigDict(extra="forbid")
    slug: str = Field(pattern=r"^[a-z0-9-]+$")


class PostUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = None
    body: str | None = None


class PostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    slug: str
    published_at: datetime | None
```

Four models because they answer four different questions, and each can change
without the others:

- `PostCreate`: what a client may send to create one.
- `PostUpdate`: what may be changed, all optional for a real PATCH.
- `PostOut`: what is published.
- `PostBase`: the shared rules, declared once.

It looks like duplication. It is the boundary, and it is where an API stops
being a projection of your database schema.

## Writing back

```python
from sillo import HttpContext

@app.post("/posts", request_model=PostCreate, response_model=PostOut)
async def create_post(ctx: HttpContext, payload):
    post = await Post.create(**payload.model_dump(), author_id=ctx.user.id)
    return post
```

```python
from sillo import HttpContext

@app.patch("/posts/{id:int}", request_model=PostUpdate, response_model=PostOut)
async def update_post(ctx: HttpContext, payload, id=Path(type=int)):
    post = await Post.get(id=id)
    await post.update_from_dict(payload.model_dump(exclude_unset=True))
    return post
```

Two things carry the safety here:

- **`exclude_unset=True`**, so an unmentioned field is not written as its
  default. Without it, a PATCH of one field resets the rest.
- **`author_id` from the request, not the body.** The model does not declare
  it, so a client cannot supply it.

[`fillable`](/v1.0/orm/mass-assignment/) on the model is the second line of defence
behind both.

## Enums on both sides

```python
class Status(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
```

```python
class Post(Model):
    status = fields.CharEnumField(Status, default=Status.DRAFT)


class PostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: Status
```

One enum, used by [`CharEnumField`](/v1.0/orm/field-reference/#enums) and by the
schema. The database stores the string, the API documents the allowed values,
and adding a member is one edit.

## Decimals

```python
class Order(Model):
    total = fields.DecimalField(max_digits=10, decimal_places=2)


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total: Decimal
```

`Decimal` on both sides, and it serialises to a JSON **string** by default,
which is correct. A monetary value in a JSON number is a value the client's
JSON parser may round.

## Testing the boundary

```python
def test_output_model_publishes_only_what_it_declares():
    assert set(PostOut.model_fields) == {"id", "title", "slug", "published_at"}
```

A blunt test, and it is the one that fails when somebody adds a field to the
output model without thinking about who reads it.
