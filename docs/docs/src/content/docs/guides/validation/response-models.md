---
title: Response models
description: response_model turns a documented output schema into an enforced one — coercing declared fields, dropping undeclared ones, and failing loudly when a handler breaks its own contract. Includes Pydantic serialization in full.
---

`response_model` makes the schema you publish the schema you actually return:

```python
from pydantic import BaseModel
from sillo import silloApp, Path

class UserOut(BaseModel):
    id: int
    name: str

app = silloApp()

@app.get("/users/{user_id}", response_model=UserOut)
async def get_user(request, response, user_id=Path(type=int)):
    return await db.fetch_user(user_id)     # row carries password_hash, internal_notes…
```

If the row is `{"id": "7", "name": "Ada", "password_hash": "…"}`, the client receives:

```json
{"id": 7, "name": "Ada"}
```

Two things happened: `"7"` was coerced to `7`, and `password_hash` **never left the process**.

## Why this matters

The leak protection is the point. Without a response model, a column added to that table next year starts appearing in your API the moment someone adds it to the database — no code change, no review, no notice. Password hashes, internal flags, soft-delete timestamps, another tenant's identifiers: all of it ships the instant it exists.

With a response model, the response can only ever contain what the model declares. New columns are invisible until someone deliberately adds them to the output schema, which is a change a reviewer can see.

The same mechanism gives you a second guarantee: the response **matches its documented type**. A handler that returns `{"id": None}` for a field declared `int` fails loudly instead of shipping a null your clients will crash on.

## Collections

```python
@app.get("/users", response_model=UserOut, response_model_many=True)
async def list_users(request, response):
    return await db.fetch_all_users()
```

Every element is validated and shaped independently. An error in one element names its index:

```json
{"loc": ["response", 3, "id"], "msg": "Input should be a valid integer"}
```

## ORM objects work directly

Validation reads attributes, so database rows need no manual conversion:

```python
@app.get("/users/{user_id}", response_model=UserOut)
async def get_user(request, response, user_id=Path(type=int)):
    return await User.get(id=user_id)     # a model instance, not a dict
```

This works because sillo validates with `from_attributes` enabled. Any object with matching attributes is acceptable — an ORM row, a dataclass, a `NamedTuple`, or a plain class of your own.

---

# Shaping the output

The rest of this page is Pydantic serialization. The same techniques apply to any model you dump by hand.

## Designing output models

The usual pattern is a shared base with input and output models diverging from it:

```python
class UserBase(BaseModel):
    name: str
    email: str

class UserCreate(UserBase):
    password: str          # accepted on input

class UserOut(UserBase):
    id: int
    created_at: datetime
    # password is absent by construction, not by remembering to exclude it
```

That last line is the discipline worth adopting. Excluding a sensitive field is something you can forget; never declaring it is not.

## Serialization options

```python
@app.get("/users", response_model=UserOut,
         response_model_many=True,
         response_model_exclude_none=True,
         response_model_exclude_unset=True,
         response_model_exclude_defaults=True,
         response_model_by_alias=True)
```

| Option | Effect |
| --- | --- |
| `response_model_many` | The handler returns a list of the model |
| `response_model_exclude_none` | Omit fields whose value is `None` |
| `response_model_exclude_unset` | Omit fields never explicitly set |
| `response_model_exclude_defaults` | Omit fields still equal to their default |
| `response_model_by_alias` | Serialize using field aliases. **Default `True`** |

The three exclusions differ in a way that matters:

```python
class Item(BaseModel):
    name: str
    tag: str | None = None
    count: int = 0

Item(name="a")                    # tag unset, count unset
Item(name="a", tag=None, count=0) # tag set to None, count set to its default
```

- `exclude_none` drops `tag` in both cases — it only looks at the value.
- `exclude_unset` drops `tag` and `count` in the first case, neither in the second — it tracks what the client or your code actually provided.
- `exclude_defaults` drops `count` in both — it compares against the declared default.

`exclude_unset` is the one to reach for in a PATCH-style response, where you want to echo back only what changed.

## Aliases

Output aliases are how you present camelCase to JavaScript clients while writing snake_case Python:

```python
from pydantic import BaseModel, Field

class UserOut(BaseModel):
    user_id: int = Field(serialization_alias="userId")
    first_name: str = Field(serialization_alias="firstName")
```

```json
{"userId": 7, "firstName": "Ada"}
```

`alias` sets both directions at once; `serialization_alias` and `validation_alias` set them separately, which is useful when a model is used for input and output with different conventions.

To convert every field rather than annotating each one:

```python
from pydantic import ConfigDict
from pydantic.alias_generators import to_camel

class UserOut(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel)
    user_id: int          # serializes as "userId"
    first_name: str       # serializes as "firstName"
```

Since `response_model_by_alias` defaults to `True`, aliases apply automatically. Set it to `False` to emit the Python names instead.

## Computed fields

To include a derived value without storing it:

```python
from pydantic import BaseModel, computed_field

class UserOut(BaseModel):
    first_name: str
    last_name: str

    @computed_field
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
```

```json
{"first_name": "Ada", "last_name": "Lovelace", "full_name": "Ada Lovelace"}
```

Computed fields appear in the generated OpenAPI schema, so clients see them documented. The return annotation is required — it is what determines the published type.

## Custom serializers

To control exactly how a field is rendered:

```python
from pydantic import BaseModel, field_serializer
from datetime import datetime

class EventOut(BaseModel):
    name: str
    starts_at: datetime

    @field_serializer("starts_at")
    def serialize_dt(self, dt: datetime) -> str:
        return dt.strftime("%Y-%m-%d %H:%M")
```

Or the whole model at once:

```python
from pydantic import model_serializer

class Money(BaseModel):
    amount: Decimal
    currency: str

    @model_serializer
    def to_string(self) -> str:
        return f"{self.amount} {self.currency}"
```

Be aware that a custom serializer can diverge from the declared schema — Pydantic will not stop you returning a string from a model documented as an object. Use `@field_serializer(..., return_type=str)` or annotate the serializer so the generated schema stays truthful.

## How types are rendered

Response models serialize in JSON mode, which converts Python types to JSON-compatible ones:

| Python | JSON |
| --- | --- |
| `datetime` | ISO 8601 string — `"2024-01-02T03:04:05"` |
| `date`, `time` | ISO 8601 string |
| `timedelta` | ISO 8601 duration — `"PT1H"` |
| `UUID` | string |
| `Decimal` | string, preserving exactness |
| `Enum` | the member's value |
| `bytes` | UTF-8 decoded string |
| `set`, `frozenset` | array |
| `IPv4Address` and friends | string |

`Decimal` becoming a string is deliberate and correct — rendering `19.99` as a JSON number would round-trip through a float and lose precision. Clients handling money should parse the string.

## Handler-built responses pass through

When a handler builds its own response it keeps full control, and the model is not applied:

```python
@app.get("/users/{user_id}", response_model=UserOut)
async def get_user(request, response, user_id=Path(type=int)):
    user = await User.get_or_none(id=user_id)
    if user is None:
        return response.json({"error": "not found"}, status_code=404)   # untouched
    return user                                                          # shaped
```

Once you have taken over status, headers, and body, sillo does not second-guess the payload. This is what makes error branches natural to write — a 404 body does not have to satisfy `UserOut`.

The same applies to redirects, file responses, and streams.

## Contract violations are a 500

A handler whose return value does not satisfy its own `response_model` produces **500**, not 422:

```python
@app.get("/user", response_model=UserOut)
async def get_user(request, response):
    return {"unexpected": True}     # -> 500
```

```json
{"error": "Internal Server Error", "detail": "Response validation failed"}
```

The caller did nothing wrong — the application broke the contract it published, which is a server-side bug. Returning 422 would wrongly blame the client and mislead anything that retries on 4xx.

The offending value is logged server-side and deliberately **not** echoed to the client, since filtering it out is exactly what the response model was for. To alert on these:

```python
from sillo import ResponseValidationError

async def on_response_invalid(request, response, exc):
    alert_oncall(path=request.url.path, errors=exc.errors)
    return response.json({"error": "Internal Server Error"}, status_code=500)

app.add_exception_handler(ResponseValidationError, on_response_invalid)
```

## Documentation

The response schema in your OpenAPI document is generated from the same model that enforces it, so the two cannot disagree. Other status codes still come from `responses=`:

```python
@app.get("/users/{user_id}",
         response_model=UserOut,                        # enforced, documents 200
         responses={404: {"description": "Not found"}})  # documented only
```

## Performance

A response model costs one validation plus one serialization pass. Because Pydantic already emits JSON-safe primitives, sillo skips its own encoder for these routes rather than walking the payload a second time — so a large collection is not penalized twice. Measured at roughly 2.9 µs for a small object, scaling linearly with size.
