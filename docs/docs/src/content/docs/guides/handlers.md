---
title: Handlers
description: "Everything a sillo handler does: the (request, response) contract, how return values become responses, path/query/body access, status codes, errors, and dependency injection."
head:
- tag: meta
  attrs:
    property: og:title
    content: Handlers in sillo
- tag: meta
  attrs:
    property: og:description
    content: "The handler contract in sillo: request/response, return values, errors, and dependency injection."
---

#  Handlers

A *handler* is the function sillo calls when a request matches a route. It is where your application logic lives: read the request, do the work, return a response. Almost everything else in sillo — routing, middleware, dependency injection, serialization — exists to get the right request to the right handler and turn its result into bytes on the wire.

This page covers the handler contract end to end: the two arguments every handler receives, the many shapes a return value can take, how to read path/query/body data, how to set status codes and headers, how to raise errors, and how to pull dependencies in.

##  The smallest useful form

```python
from sillo import SilloApp

app = SilloApp()

@app.get("/")
async def index(request, response):
    return "Hello, world!"
```

Two things to notice:

1. The handler is `async` and takes **at least two positional parameters** — `request` and `response`. Their names are yours to choose (`request, response` works too), but order matters: request first, response second.
2. Returning a plain `str` is enough. sillo wraps it in a `200 OK` JSON-or-text response for you. For anything beyond the simplest case, use the `response` object.

<aside type="tip" title="Name them what you like">
The framework binds the first two handler parameters by position, not by name. `async def index(request, response)` and `async def index(request, response)` are identical. Pick names that read well in your codebase.
</aside>

##  The request and response objects

Every handler receives:

- **`request`** — a `sillo.http.Request` instance carrying the method, URL, headers, query, cookies, body, client address, and auth/session state. See [Request Information](/guides/request-info/).
- **`response`** — a `sillo.http.response.Responder` (also importable as `Response`) — a fluent builder you use to produce JSON, HTML, files, redirects, headers, and cookies. See [Sending Responses](/guides/sending-responses/).

```python
from sillo.core.http import Request, Response

@app.get("/")
async def index(request: Request, response: Response):
    return response.json({"method": request.method})
```

Type annotations are optional but recommended — they give you IDE autocomplete and let static analyzers check your code. They do not change runtime behavior.

##  Registering handlers

The decorator form is the common case:

```python
@app.get("/items")
@app.post("/items")
@app.put("/items/{id}")
@app.delete("/items/{id}")
@app.patch("/items/{id}")
@app.options("/items")
@app.head("/items")
async def items(request, response):
    ...
```

For finer control — or when building routes programmatically — use the `Route` class and `app.add_route`:

```python
from sillo.core.routing import Route

async def dynamic_handler(request, response):
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
@app.get("/users/{user_id}")
async def get_user(request, response, user_id):
    return {"id": user_id}
```

For type-safe binding, append a converter: `{name:int}`, `{name:float}`, `{name:str}` (default), or `{name:path}` for catch-all segments.

```python
@app.get("/users/{user_id:int}")
async def get_user_int(request, response, user_id: int):
    # user_id is already an int here
    return {"id": user_id, "type": type(user_id).__name__}
```

Available converters: `str`, `int`, `float`, `path`. Register your own with `register_url_convertor` from `sillo.converters`.

###  Query parameters

Read them off `request.query_params` (a dict-like, case-preserving object), or — preferably — declare them with the `Query` extractor so sillo does type conversion for you.

```python
@app.get("/search")
async def search(request, response, q: str = Query(""), page: int = Query(1), tag: list = Query(None)):
    return {"q": q, "page": page, "tag": tag}
```

Imperative access is also available:

```python
@app.get("/search")
async def search_raw(request, response):
    q = request.query_params.get("q", "")
    page = int(request.query_params.get("page", 1))
    tags = request.query_params.getlist("tag")
    return {"q": q, "page": page, "tags": tags}
```

See [Request Parameters](/guides/request-parameters/) for the full `Query`/`Header`/`Cookie` reference.

###  Request body

The body is parsed lazily the first time you ask for it:

```python
@app.post("/data")
async def process_data(request, response):
    json_data = await request.json     # parsed JSON (dict/list)
    form_data = await request.form     # multipart / urlencoded -> FormData
    raw_bytes = await request.body     # raw bytes
    text      = await request.text     # decoded text
    return {"keys": list(json_data.keys()) if isinstance(json_data, dict) else None}
```

`request.json`, `request.form`, `request.body`, `request.text`, and `request.files` are all **awaitable properties** — `await` them once; the result is cached for the request.

For validated bodies, set `request_model` on the route (or `app.post(...)`) with a Pydantic model; the validated instance is available as `request.validated_data`:

```python
from pydantic import BaseModel
from sillo import SilloApp

app = SilloApp()

class CreateItem(BaseModel):
    name: str
    price: float

@app.post("/items", request_model=CreateItem)
async def create_item(request, response):
    item = request.validated_data      # a CreateItem instance
    return response.json({"created": item.model_dump()}, status_code=201)
```

##  Returning responses

You can return a handler result in several ways, from least to most explicit:

###  1. A plain value (auto-serialized)

```python
@app.get("/ping")
async def ping(request, response):
    return {"status": "ok"}     # -> 200 application/json
```

sillo JSON-encodes dicts, lists, and most types. Primitives become JSON scalars. This is the fastest way to write a small endpoint.

###  2. The `response` builder

For control over status, headers, or content type, return `response.json(...)`, `response.html(...)`, `response.text(...)`, `response.file(...)`, or `response.redirect(...)`:

```python
@app.get("/reports/{id}")
async def report(request, response, id: int):
    return (
        response
        .status(200)
        .set_header("X-Report-Id", str(id))
        .json({"report": id})
    )
```

Methods are chainable. You must set a *type* (`.json()`, `.html()`, …) before calling `.set_cookie()`/`.set_header()`/`.status()`, because those operate on an already-built response.

###  3. A raw `BaseResponse` subclass

Return an instance of `JSONResponse`, `HTMLResponse`, `PlainTextResponse`, `FileResponse`, `StreamingResponse`, or `RedirectResponse` directly:

```python
from sillo.core.http.response import JSONResponse

@app.get("/raw")
async def raw(request, response):
    return JSONResponse({"hello": "world"}, status_code=201)
```

##  Status codes and headers

```python
@app.get("/statuses")
async def statuses(request, response):
    # 2xx
    return response.json({"ok": True}, status_code=200)
    # 4xx / 5xx
    return response.json({"error": "Not found"}, status_code=404)
```

Prefer named constants from `sillo.http.status` for readability:

```python
from sillo.http.status import HTTP_201_CREATED, HTTP_404_NOT_FOUND

@app.post("/things")
async def make_thing(request, response):
    return response.json({"id": 1}, status_code=HTTP_201_CREATED)
```

Set ad-hoc headers with `.set_header(...)` and cookies with `.set_cookie(...)`. See [Headers](/guides/headers/) and [Cookies](/guides/cookies/).

##  Raising errors

Raise `HTTPException` to short-circuit with a clean status + body:

```python
from sillo.exceptions import HTTPException

@app.get("/users/{user_id:int}")
async def get_user(request, response, user_id: int):
    if user_id > 1000:
        raise HTTPException(HTTP_404_NOT_FOUND, f"User {user_id} not found")
    return {"id": user_id}
```

Uncaught exceptions become `500` responses in production. Register handlers for your own exception types with `app.add_exception_handler`:

```python
from sillo.exceptions import HTTPException

@app.add_exception_handler(HTTPException)
async def http_error(request, response, exc):
    return response.json(
        {"error": exc.detail, "status_code": exc.status_code},
        status_code=exc.status_code,
    )
```

See [Error Handling](/guides/error-handling/) for the full picture, including `add_exception_handler` with status-code keys and validation-error mapping.

##  Pulling in dependencies

Handlers declare *what they need*; sillo resolves it. Mark a parameter with `Depend(...)`:

```python
from sillo import Depend

def get_current_user(request):
    token = request.headers.get("Authorization", "").removeprefix("Bearer ")
    if not token:
        from sillo.exceptions import HTTPException
        raise HTTPException(401, "Missing token")
    return {"user_id": "u_1"}

@app.get("/me")
async def me(request, response, user: dict = Depend(get_current_user)):
    return response.json(user)
```

Dependencies can be nested, cached per request, and clean up after themselves via async generators. The full system — `get_request=True`, sub-dependencies, caching, generator teardown — is documented in [Dependency Injection](/guides/dependency-injection/).

<aside type="caution" title="No `Context()` and no `scope=` on Depend">
Two patterns you may see in older examples are not part of sillo's API: `Context().request` for injecting the request, and `Depend(fn, scope="request")`. Use a plain `request` parameter in the dependency, or `Depend(get_request=True)`, instead. `Depend` accepts only `dependency` and `get_request`.
</aside>

##  A complete handler

```python
from pydantic import BaseModel
from sillo import SilloApp, Query, Depend
from sillo.http.status import HTTP_201_CREATED, HTTP_404_NOT_FOUND
from sillo.exceptions import HTTPException

app = SilloApp()

class ItemIn(BaseModel):
    name: str
    price: float

def load_user(request):
    # pretend auth
    return {"user_id": "u_1"}

@app.post("/items", request_model=ItemIn)
async def create_item(
    request,
    response,
    item: ItemIn = Depend(lambda: request.validated_data),
    user: dict = Depend(load_user),
    dry_run: bool = Query(False),
):
    if dry_run:
        return response.json({"would_create": item.model_dump(), "as": user["user_id"]})

    # ... persist item ...
    return response.json(
        {"created": item.model_dump(), "by": user["user_id"]},
        status_code=HTTP_201_CREATED,
    )
```

This one handler demonstrates: path-less body validation (`request_model`), an injected dependency, a query flag, and an explicit status code.

##  Works with

- [Routing](/guides/routing/) — path syntax, converters, `name=`, and route options
- [Request Information](/guides/request-info/) — every `request.*` attribute
- [Request Parameters](/guides/request-parameters/) — `Query` / `Header` / `Cookie`
- [Sending Responses](/guides/sending-responses/) — the `response` builder in depth
- [Dependency Injection](/guides/dependency-injection/) — `Depend`, nesting, caching, teardown

##  Related topics

- [Error Handling](/guides/error-handling/) — `HTTPException` and custom handlers
- [Routers & Sub-Apps](/guides/routers-and-subapps/) — group related function handlers behind a prefix
- [Middleware](/guides/middleware/) — logic that wraps handlers for every request


##  Keep handlers thin

A handler has one job: turn an HTTP request into an HTTP response. Every
line in it that is not about HTTP belongs somewhere else.

The reason is testability. A handler that computes a billing total needs
an HTTP request to test; a function that computes a billing total needs
two numbers. The second is where the bugs are, and it should be testable
without a client.

```python title="the shape that scales"
@app.post("/orders", request_model=OrderCreate)
async def create_order(request, response):
    order = await orders.place(request.user.id, request.validated_data)
    return response.json(OrderOut.model_validate(order).model_dump(), status_code=201)
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

Raise `HTTPException` for anything the client caused — it carries the
status and short-circuits cleanly:

```python
if order.owner_id != request.user.id:
    raise HTTPException(status_code=403, detail="not your order")
```

Return a response directly when you want full control over the body.
Both are fine; mixing them arbitrarily within one codebase is what makes
error shapes inconsistent, so pick a convention.

The one thing to avoid is catching broadly inside a handler and returning
a 200 with an error field. That defeats every status-code-based
behaviour a client, a proxy, or your own monitoring relies on.

##  Sync handlers

A handler may be a plain `def`. sillo runs it in a thread so it does not
block the loop — which is correct, and slower than an async handler by
the cost of a thread hop.

Use one when you are calling a synchronous library and the alternative is
`run_in_threadpool` on every line. Otherwise write `async def`: everything
in the framework, the ORM, and the HTTP client is async, and an async
handler that awaits them is both faster and simpler.

What you must never do is a blocking call inside an `async def`. That has
neither the thread nor the await, and it stalls every concurrent request
in the process. See [Concurrency](/guides/concurrency/).


##  What a handler receives

Every handler takes `request` and `response` as its first two parameters.
Anything after them comes from the framework: validated markers,
dependencies, and — for `request_model=` routes — the validated body.

`request` carries the input: path and query parameters, headers, cookies,
the body, the client address, and `request.state` for anything middleware
attached. `response` is a factory for building replies — `response.json`,
`response.text`, `response.html`, `response.redirect`, and the streaming
and file variants.

Returning a response object is explicit and preferred. Returning a plain
dict or list also works and is encoded to JSON with a 200; that shortcut
is convenient and gives up control over the status and headers, which is
why it stops being appropriate the moment an endpoint has more than one
outcome.

##  Naming and organisation

Handler names appear in `sillo urls`, in generated documentation, and in
tracebacks, so they are worth choosing. Name for the action —
`create_order`, `list_orders`, `cancel_order` — not for the mechanism.

Group handlers by resource in modules that mirror your URLs, and mount
them with [routers](/guides/routers-and-subapps/). A single file of two
hundred handlers is navigable by search and by nothing else, and the
merge conflicts alone justify splitting it well before that point.


##  Idempotency

`GET`, `HEAD`, `PUT`, and `DELETE` are expected to be idempotent —
calling them twice has the same effect as calling them once. Clients,
proxies, and retry logic all rely on that, and a `GET` with a side effect
breaks assumptions well outside your codebase.

`POST` is not idempotent by definition, which is why a retried `POST` can
create two orders. Where that matters, accept an idempotency key from the
client and store the result against it, returning the stored response on
a repeat rather than doing the work twice.
