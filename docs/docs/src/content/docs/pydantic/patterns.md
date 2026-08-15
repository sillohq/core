---
title: Patterns
description: "The Pydantic shapes that come up repeatedly in a Sillo application: model families, shared bases, paginated envelopes, filter dependencies, config models and error contracts."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Pydantic Patterns in Sillo
  - tag: meta
    attrs:
      property: og:description
      content: Model families, envelopes, filter dependencies, settings and error contracts.
---

## A shared base

Set the policy once:

```python
# app/schemas/base.py
from pydantic import BaseModel, ConfigDict


class RequestModel(BaseModel):
    """Anything a client sends."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        frozen=True,
        validate_default=True,
    )


class ResponseModel(BaseModel):
    """Anything built from a database row."""

    model_config = ConfigDict(from_attributes=True)
```

Every request model rejects typos and strips whitespace; every response model
can read an ORM instance. Changing the policy is one edit rather than fifty.

## The model family

```python
class PostBase(RequestModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1)


class PostCreate(PostBase):
    slug: str = Field(pattern=r"^[a-z0-9-]+$", max_length=200)


class PostUpdate(RequestModel):
    title: str | None = None
    body: str | None = None
    published: bool | None = None


class PostSummary(ResponseModel):
    id: int
    title: str
    published_at: datetime | None


class PostDetail(PostSummary):
    body: str
    author: AuthorOut
```

Five models, five questions. A list endpoint returns `PostSummary` and does not
transfer every post body; a detail endpoint returns `PostDetail`; a PATCH takes
`PostUpdate` with everything optional.

Keep them in `app/schemas/`, one module per resource. They are part of your API
surface and benefit from being somewhere you can read the whole of it.

## A paginated envelope

```python
from typing import Generic, TypeVar

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    pages: int
    has_next: bool
```

```python
@app.get("/posts", response_model=Page[PostSummary])
async def list_posts(request, response, page=Query(1, type=int, ge=1)):
    result = await paginate(Post.filter(status="published").order_by("-id"), page=page)
    return result.to_dict()
```

Declared once, correct for every resource, and each parameterisation gets its
own [named schema](/pydantic/openapi/#naming-and-collisions)
(`PagePostSummary`) so generated clients get a real type instead of an untyped
object.

## Filters as a dependency

```python
from sillo import Depend, Query


class PostFilters(BaseModel):
    status: Literal["draft", "published", "archived"] | None = None
    author_id: int | None = None
    q: str | None = None


def post_filters(
    status=Query(None, type=str),
    author_id=Query(None, type=int),
    q=Query(None, type=str, max_length=100),
) -> PostFilters:
    return PostFilters(status=status, author_id=author_id, q=q)


@app.get("/posts", response_model=Page[PostSummary])
async def list_posts(request, response, filters=Depend(post_filters)):
    query = Post.all()
    if filters.status:
        query = query.filter(status=filters.status)
    if filters.author_id:
        query = query.filter(author_id=filters.author_id)
    if filters.q:
        query = query.filter(Q(title__icontains=filters.q) | Q(body__icontains=filters.q))
    ...
```

The parameters are collected from the dependency and documented on every route
that uses it. See [Parameters](/pydantic/parameters/#dependencies) and
[building a Q up conditionally](/orm/filtering/#building-one-up).

## Validated configuration

```python
# app/config.py
from pydantic import BaseModel, Field, SecretStr


class Config(BaseModel):
    app_name: str = "Myapp"
    debug: bool = False
    secret_key: SecretStr
    database_url: str
    session_lifetime: int = Field(default=86400, ge=60)
    cors_origins: list[str] = Field(default_factory=list)


config = Config(
    secret_key=os.environ["SECRET_KEY"],
    database_url=os.environ["DATABASE_URL"],
    debug=os.getenv("DEBUG", "false").lower() == "true",
)
```

Configuration is input too, and it fails at **startup** rather than at the
first request that reads it. A missing `SECRET_KEY` should stop the process,
not produce a 500 an hour later.

[`SecretStr`](/pydantic/types/#pydantics-own-types) keeps the key out of
`repr()`, tracebacks and logs.

## A reusable constrained type

```python
from typing import Annotated
from pydantic import AfterValidator, Field


def _is_slug(value: str) -> str:
    if not re.fullmatch(r"[a-z0-9-]+", value):
        raise ValueError("must be lowercase letters, digits and hyphens")
    return value


Slug = Annotated[str, Field(max_length=200), AfterValidator(_is_slug)]
Email = Annotated[EmailStr, Field(max_length=255)]
Money = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
```

```python
class PostCreate(RequestModel):
    slug: Slug


class ProductCreate(RequestModel):
    price: Money
```

The rule lives with the type, not with each model that happens to use it. See
[Validators](/pydantic/validators/#reusable-annotated-validators).

## One-of-two-fields

```python
class Notification(RequestModel):
    email: EmailStr | None = None
    phone: str | None = None

    @model_validator(mode="after")
    def exactly_one_target(self):
        if bool(self.email) == bool(self.phone):
            raise ValueError("provide exactly one of email or phone")
        return self
```

A [model validator](/pydantic/validators/#model_validator) is the right place.
It sees both fields, and does not depend on declaration order the way a field
validator would.

## An error contract

```python
class ErrorDetail(BaseModel):
    field: str
    message: str


class ErrorResponse(BaseModel):
    error: str
    detail: str
    fields: list[ErrorDetail] = []
```

```python
@app.post("/posts", response_model=PostOut, responses={
    409: {"model": ErrorResponse, "description": "Slug already in use"},
    422: {"model": ErrorResponse, "description": "Validation failed"},
})
```

Documenting your errors with a model means clients can handle them
programmatically rather than by pattern-matching on strings. See
[customising the 422](/pydantic/errors/#customising-the-response).

## A job payload

```python
class SendWelcomeEmail(BaseModel):
    user_id: int
    template: str = "welcome"
    locale: str = "en"
```

```python
await queue.dispatch("send_welcome", SendWelcomeEmail(user_id=user.id).model_dump())
```

```python
async def handle(payload: dict):
    data = SendWelcomeEmail.model_validate(payload)
```

A queued job's payload crosses a process boundary and is deserialised somewhere
else, possibly by a newer version of your code. Validating it on the way out
*and* on the way in turns a schema mismatch into a clear error instead of a
`KeyError` at 3am.

Keep job payloads flat and made of primitives. A `datetime` round-trips through
JSON as a string, and the model is what turns it back.

## Anti-patterns

**One model for input and output.**

```python
class Post(BaseModel):     # used for both
    id: int
    title: str
```

The `id` is required on input, where the client cannot know it. Split them.

**`Any` where the shape is known.** It documents as "anything" and validates
nothing.

**Excluding instead of a separate model.** `model_dump(exclude={"password"})`
is a decision each call site has to remember; a `UserOut` model is a decision
made once.

**Validators that query.** They cannot be async and they race. Use a
[constraint](/orm/meta/#constraints) and catch the error.

**Optional without a default.** `x: int | None` is required in v2. Every time.
