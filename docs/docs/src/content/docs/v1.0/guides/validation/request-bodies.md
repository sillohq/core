---
title: Request bodies
description: "Declare a JSON body once with request_model= on the decorator, and learn Pydantic's BaseModel in full: nested models, custom validators, model configuration, unions, and aliases."
---

The JSON body is the one input declared on the **decorator** rather than with a parameter marker:

```python
from pydantic import BaseModel
from sillo import SilloApp, HttpContext

app = SilloApp()

class UserCreate(BaseModel):
    name: str
    email: str
    age: int

@app.post("/users", request_model=UserCreate)
async def create_user(ctx: HttpContext, user):
    return {"name": user.name, "age": user.age}    # user IS a UserCreate
```

```bash
curl -X POST localhost:8000/users \
  -H 'Content-Type: application/json' \
  -d '{"name":"Ada","email":"a@b.co","age":36}'
```

There is exactly one way to declare a body, so there is never a question of which mechanism a route is using.

##  How the body reaches your handler

sillo injects the validated model into the **first plain parameter** after
the context — a parameter with no default, which nothing else in the framework
would fill. The name is entirely yours:

```python
# All equivalent — the second positional parameter receives the validated
# model regardless of what you call it.
from sillo import HttpContext

async def create_user(ctx: HttpContext, user): ...
async def create_user(ctx: HttpContext, data): ...
async def create_user(ctx: HttpContext, payload): ...
```

It is also always available on the request, which is what you want when the handler has no spare parameter:

```python
from sillo import HttpContext

@app.post("/users", request_model=UserCreate)
async def create_user(ctx: HttpContext):
    user = ctx.validated_data
```

###  It composes with everything

Dependencies, markers, and path parameters are skipped when choosing the body parameter, so they mix freely:

```python
from sillo import HttpContext, Depend, Path, Query

@app.post("/teams/{team_id}/users", request_model=UserCreate)
async def create_user(ctx: HttpContext, user,          # the body
                      team_id=Path(type=int),           # path
                      page=Query(1, type=int, ge=1),    # query
                      db=Depend(get_db)):               # dependency
    ...
```

Path parameters are excluded **by name**, so a bare parameter matching a URL segment binds from the URL, not the body:

```python
from sillo import HttpContext

@app.post("/teams/{team_id}/users", request_model=UserCreate)
async def create_user(ctx: HttpContext, team_id, user):
    # team_id comes from the URL, user from the body
    ...
```

---

#  Writing models

The rest of this page is Pydantic. Everything here applies equally to `response_model`.

##  Fields

A model declares its fields with ordinary type annotations. Fields without a default are required:

```python
class UserCreate(BaseModel):
    name: str                    # required
    nickname: str = ""           # optional, defaults to ""
    bio: str | None = None       # optional, may be explicitly null
    tags: list[str] = []         # optional, defaults to an empty list
```

Mutable defaults are safe here: Pydantic copies them per instance, so unlike a
plain Python function default, `tags` is not shared between requests.

###  `str | None` versus a default

These mean different things, and the difference shows in your API:

```python
bio: str | None            # required, but may be null: {"bio": null} is valid
bio: str | None = None     # optional and nullable: omitting it is valid
bio: str = ""              # optional, never null
```

###  `Field` for constraints and metadata

```python
from pydantic import BaseModel, Field

class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=50)
    age: int = Field(ge=0, le=150)
    slug: str = Field(pattern=r"^[a-z0-9-]+$")
    score: float = Field(default=0.0, ge=0, le=1)
    email: str = Field(description="Primary contact address",
                       examples=["ada@example.com"])
```

`Field()` takes the same constraints as a sillo marker (`gt`, `ge`, `lt`, `le`,
`multiple_of`, `min_length`, `max_length`, `pattern`, `strict`) plus
documentation keywords that flow into your OpenAPI schema.

To make a field required *and* constrained, either use `Field(...)` with the Ellipsis, or simply omit the default:

```python
name: str = Field(..., min_length=2)     # required, explicit
name: str = Field(min_length=2)          # required, same thing
```

###  Types

Everything from the [parameter type catalog](/v1.0/guides/validation/parameters/#the-type-catalog) works in a model, plus the container types that only make sense in JSON:

```python
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Literal
from uuid import UUID

class Order(BaseModel):
    id: UUID
    placed_at: datetime
    total: Decimal                       # exact, unlike float
    currency: Literal["usd", "eur"]
    status: OrderStatus                  # an Enum
    items: list[Item]                    # a list of nested models
    metadata: dict[str, str]             # arbitrary string map
    coords: tuple[float, float]          # fixed-length
```

##  Nested models

Nesting needs no special handling. Declare one model as another's field type:

```python
class Address(BaseModel):
    street: str
    city: str
    postcode: str = Field(pattern=r"^[0-9]{5}$")

class UserCreate(BaseModel):
    name: str
    address: Address
    previous_addresses: list[Address] = []
```

```json
{"name": "Ada",
 "address": {"street": "1 Main", "city": "London", "postcode": "12345"}}
```

Errors point at the exact path that failed, including list indices:

```json
{"detail": [
  {"loc": ["body", "address", "postcode"], "msg": "String should match pattern '^[0-9]{5}$'",
   "type": "string_pattern_mismatch"},
  {"loc": ["body", "previous_addresses", 0, "city"], "msg": "Field required", "type": "missing"}
]}
```

Nested models are lifted into `components.schemas` in your OpenAPI document automatically.

###  Self-referencing models

A model may reference itself, using a string annotation:

```python
class Comment(BaseModel):
    text: str
    replies: list["Comment"] = []
```

##  Custom validation

When a constraint cannot express your rule, write a validator.

###  Field validators

```python
from pydantic import BaseModel, field_validator

class UserCreate(BaseModel):
    name: str
    username: str

    @field_validator("username")
    @classmethod
    def no_reserved_names(cls, v: str) -> str:
        if v.lower() in {"admin", "root", "system"}:
            raise ValueError("that username is reserved")
        return v
```

Raise `ValueError` to fail. Pydantic converts it into a proper validation
error, and sillo returns it as part of the 422:

```json
{"detail": [{"loc": ["body", "username"], "msg": "Value error, that username is reserved",
             "type": "value_error"}]}
```

Return the value (possibly transformed) to accept it. Validators are a
normalization hook as much as a rejection hook:

```python
@field_validator("username")
@classmethod
def normalize(cls, v: str) -> str:
    return v.strip().lower()
```

Validate several fields with one function, or all of them:

```python
@field_validator("name", "username")
@classmethod
def not_blank(cls, v: str) -> str:
    if not v.strip():
        raise ValueError("must not be blank")
    return v

@field_validator("*")           # every field
@classmethod
def strip_strings(cls, v):
    return v.strip() if isinstance(v, str) else v
```

###  Before and after

By default a validator runs *after* Pydantic has coerced the value to the
declared type, so `v` is already the right type. Use `mode="before"` to see the
raw input instead, useful for accepting a format Pydantic does not know:

```python
@field_validator("tags", mode="before")
@classmethod
def split_csv(cls, v):
    if isinstance(v, str):
        return [t.strip() for t in v.split(",")]
    return v
```

###  Model validators

To check fields against each other, validate the whole model:

```python
from pydantic import BaseModel, model_validator

class DateRange(BaseModel):
    start: date
    end: date

    @model_validator(mode="after")
    def check_order(self):
        if self.end < self.start:
            raise ValueError("end must not be before start")
        return self
```

With `mode="after"` you receive the validated instance and return it. With `mode="before"` you receive the raw input dict, which lets you restructure a payload before field validation runs:

```python
@model_validator(mode="before")
@classmethod
def unwrap_envelope(cls, data):
    if isinstance(data, dict) and "data" in data:
        return data["data"]
    return data
```

##  Aliases

When the wire format differs from your Python naming:

```python
class UserCreate(BaseModel):
    first_name: str = Field(alias="firstName")
    last_name: str = Field(alias="lastName")
```

The client sends `firstName`; your code reads `user.first_name`. Errors report the alias, since that is what the client sent.

To accept **both** names:

```python
from pydantic import ConfigDict

class UserCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    first_name: str = Field(alias="firstName")
```

To convert every field automatically rather than annotating each one:

```python
from pydantic.alias_generators import to_camel

class UserCreate(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    first_name: str        # accepts "firstName"
    postal_code: str       # accepts "postalCode"
```

##  Model configuration

`model_config` changes how a model behaves as a whole:

```python
class UserCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",              # reject unknown keys
        str_strip_whitespace=True,   # trim every string field
        frozen=True,                 # make instances immutable
        populate_by_name=True,       # accept field names as well as aliases
        from_attributes=True,        # allow validating arbitrary objects
    )
```

###  `extra` is worth a decision

| Value | Behavior |
| --- | --- |
| `"ignore"` | Unknown keys are silently dropped. **The default.** |
| `"forbid"` | Unknown keys are a validation error. |
| `"allow"` | Unknown keys are kept on the instance. |

`"forbid"` catches client typos that would otherwise pass silently. A request
sending `emial` gets told about it rather than having the field quietly
ignored:

```json
{"detail": [{"loc": ["body", "emial"], "msg": "Extra inputs are not permitted",
             "type": "extra_forbidden"}]}
```

The trade-off is strictness against forward compatibility: with `"forbid"`, an older server rejects payloads from a newer client that added a field.

##  Unions and discriminated unions

A field can accept more than one shape:

```python
class Payment(BaseModel):
    method: Card | BankTransfer
```

Pydantic tries each in turn, which makes errors hard to read when none match. A *discriminated* union is faster and gives a clear error, by naming the field that decides:

```python
from typing import Literal, Union
from pydantic import Field

class Card(BaseModel):
    kind: Literal["card"]
    number: str

class BankTransfer(BaseModel):
    kind: Literal["bank"]
    iban: str

class Payment(BaseModel):
    method: Union[Card, BankTransfer] = Field(discriminator="kind")
```

Now `{"kind": "card", ...}` goes straight to `Card`, and an unknown `kind` produces one clear error rather than a list of failures from every branch. Your OpenAPI document gains a proper `oneOf` with a discriminator mapping.

##  Computed fields

To expose a derived value without storing it:

```python
from pydantic import computed_field

class User(BaseModel):
    first_name: str
    last_name: str

    @computed_field
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
```

Computed fields are included when serializing and appear in the generated schema. They are most useful on a `response_model`.

##  Reusing shape across models

Ordinary inheritance works, and is the usual way to keep an input and output model in step:

```python
class UserBase(BaseModel):
    name: str
    email: str

class UserCreate(UserBase):
    password: str            # accepted on input

class UserOut(UserBase):
    id: int                  # returned, and password is absent by construction
```

##  Errors

A body that fails validation returns **422** with the bare list of Pydantic errors:

```json
[{"loc": ["age"], "msg": "Field required", "type": "missing"}]
```

Under `strict_validation=True` it becomes the unified envelope that every other location uses:

```json
{"detail": [{"loc": ["body", "age"], "msg": "Field required", "type": "missing"}]}
```

See [Validation errors](/v1.0/guides/validation/errors/) for the full contract and the complete error-type catalog.

###  Malformed and wrong-shaped payloads

Both return 422:

```bash
curl -X POST localhost:8000/users -H 'Content-Type: application/json' -d '{not json'
# -> 422, type "json_invalid"

curl -X POST localhost:8000/users -H 'Content-Type: application/json' -d '["a","b"]'
# -> 422, "Input should be a valid dictionary or instance of UserCreate"
```

##  Reading the raw body as well

Body parsing is cached on the request, so reading it yourself costs nothing extra:

```python
from sillo import HttpContext

@app.post("/users", request_model=UserCreate)
async def create_user(ctx: HttpContext, user):
    raw = await ctx.json          # served from cache
    return {"validated": user.name, "raw_keys": list(raw)}
```

This is how you detect which optional fields a client actually sent, if `model_fields_set` is not enough:

```python
user.model_fields_set     # {"name", "email"} — the fields explicitly provided
```

##  Do not mix with forms

A request has one body, and it is either JSON or a form. Never both. Declaring
`request_model=` alongside `Form` or `File` parameters on the same route means
one of them always receives nothing. Pick the encoding per endpoint.


##  Modelling input separately from storage

The most consequential decision on this page is whether your request
model is also your database model. It should not be.

A table has columns a client must never set, `id`, `created_at`, `owner_id`,
`is_admin`, `balance`. A request model derived from that table inherits every
one of them, and Pydantic will happily populate them from the request body.
That is mass assignment, and it is the mechanism behind a long history of
privilege escalation bugs.

```python title="the input model is a subset, deliberately"
from sillo import HttpContext, json

class ArticleCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str
    tags: list[str] = Field(default_factory=list, max_length=10)
    # No id. No author_id. No published_at. No view_count.


@app.post("/articles", request_model=ArticleCreate)
async def create_article(ctx: HttpContext):
    data = ctx.validated_data
    article = await Article.create(
        **data.model_dump(),
        author_id=ctx.user.id,        # from the session, never the body
        published_at=None,
    )
    return json({"id": article.id}, status_code=201)
```

The server-controlled fields are set explicitly, from server-controlled
sources. Nothing a client sends can reach them, because they are not in
the model.

The second reason to separate them is churn. A table changes for storage
reasons (a column split, an index, a denormalisation) and none of those should
break your API. Keeping the two independent means a migration is a migration
rather than a breaking API change.

##  Create and update are different shapes

A `POST` body and a `PATCH` body describe different things. `POST` says
"here is the complete object"; `PATCH` says "change these fields and
leave the rest". Using one model for both forces a choice between
required fields that break PATCH and optional fields that let POST create
half an object.

```python title="two models, one base"
class ArticleBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str


class ArticleCreate(ArticleBase):
    pass                                 # everything required


class ArticleUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    body: str | None = None
```

Then, crucially, apply an update with `exclude_unset=True`:

```python
await article.update_from_dict(ctx.validated_data.model_dump(exclude_unset=True))
```

Without `exclude_unset`, a PATCH that sends only `title` also sends
`body=None`, and the update nulls the body. This is the single most common bug
in partial-update endpoints, and it is silent. The request succeeds and data
disappears.

`exclude_unset` distinguishes "not sent" from "sent as null", which is
exactly the distinction PATCH needs. If clients must be able to null a
field explicitly, that works too: an explicitly-sent `null` counts as
set.

##  Size and depth limits

A JSON body is parsed before it is validated, so a body large enough to
exhaust memory does so before any of your constraints apply.

Enforce a byte limit at the proxy (`client_max_body_size` in nginx) so
oversized requests never reach Python. Inside the application, bound the
collections your models accept:

```python
tags: list[str] = Field(default_factory=list, max_length=50)
items: list[LineItem] = Field(max_length=500)
```

An unbounded `list[LineItem]` accepts a hundred thousand items and
validates every one of them, which is a CPU denial of service with a
valid request.

Deeply nested models have the same shape of problem: a recursive model
with no depth limit lets a client send a structure a thousand levels
deep. If a model can contain itself, bound the recursion explicitly
rather than trusting clients not to.
