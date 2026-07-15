---
title: Exception Handlers & Pydantic
description: Automatic Tortoise exception to HTTP status mapping and Pydantic schema generation from Tortoise model fields.
---

# Exception Handlers & Pydantic

## DB Exception Handlers

Map Tortoise ORM exceptions to proper HTTP responses automatically.

```python
from sillo import silloApp
from sillo.record import register_db_exception_handlers

app = silloApp()
register_db_exception_handlers(app)
```

This registers four handlers that convert database errors into
structured JSON responses:

| Tortoise Exception | HTTP | Body |
|---|---|---|
| `DoesNotExist` | 404 | `{"error": "Not Found", "detail": "..."}` |
| `IntegrityError` | 409 | `{"error": "Conflict", "detail": "..."}` |
| `ValidationError` | 422 | `{"error": "Validation Error", "detail": "..."}` |
| `OperationalError` | 503 | `{"error": "Service Unavailable", "detail": "Database unavailable"}` |

### How Exception Handlers Work

Sillo's exception handling middleware catches any exception raised in
a route handler.  If the exception type matches a registered handler,
the handler is called with `(request, response, exc)` and its return
value becomes the HTTP response.  This is identical to the standard
`app.add_exception_handler()` API.

These handlers run through the normal middleware pipeline, so they
benefit from CORS headers, logging, and any other middleware you've
registered.

### Customizing Individual Handlers

```python
from tortoise.exceptions import DoesNotExist

async def custom_404(request, response, exc):
    return response.json({
        "error": "Resource not found",
        "detail": str(exc),
        "code": "NOT_FOUND",
    }, status_code=404)

app.add_exception_handler(DoesNotExist, custom_404)
```

### In Production

For production, you typically want to log the full exception and return
a sanitized message:

```python
import logging

async def production_integrity_handler(request, response, exc):
    logging.error("Integrity error: %s", exc, exc_info=True)
    return response.json({
        "error": "Conflict",
        "detail": "This operation conflicts with existing data.",
    }, status_code=409)

app.add_exception_handler(IntegrityError, production_integrity_handler)
```

## Pydantic Schema Generation

`pydantic_model_from_tortoise()` generates a Pydantic model from a
Tortoise model's fields.  No manual schema duplication.

```python
from sillo.record import pydantic_model_from_tortoise

UserCreate = pydantic_model_from_tortoise(
    User,
    name="UserCreate",
    exclude=["id", "created_at", "updated_at", "deleted_at"],
    optional_fields=["bio", "avatar_url"],
)

@app.post("/users", request_model=UserCreate)
async def create_user(request, response):
    user = await User.create(**request.validated_data.model_dump())
    return response.json(user.to_dict(), status_code=201)
```

### How Field Types Are Mapped

The function inspects each Tortoise field using `isinstance` checks and
maps to Python types:

| Tortoise Field | Python / Pydantic Type |
|---|---|
| `IntField`, `SmallIntField`, `BigIntField` | `int` |
| `FloatField`, `DecimalField` | `float` |
| `BooleanField` | `bool` |
| `CharField`, `TextField` | `str` |
| `DatetimeField`, `DateField` | `str` (ISO 8601 format) |
| `TimeDeltaField` | `float` |
| `JSONField` | `dict` |

Null fields become `Optional[Type]` with a `None` default.  Primary key
fields are excluded from required validation (they're auto-generated).

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `model_class` | `type` | required | The Tortoise model class |
| `name` | `str` | auto | Name for the generated Pydantic model |
| `exclude` | `List[str]` | `None` | Field names to exclude |
| `include` | `List[str]` | `None` | If set, ONLY include these fields |
| `optional_fields` | `List[str]` | `None` | Fields to make Optional |

### In a PATCH Handler

```python
UserUpdate = pydantic_model_from_tortoise(
    User, name="UserUpdate",
    exclude=["id", "created_at", "updated_at"],
    optional_fields=["name", "email", "bio"],  # all optional for partial update
)

@app.patch("/users/{user_id}", request_model=UserUpdate)
async def update_user(request, response, user_id: str):
    user = await User.get_or_none(id=user_id)
    if not user:
        return response.json({"error": "Not found"}, status_code=404)
    await user.update_from_dict(
        request.validated_data.model_dump(exclude_unset=True)
    )
    return response.json(user.to_dict())
```
