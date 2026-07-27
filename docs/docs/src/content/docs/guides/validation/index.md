---
title: Validation
description: sillo validates every request input and every response with Pydantic. The type goes on the declaration, never in a type annotation, and the same declaration drives coercion, validation, and your OpenAPI schema.
---

sillo validates every input a route consumes and, when you ask it to, every response it produces. Pydantic is the engine underneath, but you never restructure your handlers around type annotations — the type goes on the declaration, alongside the rest of the parameter's configuration.

One declaration drives three things: how a value is coerced, how it is validated, and what appears in your OpenAPI document. All three come from the same schema, so your published contract cannot drift away from what your API actually enforces.

##  A complete example

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

##  The two ways to declare input

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

##  A short Pydantic primer

You do not need prior Pydantic experience to use sillo, and these guides teach what you need as you go. If you have never used it, here is the whole idea in one page.

###  Models are schemas

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

###  Coercion: strings become the type you asked for

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

###  Constraints

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

###  Errors describe themselves

When validation fails, Pydantic reports every problem it found, each with a machine-readable `type`, a human-readable `msg`, and a `loc` path to the offending field. sillo prefixes that path with the request location and returns it as a 422. You almost never write error-handling code for input validation — see [Validation errors](/guides/validation/errors/).

##  No type annotations required

sillo never reads annotations on your handler. The type lives on the declaration itself:

```python
page = Query(1, type=int, ge=1, le=100)
```

This is a deliberate design choice, and the practical consequences are worth stating:

- A handler with **no annotations at all** is fully validated.
- Annotations remain entirely yours — for your own type checker, your editor, your team's conventions — with no framework meaning attached.
- The declaration is one object, so a parameter's type, default, constraints, alias, and documentation all live together rather than being split between the signature and the annotation.

Inside your Pydantic models you write ordinary annotations, because that is how a model defines its fields. The two are unrelated.

##  What each guide covers

<div class="not-content">

- **[Parameters](/guides/validation/parameters/)** — query strings, headers, cookies, and path segments. The full type catalog, every constraint, aliases, lists, enums, and the two declaration styles sillo supports.
- **[Request bodies](/guides/validation/request-bodies/)** — `request_model=`, how the validated model reaches your handler, and a thorough tour of `BaseModel`: nested models, custom validators, model configuration, and unions.
- **[Forms and file uploads](/guides/validation/forms-and-files/)** — urlencoded and multipart bodies, the `UploadFile` API, upload validation patterns, and the limits worth knowing.
- **[Response models](/guides/validation/response-models/)** — enforcing your output contract, preventing accidental field leaks, and Pydantic's serialization controls in full.
- **[Validation errors](/guides/validation/errors/)** — the 422 contract, the complete error-type catalog, custom messages, and custom handlers.
- **[Generated documentation](/guides/validation/openapi/)** — how declarations become JSON Schema, and how to enrich what gets published.

</div>

##  Both declaration styles work

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

##  Performance

Every model is compiled once, when the route is registered. Serving a request runs a fixed, small number of validation calls — one per declared location — with no signature introspection and no recursion. Routes that declare nothing skip the machinery entirely.

Measured on the reference implementation: roughly **2.4 µs** to validate one location, of which 1.7 µs is Pydantic itself. Against a typical request that is noise.


##  What validation does not do

Validation checks shape, not meaning. Knowing the difference prevents a
whole category of security bug where a request passes validation and
still should not have been allowed.

A validator confirms `user_id` is an integer between 1 and 2^63. It does
not confirm the requester may read that user. A validator confirms
`amount_cents` is a positive integer. It does not confirm the account has
the funds. A validator confirms `role` is one of three strings. It does
not confirm the caller may assign that role.

The rule: **validation is about the request, authorization is about the
requester, and business rules are about the state of the world.** Each
needs its own layer, and only the first is covered here. See
[Permissions](/guides/permissions/) for the second.

The corollary matters when designing input models. A field a client must
never set — `is_admin`, `account_id`, `price` — should not be in the
input model at all. Pydantic silently ignores undeclared fields, so
omitting them is itself the defence. Adding them "for completeness" and
overwriting them later is one refactor away from a privilege escalation.

##  Where validation happens in the request

Understanding the ordering explains several otherwise confusing
behaviours.

1. Routing matches the path and extracts path parameters
2. Middleware runs, outermost first
3. Dependencies are resolved, including any markers they declare
4. Query, header, cookie, and path values are extracted and validated
5. The body is read and validated
6. Your handler runs
7. `response_model` validates what you returned

Two consequences. Middleware runs **before** validation, so a middleware
reading `request.query_params` sees raw strings, not coerced values —
`request.query_params["page"]` is `"2"`, not `2`. And a validation
failure happens before your handler, so nothing in the handler runs; if
you need to log rejected requests, do it in a
`RequestValidationError` handler, not in the endpoint.

The body is read last, and only if something declared it. A route with no
body declaration never awaits the request body, which is why a handler
that ignores the body is not slowed down by a client sending one.

##  Migrating existing routes

Marker-based validation is opt-in per parameter. A marker constructed the
old way — `Query()`, `Query(1)`, `Query(required=True)` — keeps its
original behaviour exactly, including its quirks. Passing any new
argument, `type=` or a constraint like `ge=`, moves that one parameter to
the validated path.

That means you can migrate a route a parameter at a time, and existing
routes keep working untouched:

```python title="two parameters, two behaviours, one route"
@app.get("/items")
async def items(
    request,
    response,
    page: int = Query(1, type=int, ge=1),       # validated: 422 on ?page=0
    legacy: str = Query("x"),                    # legacy: unvalidated
):
    ...
```

Migrate the parameters that face untrusted input first — anything a
browser or a public client can set. Internal parameters set by your own
frontend can wait.

The behaviour worth migrating soonest is the one where bad input produces
a 500 rather than a 422. A legacy `Query()` whose value fails to coerce
raises a bare `ValueError`, which reaches the framework as an unhandled
exception. Adding `type=` converts that into a clean 422 with a `loc`
telling the client which parameter was wrong.


##  Choosing between markers and models

Both declaration styles are supported, and the choice is not arbitrary.

Reach for **markers** — `Query`, `Header`, `Cookie`, `Path`, `Form`,
`File` — when the input is a handful of scalars belonging to this route
and nowhere else. Pagination, a search term, a sort direction, a feature
flag. The declaration sits in the signature where a reader looking at the
handler will see it, and there is no separate class to keep in sync.

Reach for a **model** — `request_model=` with a `BaseModel` — when the
input is a structure: nested objects, lists of objects, fields with
interdependent validation, or a shape reused across create and update
endpoints. A model gives you cross-field validators, inheritance, and one
place to change when the payload changes.

The dividing line in practice is about five fields. Below that, a
signature reads better than a class; above it, the signature becomes a
wall and the class wins.

Mixing them on one route is normal and expected — path and query
parameters as markers, the body as a model:

```python title="the common combination"
@app.put("/orders/{order_id}", request_model=OrderUpdate)
async def update_order(
    request,
    response,
    order_id: int = Path(type=int),
    notify: bool = Query(False, type=bool),
):
    data = request.validated_data
    ...
```

What does not mix is two declarations of the same body. A route with both
`request_model=` and `Form(...)` markers has two things trying to consume
one request body, and the second gets nothing.
