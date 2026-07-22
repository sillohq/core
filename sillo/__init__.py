"""
sillo — The Platform for Python Backends

A modern ASGI web framework. Async-native. Zero boilerplate validation.
Built-in DI with pre-flattened execution plans. Everything you need — routing,
middleware, auth, CORS, CSRF, sessions, caching, GraphQL — ships as first-party.

Key Features:
- ASGI-based, async/await throughout
- Dependency injection with pre-flattened execution plan (zero recursion at runtime)
- Pydantic request validation via request_model — no type annotations needed
- Fluent Responder for building HTTP responses (json, html, file, stream, redirect)
- Middleware system: CORS, CSRF, sessions, auth, rate limiting, compression
- Depend(get_request=True) to inject the raw Request into any dependency
- GraphQL support via Strawberry (sillo.graphql)
- WebSocket support with type safety
- Flexible routing with path parameters and type conversion
- OpenAPI documentation generation
- Testing utilities with TestClient

Quick Start:
    from sillo import silloApp
    from pydantic import BaseModel

    app = silloApp(title="My API", version="1.0.0")

    @app.get("/hello/{name}")
    async def hello(request, response, name: str):
        return response.json({"message": f"Hello, {name}!"})

Common Patterns:

1. Request Validation (zero annotations):
    class UserCreate(BaseModel):
        name: str
        email: str

    @app.post("/users", request_model=UserCreate)
    async def create_user(request, response):
        user = request.validated_data   # already a Pydantic model
        return response.json(user.model_dump(), status_code=201)

2. Dependency Injection:
    from sillo import Depend

    async def get_db():
        return Database()

    @app.get("/items")
    async def list_items(request, response, db=Depend(get_db)):
        return response.json(await db.query("SELECT * FROM items"))

    # Inject Request into any dependency:
    def get_auth(req=Depend(get_request=True)):
        return req.headers.get("Authorization")

3. Middleware:
    app.use(CORSMiddleware(config=CorsConfig(allow_origins=["*"])))
    app.use(RateLimitMiddleware(rate=100))
    app.use(SessionMiddleware(config=SessionConfig()))

4. Responses:
    return response.json(data, status_code=201)
    return response.html("<h1>Hello</h1>")
    return response.file("downloads/report.pdf")
    return response.stream(async_generator(), content_type="text/plain")
    return response.redirect("/dashboard", status_code=302)

5. Exception Handlers:
    async def custom_handler(request, response, exc):
        return response.json({"error": str(exc)}).status(400)

    app.add_exception_handler(CustomError, custom_handler)

6. GraphQL:
    from sillo.graphql import GraphQL

    GraphQL(app, schema, path="/graphql", graphiql=True)
"""

from sillo.core.routing import Route, Router

from .application import silloApp
from .frontend import FrontendApp
from sillo.core.dependencies import Depend
from .parameters import Query, Header, Cookie

__all__ = [
    "silloApp",
    "Depend",
    "Router",
    "Route",
    "FrontendApp",
    "Query",
    "Header",
    "Cookie",
]
