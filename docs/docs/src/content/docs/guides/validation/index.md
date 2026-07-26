---
title: Validation
description: sillo validates every request input and every response with Pydantic. The type goes on the declaration, never in a type annotation, and the same declaration drives coercion, validation, and your OpenAPI schema.
---

sillo validates every input a route consumes and, when you ask it to, every response it produces. Pydantic is the engine underneath, but you never restructure your handlers around type annotations — the type goes on the declaration, alongside the rest of the parameter's configuration.

One declaration drives three things: how a value is coerced, how it is validated, and what appears in your OpenAPI document. All three come from the same schema, so your published contract cannot drift away from what your API actually enforces.

## A complete example

```python
from pydantic import BaseModel
from sillo import silloApp, Depend, Path, Query

class UserCreate(BaseModel):
    name: str
    email: str
    age: int

class UserOut(BaseModel):
    id: int
    name: str

app = silloApp()

@app.post("/teams/{team_id}/users",
          request_model=UserCreate,      # JSON body
          response_model=UserOut)        # shapes the reply
async def create_user(request, response, user,          # the validated body
                      team_id=Path(type=int),           # from the URL
                      notify=Query(False, type=bool),   # ?notify=true
                      db=Depend(get_db)):               # a dependency
    return await save(user, team_id, db)
```

Bad input never reaches the handler. It returns **422** naming exactly what failed:

```json
{
  "detail": [
    {"loc": ["query", "notify"], "msg": "Input should be a valid boolean", "type": "bool_parsing"},
    {"loc": ["body", "email"], "msg": "Field required", "type": "missing"}
  ]
}
```

## The two ways to declare input

There is one rule to remember:

| | How to declare it |
| --- | --- |
| **JSON body** | `request_model=Model` on the decorator |
| **Everything else** | a marker on the parameter |

Only the JSON body is a decorator argument. Query strings, headers, cookies, path segments, form fields, and file uploads are all parameter markers, placed as the parameter's default value:

```python
from sillo import Query, Header, Cookie, Path, Form, File

page    = Query(1, type=int, ge=1)
token   = Header(type=str)
sid     = Cookie(None, type=str)
user_id = Path(type=int)
title   = Form(type=str)
avatar  = File(...)
```

The first two handler parameters are always `request` and `response`, exactly as they have always been.

## A short Pydantic primer

You do not need prior Pydantic experience to use sillo, and these guides teach what you need as you go. If you have never used it, here is the whole idea in one page.

### Models are schemas

A Pydantic model is a class describing the shape of some data. You declare fields with Python type annotations, and Pydantic turns that declaration into a validator:

```python
from pydantic import BaseModel

class UserCreate(BaseModel):
    name: str
    email: str
    age: int
```

Note the distinction that matters here: **annotations inside a model are how you define the model's fields**, which is ordinary Python. sillo never reads annotations on your *handler* — that is a separate thing, covered below.

Validating produces a real instance with real attributes:

```python
user = UserCreate.model_validate({"name": "Ada", "email": "a@b.co", "age": 36})
user.name        # "Ada"  — a str, guaranteed
user.age         # 36     — an int, guaranteed
```

Fields with no default are required. Give one to make a field optional:

```python
class UserCreate(BaseModel):
    name: str                       # required
    nickname: str = ""              # optional, defaults to ""
    bio: str | None = None          # optional, may be null
```

### Coercion: strings become the type you asked for

This is why Pydantic fits an HTTP framework so well. Everything arriving over HTTP is text — a query string is text, a header is text, a form field is text. Pydantic converts it:

```python
UserCreate.model_validate({"name": "Ada", "email": "a@b.co", "age": "36"})
#                                                                   ^^^^ a string
# user.age == 36, an int
```

That conversion is called *lax mode*, and it is the default. It is deliberately not a free-for-all — it converts where the intent is unambiguous and refuses where it is not:

| Input | Declared as | Result |
| --- | --- | --- |
| `"36"` | `int` | `36` |
| `"1.5"` | `float` | `1.5` |
| `"abc"` | `int` | error — `int_parsing` |
| `36` | `str` | error — `string_type` |
| `"true"`, `"1"`, `"yes"`, `"on"`, `"t"`, `"y"` | `bool` | `True` |
| `"false"`, `"0"`, `"no"`, `"off"`, `"f"`, `"n"` | `bool` | `False` |
| `"maybe"` | `bool` | error — `bool_parsing` |
| `"2024-01-02T03:04:05"` | `datetime` | a real `datetime` |
| `"123e4567-e89b-…"` | `UUID` | a real `UUID` |

Note that int-to-str is an error. Pydantic v2 will widen a string into a number when the string clearly *is* a number, but will not silently stringify data — that direction loses information and hides bugs.

Pass `strict=True` on any marker or field to disable coercion entirely and require the exact type.

### Constraints

Beyond the type, you can constrain the value. In a model these go on `Field`:

```python
from pydantic import BaseModel, Field

class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=50)
    age: int = Field(ge=0, le=150)
    slug: str = Field(pattern=r"^[a-z-]+$")
```

On a sillo marker they are plain keyword arguments:

```python
page = Query(1, type=int, ge=1, le=100)
slug = Query(type=str, min_length=3, pattern=r"^[a-z-]+$")
```

The full set is `gt`, `ge`, `lt`, `le`, `multiple_of`, `min_length`, `max_length`, `pattern`, and `strict`. They are covered in depth in [Parameters](/guides/validation/parameters/).

### Errors describe themselves

When validation fails, Pydantic reports every problem it found, each with a machine-readable `type`, a human-readable `msg`, and a `loc` path to the offending field. sillo prefixes that path with the request location and returns it as a 422. You almost never write error-handling code for input validation — see [Validation errors](/guides/validation/errors/).

## No type annotations required

sillo never reads annotations on your handler. The type lives on the declaration itself:

```python
page = Query(1, type=int, ge=1, le=100)
```

This is a deliberate design choice, and the practical consequences are worth stating:

- A handler with **no annotations at all** is fully validated.
- Annotations remain entirely yours — for your own type checker, your editor, your team's conventions — with no framework meaning attached.
- The declaration is one object, so a parameter's type, default, constraints, alias, and documentation all live together rather than being split between the signature and the annotation.

Inside your Pydantic models you write ordinary annotations, because that is how a model defines its fields. The two are unrelated.

## What each guide covers

<div class="not-content">

- **[Parameters](/guides/validation/parameters/)** — query strings, headers, cookies, and path segments. The full type catalog, every constraint, aliases, lists, enums, and the two declaration styles sillo supports.
- **[Request bodies](/guides/validation/request-bodies/)** — `request_model=`, how the validated model reaches your handler, and a thorough tour of `BaseModel`: nested models, custom validators, model configuration, and unions.
- **[Forms and file uploads](/guides/validation/forms-and-files/)** — urlencoded and multipart bodies, the `UploadFile` API, upload validation patterns, and the limits worth knowing.
- **[Response models](/guides/validation/response-models/)** — enforcing your output contract, preventing accidental field leaks, and Pydantic's serialization controls in full.
- **[Validation errors](/guides/validation/errors/)** — the 422 contract, the complete error-type catalog, custom messages, and custom handlers.
- **[Generated documentation](/guides/validation/openapi/)** — how declarations become JSON Schema, and how to enrich what gets published.

</div>

## Both declaration styles work

sillo has always let you declare a parameter with just a default value, inferring the type from it. That still works exactly as it always did:

```python
page = Query(1)        # int, inferred from the default
q    = Query()         # raw string; None when absent
tags = Query([])       # comma-split: ?tags=a,b,c -> ["a", "b", "c"]
```

Adding a `type=` or any constraint moves the parameter onto the fully validated path, where a bad value returns a 422 instead of a server error:

```python
page = Query(1, type=int, ge=1)
```

Both styles coexist in the same application, and even in the same handler. Documentation-only keywords such as `description=` never change which path a parameter takes, so annotating an endpoint for your docs can never alter how it behaves.

To validate everything in an application, including parameters written the short way:

```python
app = silloApp(strict_validation=True)
```

## Performance

Every model is compiled once, when the route is registered. Serving a request runs a fixed, small number of validation calls — one per declared location — with no signature introspection and no recursion. Routes that declare nothing skip the machinery entirely.

Measured on the reference implementation: roughly **2.4 µs** to validate one location, of which 1.7 µs is Pydantic itself. Against a typical request that is noise.
