---
title: Parameters
description: "Query, Path, Header, Cookie, Form and File — declaring typed, validated parameters with Pydantic constraints, and the legacy mode that predates them."
head:
  - tag: meta
    attrs:
      property: og:title
      content: Sillo Parameter Markers and Pydantic
  - tag: meta
    attrs:
      property: og:description
      content: Query, Path, Header, Cookie, Form and File with Pydantic types and constraints.
---

```python
from sillo import Query, Path


@app.get("/posts/{post_id:int}")
async def get_post(
    request, response,
    post_id=Path(type=int),
    page=Query(1, type=int, ge=1),
    q=Query(None, type=str, max_length=100),
):
    ...
```

Markers go in the **default position**, and the type goes on the marker. Sillo
handlers never require annotations, and annotations are never read.

## The six markers

| Marker | Reads from |
| --- | --- |
| `Query` | The query string |
| `Path` | The URL path |
| `Header` | A request header |
| `Cookie` | A cookie |
| `Form` | A urlencoded or multipart body field |
| `File` | An uploaded file |

```python
from sillo import Query, Path, Header, Cookie, Form, File
```

## Two modes

This is the thing to understand first.

**Legacy mode** — constructed with only a default, `alias` or `required`.
Behaves exactly as Sillo always has: coercion inferred from the default's
runtime type, a missing required parameter raising `ValueError`, and a
parameter with no default yielding the raw string.

```python
page = Query(1)             # legacy
```

**Validated mode** — constructed with an explicit `type` **or any constraint**.
The parameter is compiled into a Pydantic field at route registration and
validated per request, producing a proper 422 rather than a 500.

```python
page = Query(1, type=int, ge=1)      # validated
```

The mode is decided by what you constructed the marker with, never by
annotations. Documentation-only keywords — `description`, `example`, `title`,
`deprecated` — deliberately do **not** switch the mode, so enriching an
OpenAPI entry can never silently change runtime behaviour.

To opt a whole application in, including markers written the old way:

```python
app = SilloApp(strict_validation=True)
```

Or per route:

```python
@app.get("/posts", strict_validation=True)
```

**Write new code in validated mode.** A typed parameter gets coercion, a
documented schema, and a 422 that names the problem.

## Constraints

Every marker accepts the same set:

| | |
| --- | --- |
| Numeric | `gt`, `ge`, `lt`, `le`, `multiple_of` |
| String | `min_length`, `max_length`, `pattern` |
| Behaviour | `strict` |
| Docs only | `title`, `description`, `example`, `deprecated` |

```python
page = Query(1, type=int, ge=1, le=1000, description="1-based page number")
size = Query(20, type=int, ge=1, le=100)
sort = Query("created_at", type=str, pattern=r"^-?(created_at|title|views)$")
```

Constraints are enforced **and** published — the `ge=1` above appears as
`minimum: 1` in your [OpenAPI document](/pydantic/openapi/), so the validation
and the documentation cannot disagree.

That `pattern` on `sort` is worth copying. A sort parameter interpolated into
`order_by` without one is how an ordering parameter becomes an injection
surface.

## Coercion

Everything arriving in a URL, a header or a form is a **string**. Pydantic's
lax mode is what turns `"5"` into `5`:

```python
page = Query(1, type=int)         # ?page=5 → 5
active = Query(False, type=bool)  # ?active=true → True
```

:::caution[Do not use `strict=True` here]
Strict mode disables coercion, and query parameters, headers, path segments and
form fields are strings by definition. `Query(type=int, strict=True)` rejects
every input, including valid ones.

`strict` is for a [JSON body](/pydantic/request-models/), where the client
controls the types.
:::

## `Query`

```python
page = Query(1, type=int, ge=1)                 # optional, defaults to 1
q = Query(None, type=str, max_length=100)       # optional, may be absent
term = Query(type=str, min_length=1)            # required — no default
```

A marker with no default is required, and a missing one is a 422 rather than a
500.

Lists come from a repeated parameter:

```python
tags = Query(default_factory=list, type=list[str])
```

```
?tags=python&tags=async
```

Renaming the wire parameter:

```python
page_size = Query(20, type=int, alias="per_page")
```

The alias is what the client sends and what appears in
[error paths](/pydantic/errors/#loc); `page_size` is the Python name.

## `Path`

```python
@app.get("/posts/{post_id:int}")
async def get_post(request, response, post_id=Path(type=int)):
    ...
```

Path parameters are always required — the route did not match otherwise — so a
default is meaningless here.

Note the converter in the path (`{post_id:int}`) **and** the type on the
marker. The converter decides whether the route matches at all; the marker
decides what the handler receives and what the documentation says. Keep them
in agreement.

## `Header`

```python
user_agent = Header(None, type=str)
api_version = Header("2026-01-01", type=str, alias="X-API-Version")
```

Header names are converted to `Header-Case` automatically, so `user_agent`
reads `User-Agent`. Pass `alias` when the real name is not derivable.

Header lookups are case-insensitive, as HTTP requires.

## `Cookie`

```python
session_id = Cookie(None, type=str)
theme = Cookie("light", type=str, pattern=r"^(light|dark)$")
```

Validate anything you read from a cookie. A cookie is client-controlled data
that *looks* like server state, which is exactly why it gets trusted by
accident.

## `Form` and `File`

```python
from sillo import File, Form


@app.post("/upload", request_content_type="multipart/form-data")
async def upload(
    request, response,
    title=Form(type=str, min_length=1, max_length=200),
    document=File(),
):
    content = await document.read()
    ...
```

`File()` yields an `UploadFile` with `filename`, `content_type` and `read()`.

:::caution[Validate uploads yourself]
Neither marker checks a file's size or its real content type. `content_type` is
supplied by the client and is trivially wrong — a `.php` renamed `.jpg` still
announces itself as an image.

Check the size as you read, sniff the actual bytes, and never trust the
filename as a path. See [File uploads](/guides/file-upload/).
:::

Do not mix `Form`/`File` with
[`request_model`](/pydantic/request-models/) — a request has one body, and it
is either JSON or a form.

## How it is compiled

At **route registration**, Sillo groups the markers by location and compiles
one Pydantic model per location — one for the query string, one for headers,
and so on.

A request then costs a fixed number of validation calls with no signature
introspection on the hot path. That is the reason for declaring parameters as
markers rather than reading annotations per request: the work happens once, at
import.

It is also why failures from several locations arrive together. Each location's
model is validated, and the errors are concatenated — so a bad query parameter
and a bad body are one 422, not two round trips.

## Errors

```json
{
  "detail": [
    {"loc": ["query", "page"], "msg": "Input should be greater than or equal to 1",
     "type": "greater_than_equal", "input": "0"}
  ]
}
```

The first element of `loc` names the location, so a client can tell a bad query
string from a malformed body. See [Validation errors](/pydantic/errors/).

## Dependencies

Markers compose with `Depend`, and a dependency can declare markers of its own:

```python
from sillo import Depend, Query


def pagination(page=Query(1, type=int, ge=1), size=Query(20, type=int, ge=1, le=100)):
    return {"page": page, "size": size}


@app.get("/posts")
async def list_posts(request, response, paging=Depend(pagination)):
    ...
```

The parameters are collected from the dependency and validated with the rest,
so they appear in the OpenAPI document for every route that uses it. This is
the shape for a pagination or filter set shared across endpoints.

## See also

- [Request models](/pydantic/request-models/) — the JSON body
- [Fields](/pydantic/fields/) — the same constraints on model fields
- [Request parameters](/guides/request-parameters/) — the wider guide
