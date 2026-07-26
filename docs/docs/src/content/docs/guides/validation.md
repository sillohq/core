---
title: Validation
description: sillo validates every request input and every response with Pydantic. You declare the type on the marker, not in a type annotation, and the same declaration drives coercion, validation, and the generated OpenAPI schema.
head:
- tag: meta
  attrs:
    property: og:title
    content: Validation
- tag: meta
  attrs:
    property: og:description
    content: sillo validates every request input and every response with Pydantic. You declare the type on the marker, not in a type annotation, and the same declaration drives coercion, validation, and the generated OpenAPI schema.
---

sillo validates every input a route consumes and, when you ask it to, every response it produces. Pydantic does the work, but you never have to restructure your handlers around type annotations — the type goes on the marker, where the rest of the parameter's configuration already lives.

One declaration drives three things: how the value is coerced, how it is validated, and what appears in your OpenAPI document. They are generated from the same schema, so your published contract cannot drift away from what your API actually enforces.

## The markers

Every place a request can carry data has a marker. Import them from `sillo`:

```python
from sillo import Query, Header, Cookie, Path, Form, File
```

| Marker | Reads from | Example |
| --- | --- | --- |
| `Query` | URL query string | `page=Query(1, type=int)` |
| `Header` | Request headers | `token=Header(type=str)` |
| `Cookie` | Cookies | `sid=Cookie(None, type=str)` |
| `Path` | URL path segments | `user_id=Path(type=int)` |
| `Form` | Form or multipart field | `title=Form(type=str)` |
| `File` | Uploaded file | `avatar=File(...)` |

The JSON request body is the one input that is **not** a marker. It is declared once on the decorator with `request_model=`, so there is exactly one way to declare a body — see [Request bodies](#request-bodies).

A handler using several at once:

```python
from pydantic import BaseModel
from sillo import silloApp, Path, Query

class UserCreate(BaseModel):
    name: str
    email: str

class UserOut(BaseModel):
    id: int
    name: str

app = silloApp()

@app.post("/teams/{team_id}/users",
          request_model=UserCreate,
          response_model=UserOut)
async def create_user(request, response, user,
                      team_id=Path(type=int),
                      notify=Query(False, type=bool)):
    created = await save_user(user, team_id, notify=notify)
    return created
```

The first two parameters are always `request` and `response`, exactly as before. The body arrives in `user`; everything else is declared with a marker.

## Declaring the type

The type lives on the marker as `type=`:

```python
page=Query(1, type=int)
tags=Query([], type=List[str])
```

If you leave `type=` off, sillo infers it from the default value — `Query(1)` is an integer, `Query("")` a string. That inference is what pre-existing sillo applications rely on, and it still works.

## Constraints

Pydantic's constraints are marker keyword arguments:

```python
page = Query(1, type=int, ge=1, le=100)
slug = Query(type=str, min_length=3, max_length=64, pattern=r"^[a-z-]+$")
```

Available: `gt`, `ge`, `lt`, `le`, `multiple_of`, `min_length`, `max_length`, `pattern`, `strict`.

Documentation-only keywords — `title`, `description`, `example`, `deprecated` — enrich the OpenAPI entry without changing validation behavior:

```python
q = Query(type=str, description="Full-text search", example="widgets")
```

## Validation errors

A failure returns **422** with every problem found, across every location, in one response:

```json
{
  "detail": [
    {"loc": ["query", "page"], "msg": "Input should be greater than or equal to 1", "type": "greater_than_equal"},
    {"loc": ["body", "email"], "msg": "Field required", "type": "missing"}
  ]
}
```

The first element of `loc` is the location that failed, so a client can tell a malformed query string from a malformed body without guessing. The name reported is the **wire name** — if you set `alias="page"` on a parameter called `page_num`, errors say `page`.

Nothing short-circuits: a request with a bad query parameter *and* a bad body reports both, rather than making the client fix one problem per round trip.

## Lists and repeated parameters

A list-typed parameter collects repeated occurrences of the key:

```python
@app.get("/items")
async def search(request, response, tags=Query([], type=List[str])):
    ...
```

```
GET /items?tags=red&tags=blue   ->   tags == ["red", "blue"]
```

This is the standard HTTP convention. Note that it differs from the legacy comma-splitting behavior described under [Legacy parameters](#legacy-parameters) below.

## Request bodies

The JSON body is declared on the decorator, with `request_model=`:

```python
@app.post("/users", request_model=UserCreate)
async def create(request, response, user):
    return {"name": user.name}       # user IS a UserCreate instance
```

sillo injects the validated model into the **first plain parameter** after `request` and `response` — a parameter with no default, which nothing else in the framework would fill. The name is yours to choose; `user`, `data`, and `payload` all work.

It is also always available on the request, which is what you want when the handler has no plain parameter to spare:

```python
@app.post("/users", request_model=UserCreate)
async def create(request, response):
    user = request.validated_data
```

### It composes with everything

Dependencies, markers, and path parameters are all skipped when choosing the body parameter, so they can be mixed freely:

```python
@app.post("/teams/{team_id}/users", request_model=UserCreate)
async def create(request, response, user,          # <- the body
                 team_id=Path(type=int),           # path
                 page=Query(1, type=int, ge=1),    # query
                 db=Depend(get_db)):               # dependency
    ...
```

Path parameters are excluded by name, so a handler like `async def create(request, response, team_id, user)` on `/teams/{team_id}/users` binds `team_id` from the URL and `user` from the body.

### Errors

A body that fails validation returns 422 with the bare list of Pydantic errors:

```json
[{"loc": ["age"], "msg": "Field required", "type": "missing"}]
```

This is the shape sillo has always returned, kept so existing clients keep working. Under `strict_validation=True` it becomes the unified envelope used by every other location:

```json
{"detail": [{"loc": ["body", "age"], "msg": "Field required", "type": "missing"}]}
```

Malformed JSON, or a payload of the wrong shape entirely (an array where an object was declared), returns 422 in both modes. Previously both crashed with a 500.

## Forms and file uploads

Declaring any `Form` or `File` parameter switches the route to parsing the body as a form. sillo picks urlencoded or multipart based on what the client sends:

```python
from sillo import Form, File

@app.post("/upload")
async def upload(request, response,
                 title=Form(type=str),
                 avatar=File(...)):
    content = await avatar.read()
    return {"title": title, "filename": avatar.filename, "size": len(content)}
```

`File` parameters arrive as `UploadFile` (the framework's `UploadedFile`) and are passed through without coercion — the object wraps a spooled file handle, not data Pydantic can meaningfully check. Use `File(None)` to make an upload optional. In the OpenAPI document they appear as `{"type": "string", "format": "binary"}` under `multipart/form-data`.

## Response models

`response_model` turns a documented output schema into an enforced one:

```python
@app.get("/users/{user_id}", response_model=UserOut)
async def get_user(request, response, user_id=Path(type=int)):
    return await db.fetch_user(user_id)     # may carry password_hash, etc.
```

Fields `UserOut` does not declare are dropped before the response is encoded, so an internal column added to a database row later cannot quietly start leaking. Declared fields are coerced, and objects are read by attribute, so ORM rows work without converting to a dict first.

Options:

```python
@app.get("/users", response_model=UserOut,
         response_model_many=True,            # handler returns a list
         response_model_exclude_none=True,    # drop null fields
         response_model_exclude_unset=True,
         response_model_exclude_defaults=True,
         response_model_by_alias=True)        # default
```

Two behaviors worth knowing:

- A handler that builds its own response — `return response.json(...)` — passes through untouched. Once you take control of status, headers, and body, sillo does not second-guess the payload.
- A handler whose return value violates its own `response_model` produces a **500**, not a 422. The caller did nothing wrong; the application broke the contract it published. The offending value is logged server-side and deliberately not echoed to the client, since filtering it out is what the response model was for.

## Validating inside dependencies

Markers work in any injected callable, not just handlers:

```python
from sillo import Depend, Query

def pagination(page=Query(1, type=int, ge=1),
               size=Query(20, type=int, ge=1, le=100)):
    return {"page": page, "size": size}

@app.get("/items")
async def list_items(request, response, pager=Depend(pagination)):
    ...
```

The parameters are validated with the rest of the request and documented on every route that uses the dependency.

## Legacy parameters

Markers written the way sillo has always supported — a default, an `alias`, a `required` flag, and nothing else — keep their original behavior exactly:

```python
page = Query(1)          # int, inferred from the default
q    = Query()           # raw string; None when absent
tags = Query([])         # comma-split: ?tags=a,b,c -> ["a", "b", "c"]
```

They are not routed through Pydantic, which means they also keep the original rough edges: a missing `Query(required=True)` raises and surfaces as a **500**, and a value that fails to coerce does the same. This is deliberate — upgrading sillo must not change how a running application responds.

Supplying a `type=` or any constraint opts an individual parameter into validation. To opt in an entire application at once, including parameters written the old way:

```python
app = silloApp(strict_validation=True)
```

Now `Query(required=True)` with nothing supplied returns a 422 naming the parameter, and `Query(1)` with `?page=abc` returns a 422 instead of a 500. Recommended for new applications.

Under `strict_validation=True` its errors join the unified `{"detail": [...]}` shape used by every other location.

## Generated documentation

Parameter schemas, request bodies, and response schemas in `/openapi.json` are produced from the same Pydantic models that validate the request. A constraint you declare is a constraint that appears in your docs *and* is enforced at runtime:

```python
page = Query(1, type=int, ge=1, le=99, description="Page number")
```

```json
{
  "name": "page",
  "in": "query",
  "required": false,
  "schema": {
    "type": "integer",
    "minimum": 1,
    "maximum": 99,
    "default": 1,
    "description": "Page number"
  }
}
```

## Performance

Every model is compiled once, when the route is registered. Serving a request runs a fixed, small number of `model_validate` calls — one per declared location — with no signature introspection and no recursion, matching the pre-flattened execution plan sillo's dependency injector already uses. Routes that declare no validated parameters skip the machinery entirely.
