---
title: Validation Errors
description: "The 422 a client receives. The error structure, what loc means, how failures from several locations are reported together, and how to customise the message or the whole response."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Pydantic Validation Errors in Sillo
  - tag: meta
    attrs:
      property: og:description
      content: The 422 body, the loc path, error types, and customising the response.
---

When validation fails, Sillo returns **422 Unprocessable Entity** with every
failure listed:

```json
{
  "detail": [
    {
      "loc": ["body", "title"],
      "msg": "String should have at least 1 character",
      "type": "string_too_short",
      "input": ""
    },
    {
      "loc": ["query", "page"],
      "msg": "Input should be a valid integer, unable to parse string as an integer",
      "type": "int_parsing",
      "input": "abc"
    }
  ]
}
```

Note that both failures are in one response. A bad query parameter **and** a
malformed body are reported together rather than one per round trip. A client
fixing a form gets every problem at once instead of discovering them in
sequence.

## The error object

| Key | Meaning |
| --- | --- |
| `loc` | Path to the failure. First element is the request location. |
| `msg` | Human-readable message |
| `type` | Machine-readable error code |
| `input` | The value that failed, when available |

Pydantic's own `url` key (a link to pydantic.dev) is stripped. It is noise in
an HTTP API response, and it points at documentation for a library the client
may not be using.

## `loc`

The first element names **where** the value came from:

`body`, `query`, `path`, `header`, `cookie`, `form`.

```json
["body", "title"]                    a JSON body field
["query", "page"]                    a query parameter
["path", "post_id"]                  a path parameter
["body", "lines", 2, "quantity"]     the third line's quantity
["body", "address", "postcode"]      a nested field
```

That prefix is Sillo's addition. Pydantic reports locations relative to the
model it validated, which for a query string is a synthetic per-location model,
so a failure would otherwise arrive as just `["page"]` with no indication of
where `page` came from.

**Aliases are resolved.** When a field has a
[validation alias](/v0.x/pydantic/fields/#aliases), the path shows the wire name the
client actually sent, not the Python identifier:

```python
event_type: str = Field(alias="eventType")
```

```json
{"loc": ["body", "eventType"], "msg": "Field required"}
```

Reporting `event_type` would name a key the client has never seen.

## Common error types

| `type` | Cause |
| --- | --- |
| `missing` | A required field was absent |
| `string_too_short` / `string_too_long` | `min_length` / `max_length` |
| `string_pattern_mismatch` | `pattern` |
| `int_parsing` / `float_parsing` | Not a number |
| `int_type` / `string_type` / `bool_type` | Wrong type in strict mode |
| `greater_than` / `less_than_or_equal` | Numeric bounds |
| `too_short` / `too_long` | Collection length |
| `enum` | Not one of the permitted values |
| `value_error` | A `ValueError` from your own validator |
| `extra_forbidden` | An unknown field with `extra="forbid"` |
| `json_invalid` | The body was not valid JSON |

`type` is the key to branch on in a client. `msg` is for humans and its wording
can change between Pydantic versions; `type` is stable.

## Messages from your validators

```python
@field_validator("slug")
@classmethod
def url_safe(cls, value: str) -> str:
    if not re.fullmatch(r"[a-z0-9-]+", value):
        raise ValueError("must be lowercase letters, digits and hyphens")
    return value
```

```json
{
  "loc": ["body", "slug"],
  "msg": "Value error, must be lowercase letters, digits and hyphens",
  "type": "value_error"
}
```

Pydantic prefixes `Value error, `. Write the message as a continuation of that
so it reads properly, and write it for whoever has to fix the request,
"invalid" tells them nothing.

For a custom `type` as well as a message:

```python
from pydantic_core import PydanticCustomError


@field_validator("slug")
@classmethod
def url_safe(cls, value: str) -> str:
    if not re.fullmatch(r"[a-z0-9-]+", value):
        raise PydanticCustomError(
            "slug_format",
            "must be lowercase letters, digits and hyphens",
        )
    return value
```

```json
{"loc": ["body", "slug"], "msg": "...", "type": "slug_format"}
```

Worth it when a client needs to react to that specific failure rather than
displaying the message.

## Customising the response

The default shape is `{"detail": [...]}`. To change it (to match an existing
API convention, or to add a request id) register your own handler:

```python
from sillo.validation import RequestValidationError


async def validation_handler(request, response, exc: RequestValidationError):
    return response.json(
        {
            "error": "validation_failed",
            "request_id": request.state.get("request_id"),
            "fields": [
                {"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]}
                for e in exc.errors
            ],
        },
        status_code=422,
    )


app.add_exception_handler(RequestValidationError, validation_handler)
```

`exc.errors` is the flat list; `exc.body` is the raw payload that failed, when
one was available.

:::caution[`input` echoes what was sent]
The default response includes the offending value. That is helpful for
debugging and means a rejected password field can appear in the response body,
in a client's console, and in whatever logs it.

If your API accepts secrets, strip `input` in a custom handler.
:::

## Response validation is a 500, not a 422

When a handler returns something its
[`response_model`](/v0.x/pydantic/response-models/) does not permit, that is a
server-side bug. The client sent a valid request and your application produced
an invalid response.

```json
{"error": "Internal Server Error", "detail": "Response validation failed"}
```

Status **500**. Returning 422 would blame the caller and would mislead clients
that retry on 4xx.

The offending value is deliberately not echoed. It may contain exactly the data
the response model existed to filter out. It is logged instead, with the method
and path, so you can find it.

## Catching it yourself

Outside a handler, Pydantic raises `ValidationError` directly:

```python
from pydantic import ValidationError

try:
    payload = PostCreate.model_validate(data)
except ValidationError as exc:
    for error in exc.errors():
        print(error["loc"], error["msg"])
```

```python
exc.errors()        # list of dicts
exc.error_count()   # how many
exc.json()          # as JSON
```

Useful in a [console command](/v0.x/cli/custom-commands/) or a queued job, where
there is no HTTP response to produce and you want to report the failures
yourself.

## Testing

```python
def test_title_is_required(client):
    response = client.post("/posts", json={"body": "…"})
    assert response.status_code == 422

    errors = response.json()["detail"]
    assert any(e["loc"] == ["body", "title"] and e["type"] == "missing" for e in errors)
```

Assert on `loc` and `type`, not on `msg`. The message is Pydantic's wording and
can change under you on a minor upgrade; the type is the contract.
