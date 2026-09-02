---
title: Handlers
description: "Everything a sillo handler does: the context argument, how return values become responses, path/query/body access, status codes, errors, and dependency injection."
head:
- tag: meta
  attrs:
    property: og:title
    content: Handlers in sillo
- tag: meta
  attrs:
    property: og:description
    content: "The handler contract in sillo: the context, return values, errors, and dependency injection."
---

#  Handlers

A *handler* is the function sillo calls when a request matches a route. It is
where your application logic lives: read the request, do the work, return the
answer. Almost everything else in sillo (routing, middleware, dependency
injection, serialization) exists to get the right request to the right handler
and turn its result into bytes on the wire.

This page covers the handler contract end to end: the context every handler
receives, the many shapes a return value can take, how to read path/query/body
data, how to set status codes and headers, how to raise errors, and how to pull
dependencies in.

##  The smallest useful form

```python
from sillo import SilloApp, HttpContext

app = SilloApp()

@app.get("/")
async def index(ctx: HttpContext):
    return "Hello, world!"
```

Two things to notice:

1. The handler is `async` and takes **one positional parameter**: the context.
   Its name is yours to choose — `ctx` is the convention — but it is always
   first, and it is always there.
2. Returning a plain value is enough. sillo encodes it and sends a `200` — a
   `str` as `text/plain`, a `dict` or `list` as `application/json`. That is the
   default way to answer a request, not a shortcut for small ones. You only
   need a response builder when you want something the value cannot carry: a
   different status, a header, a cookie, a stream.

##  The context

Every handler receives an `HttpContext`: the method, URL, headers, query,
cookies, body, client address, and auth/session state, all on one object. It is
the whole input side of the request, and it is documented in full under
[Request Information](/v1.0/guides/request-info/).

```python
from sillo import HttpContext

@app.get("/")
async def index(ctx: HttpContext):
    return {"method": ctx.method}
```

Type annotations are optional but recommended. They give you IDE autocomplete
and let static analyzers check your code. They do not change runtime behavior.

There is no second parameter for the response, and nothing on `ctx` that
writes one — the context describes the *request*. You answer by returning:

```python
return {"ok": True}             # 200, application/json
```

When the value alone is not enough, return a response object built by one of
the free functions in [`sillo.responses`](/v1.0/guides/sending-responses/).
Anything you want to set on it — status, headers, cookies — is a method call
on that result:

```python
from sillo import json, redirect

redirect("/elsewhere")                                    # a 302
json({"id": 7}).status(201).set_header("X-Trace", trace)  # a 201 with a header
```

<aside type="tip" title="Where the names come from">
`json`, `text` and the rest are re-exported from the root package, so
`from sillo import json` and `from sillo.responses import json` are the same
function. Import the module instead — `from sillo import responses`, then
`responses.json(...)` — in a file that also needs the standard library's
`json` or `html`.
</aside>

##  Registering handlers

The decorator form is the common case:

```python
from sillo import HttpContext

@app.get("/items")
@app.post("/items")
@app.put("/items/{id}")
@app.delete("/items/{id}")
@app.patch("/items/{id}")
@app.options("/items")
@app.head("/items")
async def items(ctx: HttpContext):
    ...
```

For finer control (or when building routes programmatically) use the `Route`
class and `app.add_route`:

```python
from sillo.core.routing import Route
from sillo import HttpContext

async def dynamic_handler(ctx: HttpContext):
    return "Hello, world!"

# Methods defaults to ["GET"] when omitted
app.add_route(Route("/dynamic", dynamic_handler))

# explicit methods
app.add_route(Route("/dynamic", dynamic_handler, methods=["GET", "POST"]))
```

##  Reading the request

###  Path parameters

Declare a `{name}` segment in the path; sillo binds the matched value to a handler parameter of the same name.

```python
from sillo import HttpContext

@app.get("/users/{user_id}")
async def get_user(ctx: HttpContext, user_id):
    return {"id": user_id}
```

For type-safe binding, append a converter: `{name:int}`, `{name:float}`, `{name:str}` (default), or `{name:path}` for catch-all segments.

```python
from sillo import HttpContext

@app.get("/users/{user_id:int}")
async def get_user_int(ctx: HttpContext, user_id: int):
    # user_id is already an int here
    return {"id": user_id, "type": type(user_id).__name__}
```

Available converters: `str`, `int`, `float`, `path`. Register your own with `register_url_convertor` from `sillo.converters`.

###  Query parameters

Read them off `ctx.query_params` (a dict-like, case-preserving object), or
(preferably) declare them with the `Query` extractor so sillo does type
conversion for you.

```python
from sillo import HttpContext

@app.get("/search")
async def search(ctx: HttpContext, q: str = Query(""), page: int = Query(1), tag: list = Query(None)):
    return {"q": q, "page": page, "tag": tag}
```

Imperative access is also available:

```python
from sillo import HttpContext

@app.get("/search")
async def search_raw(ctx: HttpContext):
    q = ctx.query_params.get("q", "")
    page = int(ctx.query_params.get("page", 1))
    tags = ctx.query_params.getlist("tag")
    return {"q": q, "page": page, "tags": tags}
```

See [Request Parameters](/v1.0/guides/request-parameters/) for the full `Query`/`Header`/`Cookie` reference.

###  Request body

The body is parsed lazily the first time you ask for it:

```python
from sillo import HttpContext

@app.post("/data")
async def process_data(ctx: HttpContext):
    json_data = await ctx.json     # parsed JSON (dict/list)
    form_data = await ctx.form     # multipart / urlencoded -> FormData
    raw_bytes = await ctx.body     # raw bytes
    text      = await ctx.text     # decoded text
    return {"keys": list(json_data.keys()) if isinstance(json_data, dict) else None}
```

`ctx.json`, `ctx.form`, `ctx.body`, `ctx.text`, and `ctx.files` are all
**awaitable properties**, `await` them once; the result is cached for the
request.

For validated bodies, set `request_model` on the route (or `app.post(...)`) with a Pydantic model; the validated instance is available as `ctx.validated_data`:

```python
from pydantic import BaseModel
from sillo import SilloApp, HttpContext, json

app = SilloApp()

class CreateItem(BaseModel):
    name: str
    price: float

@app.post("/items", request_model=CreateItem)
async def create_item(ctx: HttpContext):
    item = ctx.validated_data      # a CreateItem instance
    return json({"created": item.model_dump()}, status_code=201)
```

##  Returning responses

Three shapes, in the order you should reach for them:

###  1. The value itself — the default

```python
from sillo import HttpContext

@app.get("/ping")
async def ping(ctx: HttpContext):
    return {"status": "ok"}     # -> 200 application/json
```

Dicts, lists, tuples, sets, numbers, booleans, `None`, Pydantic models,
dataclasses and `Decimal` are sent as JSON. A `str` — and anything the encoder
reduces to one, such as a `datetime`, a `UUID` or an `Enum` member — is sent as
`text/plain`. [Sending Responses](/v1.0/guides/sending-responses/) has the full
table.

This is the shape most handlers should have. A `response_model` still applies,
so it stays safe as the codebase grows.

###  2. A response builder — when the value is not enough

For a status other than 200, a header, a cookie, or a content type the encoder
would not pick, return `json(...)`, `html(...)`, `text(...)`, `file(...)`, or
`redirect(...)`:

```python
from sillo import HttpContext, json

@app.get("/reports/{id}")
async def report(ctx: HttpContext, id: int):
    return (
        json({"report": id})
        .status(200)
        .set_header("X-Report-Id", str(id))
    )
```

The builder comes first and the setters chain off it, because the setters are
methods on the response the builder returned. There is nothing to configure
before you have a body.

Note that a handler returning a built response is **not** filtered by a
`response_model` — building the response says the body is your business.

###  3. A raw `BaseResponse` subclass

Return an instance of `JSONResponse`, `HTMLResponse`, `PlainTextResponse`, `FileResponse`, `StreamingResponse`, or `RedirectResponse` directly:

```python
from sillo.core.http.response import JSONResponse
from sillo import HttpContext

@app.get("/raw")
async def raw(ctx: HttpContext):
    return JSONResponse({"hello": "world"}, status_code=201)
```

##  Status codes and headers

A returned value is always a `200`. Anything else is a builder, because the
status is part of the response and there is nowhere on `ctx` to put it:

```python
from sillo import HttpContext, json

@app.get("/statuses")
async def statuses(ctx: HttpContext):
    return {"ok": True}                                # 200
    return json({"error": "Not found"}, status_code=404)
```

Prefer named constants from `sillo.http.status` for readability:

```python
from sillo.http.status import HTTP_201_CREATED, HTTP_404_NOT_FOUND
from sillo import HttpContext, json

@app.post("/things")
async def make_thing(ctx: HttpContext):
    return json({"id": 1}, status_code=HTTP_201_CREATED)
```

Set ad-hoc headers with `.set_header(...)` and cookies with `.set_cookie(...)`. See [Headers](/v1.0/guides/headers/) and [Cookies](/v1.0/guides/cookies/).

##  Raising errors

Raise `HTTPException` to short-circuit with a clean status + body:

```python
from sillo.exceptions import HTTPException
from sillo import HttpContext

@app.get("/users/{user_id:int}")
async def get_user(ctx: HttpContext, user_id: int):
    if user_id > 1000:
        raise HTTPException(HTTP_404_NOT_FOUND, f"User {user_id} not found")
    return {"id": user_id}
```

Uncaught exceptions become `500` responses in production. Register handlers for your own exception types with `app.add_exception_handler`:

```python
from sillo.exceptions import HTTPException
from sillo import HttpContext, json

@app.add_exception_handler(HTTPException)
async def http_error(ctx: HttpContext, exc):
    return json(
        {"error": exc.detail, "status_code": exc.status_code},
        status_code=exc.status_code,
    )
```

See [Error Handling](/v1.0/guides/error-handling/) for the full picture, including `add_exception_handler` with status-code keys and validation-error mapping.

##  Pulling in dependencies

Handlers declare *what they need*; sillo resolves it. Mark a parameter with `Depend(...)`:

```python
from sillo import HttpContext, Depend

def get_current_user(ctx: HttpContext):
    token = ctx.headers.get("Authorization", "").removeprefix("Bearer ")
    if not token:
        from sillo.exceptions import HTTPException
        raise HTTPException(401, "Missing token")
    return {"user_id": "u_1"}

@app.get("/me")
async def me(ctx: HttpContext, user: dict = Depend(get_current_user)):
    return user
```

Dependencies can be nested, cached per request, and clean up after themselves
via async generators. The full system (`get_context=True`, sub-dependencies,
caching, generator teardown) is documented in [Dependency
Injection](/v1.0/guides/dependency-injection/).

<aside type="caution" title="No `Context()` and no `scope=` on Depend">
Two patterns you may see in older examples are not part of sillo's API: `Context().request` for injecting the request, and `Depend(fn, scope="request")`. Take a plain `ctx` parameter in the dependency, or use `Depend(get_context=True)`, instead. `Depend` accepts only `dependency` and `get_context`.
</aside>

##  A complete handler

```python
from pydantic import BaseModel
from sillo import SilloApp, HttpContext, json, Query, Depend
from sillo.http.status import HTTP_201_CREATED, HTTP_404_NOT_FOUND
from sillo.exceptions import HTTPException

app = SilloApp()

class ItemIn(BaseModel):
    name: str
    price: float

def load_user(ctx: HttpContext):
    # pretend auth
    return {"user_id": "u_1"}

@app.post("/items", request_model=ItemIn)
async def create_item(
    ctx: HttpContext,
    item: ItemIn = Depend(lambda: ctx.validated_data),
    user: dict = Depend(load_user),
    dry_run: bool = Query(False),
):
    if dry_run:
        return {"would_create": item.model_dump(), "as": user["user_id"]}

    # ... persist item ...
    return json(
        {"created": item.model_dump(), "by": user["user_id"]},
        status_code=HTTP_201_CREATED,
    )
```

This one handler demonstrates: path-less body validation (`request_model`), an injected dependency, a query flag, and an explicit status code.

##  Works with

- [Routing](/v1.0/guides/routing/): path syntax, converters, `name=`, and route
  options
- [Request Information](/v1.0/guides/request-info/): every `ctx.*` attribute
- [Request Parameters](/v1.0/guides/request-parameters/): `Query` / `Header` /
  `Cookie`
- [Sending Responses](/v1.0/guides/sending-responses/): every response builder in
  depth
- [Dependency Injection](/v1.0/guides/dependency-injection/): `Depend`, nesting,
  caching, teardown

##  Related topics

- [Error Handling](/v1.0/guides/error-handling/): `HTTPException` and custom
  handlers
- [Routers & Sub-Apps](/v1.0/guides/routers-and-subapps/): group related function
  handlers behind a prefix
- [Middleware](/v1.0/guides/middleware/): logic that wraps handlers for every
  request


##  Keep handlers thin

A handler has one job: turn an HTTP request into an HTTP response. Every
line in it that is not about HTTP belongs somewhere else.

The reason is testability. A handler that computes a billing total needs
an HTTP request to test; a function that computes a billing total needs
two numbers. The second is where the bugs are, and it should be testable
without a client.

```python title="the shape that scales"
from sillo import HttpContext, json

@app.post("/orders", request_model=OrderCreate)
async def create_order(ctx: HttpContext):
    order = await orders.place(ctx.user.id, ctx.validated_data)
    return json(OrderOut.model_validate(order).model_dump(), status_code=201)
```

Three lines: parse, delegate, respond. `orders.place` knows nothing about
HTTP and can be tested, reused by a queue worker, and called from a CLI
command.

The signal that a handler has grown past this is a `try/except` around
business logic, or a second database query that exists to make a decision
rather than to fetch what the response returns.

##  Handler errors

An exception that escapes a handler becomes a 500 through the error
middleware. That is the right default for genuine bugs and the wrong
answer for expected failures.

Raise `HTTPException` for anything the client caused. It carries the status and
short-circuits cleanly:

```python
if order.owner_id != ctx.user.id:
    raise HTTPException(status_code=403, detail="not your order")
```

Return a response directly when you want full control over the body.
Both are fine; mixing them arbitrarily within one codebase is what makes
error shapes inconsistent, so pick a convention.

The one thing to avoid is catching broadly inside a handler and returning
a 200 with an error field. That defeats every status-code-based
behaviour a client, a proxy, or your own monitoring relies on.

##  Sync handlers

A handler may be a plain `def`. sillo runs it in a thread so it does not block
the loop, which is correct, and slower than an async handler by the cost of a
thread hop.

Use one when you are calling a synchronous library and the alternative is
`run_in_threadpool` on every line. Otherwise write `async def`: everything
in the framework, the ORM, and the HTTP client is async, and an async
handler that awaits them is both faster and simpler.

What you must never do is a blocking call inside an `async def`. That has
neither the thread nor the await, and it stalls every concurrent request
in the process. See [Concurrency](/v1.0/guides/concurrency/).


##  What a handler receives

Every handler takes the context as its first parameter. Anything after it comes
from the framework: path parameters, validated markers, dependencies, and (for
`request_model=` routes) the validated body.

The context carries the input: path and query parameters, headers, cookies, the
body, the client address, and `ctx.state` for anything middleware attached. The
output side is not a parameter at all — it is the value you return.

Return the value. A dict, a list, a Pydantic model: sillo encodes it and sends
a `200`, and a `response_model` still shapes it. Build a response with `json`,
`text`, `html`, `redirect` or the streaming and file variants when you need
something the value cannot carry — a different status, a header, a cookie. Most
handlers need the first; the branch that 404s needs the second, and the two mix
freely in one function.

##  Naming and organisation

Handler names appear in `sillo urls`, in generated documentation, and in
tracebacks, so they are worth choosing. Name for the action (`create_order`,
`list_orders`, `cancel_order`) not for the mechanism.

Group handlers by resource in modules that mirror your URLs, and mount
them with [routers](/v1.0/guides/routers-and-subapps/). A single file of two
hundred handlers is navigable by search and by nothing else, and the
merge conflicts alone justify splitting it well before that point.


##  Idempotency

`GET`, `HEAD`, `PUT`, and `DELETE` are expected to be idempotent. Calling them
twice has the same effect as calling them once. Clients, proxies, and retry
logic all rely on that, and a `GET` with a side effect breaks assumptions well
outside your codebase.

`POST` is not idempotent by definition, which is why a retried `POST` can
create two orders. Where that matters, accept an idempotency key from the
client and store the result against it, returning the stored response on
a repeat rather than doing the work twice.
