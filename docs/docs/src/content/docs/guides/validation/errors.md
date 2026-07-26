---
title: Validation errors
description: One 422 contract across every request location, reporting every failure at once. Includes the complete Pydantic error-type catalog and how to customize messages and responses.
---

A validation failure returns **422 Unprocessable Entity** with every problem found, across every location, in a single response:

```json
{
  "detail": [
    {"loc": ["query", "page"], "msg": "Input should be greater than or equal to 1",
     "type": "greater_than_equal", "input": "0"},
    {"loc": ["body", "email"], "msg": "Field required", "type": "missing"}
  ]
}
```

## The shape of an error

Every entry has the same four keys:

| Key | Meaning |
| --- | --- |
| `loc` | Path to the offending value, starting with the request location |
| `msg` | Human-readable description, suitable for showing a developer |
| `type` | Machine-readable identifier, stable across Pydantic releases |
| `input` | The value that was rejected, when available |

Build client-side handling on `type`, never on `msg` — messages are wording and may be improved; types are a contract.

## Reading `loc`

The first element names the location that failed, so a client can tell a malformed query string from a malformed body without guessing:

| `loc[0]` | Source |
| --- | --- |
| `query` | URL query string |
| `header` | Request header |
| `cookie` | Cookie |
| `path` | URL path segment |
| `body` | JSON body |
| `form` | Form field or upload |
| `response` | The handler's own output |

Remaining elements are the field path, which nests for nested models and indexes into collections:

```json
{"loc": ["body", "address", "postcode"]}
{"loc": ["body", "items", 0, "sku"]}
{"loc": ["query", "ids", 2]}
```

The name reported is the **wire** name. If a parameter called `page_num` has `alias="page"`, errors say `page` — what the client actually sent, not your internal identifier.

## Nothing short-circuits

A request with a bad query parameter *and* a malformed body reports both. Clients fix everything in one round trip rather than discovering problems one at a time:

```json
{"detail": [
  {"loc": ["path", "team_id"], "msg": "Input should be a valid integer", "type": "int_parsing"},
  {"loc": ["query", "page"],   "msg": "Input should be a valid integer", "type": "int_parsing"},
  {"loc": ["header", "X-Count"], "msg": "Field required", "type": "missing"}
]}
```

The one exception is forms: if a `Form` field fails, missing-file checks for that request are not also reported.

## The error-type catalog

These are the `type` values you will actually encounter. Knowing them makes client-side handling straightforward.

### Presence and structure

| `type` | Cause |
| --- | --- |
| `missing` | A required field was absent |
| `extra_forbidden` | An unknown key, when the model sets `extra="forbid"` |
| `json_invalid` | The body was not parseable JSON |
| `model_type` | A non-object body where an object was declared |
| `model_attributes_type` | The value could not be read as a model or object |

### Type coercion

| `type` | Cause |
| --- | --- |
| `int_parsing` | A string that is not an integer |
| `int_type` | A value of the wrong type entirely for `int` |
| `int_from_float` | A float with a fractional part given to an `int` |
| `float_parsing` | A string that is not a number |
| `bool_parsing` | Not one of the accepted boolean spellings |
| `string_type` | A non-string given to `str` — note that numbers are **not** stringified |
| `bytes_type` | Wrong type for `bytes` |
| `decimal_parsing` | Not a valid decimal |
| `uuid_parsing` | Malformed UUID |
| `datetime_parsing` / `date_parsing` / `time_parsing` | Malformed date or time |
| `enum` | Not one of the enum's members |
| `literal_error` | Not one of the `Literal` values |

### Constraints

| `type` | Constraint |
| --- | --- |
| `greater_than` | `gt` |
| `greater_than_equal` | `ge` |
| `less_than` | `lt` |
| `less_than_equal` | `le` |
| `multiple_of` | `multiple_of` |
| `string_too_short` | `min_length` on a string |
| `string_too_long` | `max_length` on a string |
| `string_pattern_mismatch` | `pattern` |
| `too_short` / `too_long` | length constraints on a collection |

### Custom validation

| `type` | Cause |
| --- | --- |
| `value_error` | A `ValueError` raised in your validator |
| `assertion_error` | A failed `assert` in your validator |

## Custom messages

Raising `ValueError` in a validator puts your text in `msg`, prefixed with `Value error,`:

```python
from pydantic import BaseModel, field_validator

class UserCreate(BaseModel):
    username: str

    @field_validator("username")
    @classmethod
    def no_reserved(cls, v: str) -> str:
        if v.lower() in {"admin", "root"}:
            raise ValueError("that username is reserved")
        return v
```

```json
{"loc": ["body", "username"], "msg": "Value error, that username is reserved",
 "type": "value_error"}
```

For a fully custom `type` as well as a message, raise `PydanticCustomError`:

```python
from pydantic_core import PydanticCustomError

@field_validator("username")
@classmethod
def no_reserved(cls, v: str) -> str:
    if v.lower() in {"admin", "root"}:
        raise PydanticCustomError(
            "reserved_username",
            "The username '{name}' is reserved",
            {"name": v},
        )
    return v
```

```json
{"loc": ["body", "username"], "msg": "The username 'admin' is reserved",
 "type": "reserved_username"}
```

A stable custom `type` is what lets a client show a translated message of its own.

## Customizing the response

Register a handler for `RequestValidationError`:

```python
from sillo import silloApp, RequestValidationError

app = silloApp()

async def my_validation_handler(request, response, exc):
    return response.json(
        {"ok": False, "errors": exc.errors},
        status_code=400,
    )

app.add_exception_handler(RequestValidationError, my_validation_handler)
```

The exception carries:

- `exc.errors` — the list of error dicts, already location-prefixed
- `exc.body` — the raw payload that failed, when available

### Field-keyed errors

Many frontends expect errors keyed by form field:

```python
async def flat_errors(request, response, exc):
    out = {}
    for err in exc.errors:
        field = ".".join(str(p) for p in err["loc"][1:]) or err["loc"][0]
        out.setdefault(field, []).append(err["msg"])
    return response.json({"errors": out}, status_code=422)
```

```json
{"errors": {"email": ["Field required"],
            "address.postcode": ["String should match pattern '^[0-9]{5}$'"]}}
```

### Redacting the input

`input` echoes the rejected value, which is convenient in development and undesirable when the field is a password:

```python
SENSITIVE = {"password", "token", "secret", "card_number"}

async def redacted(request, response, exc):
    errors = []
    for err in exc.errors:
        err = dict(err)
        if any(s in str(err["loc"][-1]).lower() for s in SENSITIVE):
            err.pop("input", None)
        errors.append(err)
    return response.json({"detail": errors}, status_code=422)
```

Declaring such fields as `SecretStr` is the more thorough fix, since it protects logs and tracebacks too.

## Response validation errors

When a handler's return value violates its `response_model`, sillo raises `ResponseValidationError` and returns **500** — the caller did nothing wrong. The offending value is logged and never echoed to the client. Customize it the same way:

```python
from sillo import ResponseValidationError

async def on_response_invalid(request, response, exc):
    alert_oncall(path=request.url.path, errors=exc.errors)
    return response.json({"error": "Internal Server Error"}, status_code=500)

app.add_exception_handler(ResponseValidationError, on_response_invalid)
```

These are worth alerting on rather than merely logging. Each one means your API is documented as returning something it did not return.

## Raising validation errors yourself

For a rule that cannot live in a model — a uniqueness check against the database, say — raise the same error so the client sees one consistent shape:

```python
from sillo import RequestValidationError

@app.post("/users", request_model=UserCreate)
async def create_user(request, response, user):
    if await User.exists(email=user.email):
        raise RequestValidationError([{
            "loc": ["body", "email"],
            "msg": "That email is already registered",
            "type": "value_error.unique",
        }])
    ...
```

## A `pydantic.ValidationError` from your own code

If you validate a model by hand and let the error escape, sillo catches it and returns a nested object:

```json
{"error": "Validation Error",
 "errors": {"username": "Field required",
            "address": {"city": "Field required"}}}
```

This shape predates the unified contract and applies only to models you validate yourself. Override it by registering a handler for `pydantic.ValidationError`.

Bodies declared with `request_model=` return a bare list of Pydantic errors for the same historical reason. Enable `strict_validation=True` to move them onto the unified envelope:

```python
app = silloApp(strict_validation=True)
```

```json
{"detail": [{"loc": ["body", "age"], "msg": "Field required", "type": "missing"}]}
```

## Which status code

| Situation | Status | Why |
| --- | --- | --- |
| Bad parameter, body, or form | 422 | The client sent something the schema rejects |
| Malformed JSON | 422 | Still a client mistake |
| Missing required input | 422 | — |
| Handler violates its `response_model` | 500 | A server-side contract breach |
| Route not matched | 404 | Resolved before validation runs |
| Authentication failed | 401 | Resolved before validation runs |

Validation runs after routing and authentication, so a 404 or 401 is never masked by a 422 — and an unauthenticated caller never learns which of your fields are required.
