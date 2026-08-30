"""
sillo — The Platform for Python Backends

A modern ASGI web framework. Async-native. Zero boilerplate validation.
Built-in DI with pre-flattened execution plans. Everything you need — routing,
middleware, auth, CORS, CSRF, sessions and caching — ships as first-party.

Key Features:
- ASGI-based, async/await throughout
- One context object per connection: HttpContext for HTTP, WebSocketContext for
  sockets, both derived from BaseContext
- Free response builders: json, html, text, redirect, file, stream
- Dependency injection with pre-flattened execution plan (zero recursion at runtime)
- Pydantic validation on every input and output — no type annotations needed
- Middleware system: CORS, CSRF, sessions, auth, rate limiting, compression
- Depend(get_request=True) to inject the context into any dependency
- GraphQL through the sillo-graphql package, importable as sillo.graphql
- WebSocket support with type safety
- Flexible routing with path parameters and type conversion
- OpenAPI documentation generation
- Testing utilities with TestClient

Quick Start:
    from sillo import HttpContext, SilloApp, json

    app = SilloApp(title="My API", version="1.0.0")

    @app.get("/hello/{name}")
    async def hello(ctx: HttpContext, name: str):
        return json({"message": f"Hello, {name}!"})

    A handler takes one argument — the context — plus any path parameters,
    dependencies and validation markers it declares. It returns a response
    built by one of the free helpers, or plain data that the route encodes.

Common Patterns:

1. Validation (zero annotations — the type lives on the declaration):
    from sillo import Query, Path, Form, File

    class UserCreate(BaseModel):
        name: str
        email: str

    @app.post("/teams/{team_id}/users",
              request_model=UserCreate,       # JSON body
              response_model=UserOut)         # shapes the reply
    async def create_user(ctx, user,                     # <- the body
                          team_id=Path(type=int),        # path segment
                          notify=Query(False, type=bool),
                          db=Depend(get_db)):
        return await save(user, team_id, db)

    The JSON body is declared once, on the decorator, with request_model=. It
    is injected into the first plain parameter after the context, and also
    available as ctx.validated_data. It composes freely with Depend and with
    parameter markers.

    Every other location has a marker: Query, Header, Cookie, Path, Form, File.
    Constraints go on the marker — Query(1, type=int, ge=1, le=100) — and feed
    both validation and the generated OpenAPI schema, so the published contract
    and the enforced one cannot drift apart.

    Bad input returns 422 naming the location that failed:
        {"detail": [{"loc": ["query", "page"], "msg": "...", "type": "..."}]}

2. Dependency Injection:
    from sillo import Depend

    async def get_db():
        return Database()

    @app.get("/items")
    async def list_items(ctx, db=Depend(get_db)):
        return json(await db.query("SELECT * FROM items"))

    # Inject the context into any dependency:
    def get_auth(ctx=Depend(get_request=True)):
        return ctx.headers.get("Authorization")

3. Middleware — one context and call_next. Return a response to stop the chain:
    class RequireLogin(BaseMiddleware):
        async def dispatch(self, ctx, call_next):
            if ctx.user is None:
                return redirect("/login")
            return await call_next()

    app.use(CORSMiddleware(config=CorsConfig(
        allow_origins=["https://app.example.com"], allow_credentials=True,
    )))
    app.use(RateLimitMiddleware(rate=100))
    app.use(SessionMiddleware(config=SessionConfig()))

4. Responses:
    return json(data, status_code=201)
    return html("<h1>Hello</h1>")
    return file("downloads/report.pdf")
    return stream(async_generator(), content_type="text/plain")
    return redirect("/dashboard", status_code=302)

5. Exception Handlers:
    async def custom_handler(ctx, exc):
        return json({"error": str(exc)}, status_code=400)

    app.add_exception_handler(CustomError, custom_handler)

6. GraphQL — `pip install sillo-graphql`, which imports as `sillo.graphql`:
    from sillo.graphql import Graph, field

    Graph(schema, limits=Limits(depth=8)).mount(app)
"""

from sillo.core.routing import Group, Route, Router, WebsocketRoute

__version__: str = "0.3.1"

from sillo.core.dependencies import Depend

# Re-exported at the root because they are what a handler signature is written
# against: the context class it takes, and the helpers it returns.
#
# Every module named here is already pulled in by `.application` below, so
# these lines cost nothing at import time. That is also the line drawn:
# `sillo.record`, `sillo.testclient` and the other subsystems are *not*
# imported by default — several need optional extras — and pulling them in here
# would make `import sillo` fail without them. They keep their own namespaces.
from sillo.core.http import BaseContext, HttpContext
from sillo.exceptions import HTTPException, NotFoundException, WebSocketException
from sillo.responses import (
    abort,
    accepted,
    apaginate,
    created,
    download,
    empty,
    file,
    html,
    json,
    ndjson,
    no_content,
    not_found,
    paginate,
    permanent_redirect,
    raw,
    redirect,
    see_other,
    sse,
    stream,
    temporary_redirect,
    text,
    xml,
)
from sillo.websockets import WebSocketContext, WebSocketDisconnect

from .application import SilloApp
from .validation import (
    Cookie,
    File,
    Form,
    Header,
    Path,
    Query,
    RequestValidationError,
    ResponseValidationError,
    UploadFile,
)

__all__ = [
    "BaseContext",
    "Cookie",
    "Depend",
    "File",
    "Form",
    "Group",
    "HTTPException",
    "Header",
    "HttpContext",
    "NotFoundException",
    "Path",
    "Query",
    "RequestValidationError",
    "ResponseValidationError",
    "Route",
    "Router",
    "SilloApp",
    "UploadFile",
    "WebSocketContext",
    "WebSocketDisconnect",
    "WebSocketException",
    "WebsocketRoute",
    "abort",
    "accepted",
    "apaginate",
    "created",
    "download",
    "empty",
    "file",
    "html",
    "json",
    "ndjson",
    "no_content",
    "not_found",
    "paginate",
    "permanent_redirect",
    "raw",
    "redirect",
    "see_other",
    "sse",
    "stream",
    "temporary_redirect",
    "text",
    "xml",
]
