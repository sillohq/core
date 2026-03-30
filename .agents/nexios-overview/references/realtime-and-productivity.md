# Nexios Realtime And Productivity

Use this reference for features beyond the basic HTTP request path.

## Table of Contents

1. [WebSockets](#websockets)
2. [OpenAPI](#openapi)
3. [Pydantic](#pydantic)
4. [Testing](#testing)
5. [CLI](#cli)
6. [Static Files](#static-files)
7. [Templating](#templating)
8. [Other Common Concepts](#other-common-concepts)

## WebSockets

Nexios documents WebSockets as a first-class real-time feature.

### Basic WebSocket Route

```python
from nexios import NexiosApp

app = NexiosApp()

@app.ws_route("/ws")
async def ws_handler(ws):
    await ws.accept()
    data = await ws.receive_json()
    await ws.send_json({"echo": data})
```

### Router-Based WebSocket Organization

```python
from nexios.routing import Router

router = Router(prefix="/ws")
async def chat_socket(ws):
    await ws.accept()
    await ws.send_text("connected")

router.add_ws_route(path="/chat", handler=chat_socket)
app.mount_router(router)
```

Teach this lifecycle:

1. Accept the connection
2. Receive messages
3. Send messages
4. Handle disconnects
5. Clean up resources

## OpenAPI

Nexios documents automatic API docs with `/docs`, `/redoc`, and `/openapi.json`.

```python
from nexios import NexiosApp

app = NexiosApp(
    title="My API",
    version="1.0.0",
    description="A documented API"
)

@app.get("/users/{user_id}", summary="Get a user", tags=["Users"])
async def get_user(request, response, user_id: int):
    return response.json({"id": user_id, "name": "Ada"})
```

Use this concept for:

- API metadata
- Request and response schemas
- Interactive docs
- Better client generation and onboarding

## Pydantic

Nexios documents both manual validation and request-model-based validation patterns.

### Manual Validation

```python
from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):
    name: str
    email: EmailStr

@app.post("/users")
async def create_user(request, response):
    payload = await request.json
    user = UserCreate(**payload)
    return response.json(user.dict(), status_code=201)
```

### Request Model Documentation

```python
class UserInput(BaseModel):
    username: str
    email: EmailStr

@app.post("/users", request_model=UserInput)
async def create_user(request, response):
    return response.json(request.validated_data, status_code=201)
```

Teach Pydantic in Nexios as optional structure, not mandatory ceremony.

## Testing

Use the documented test client when teaching endpoint tests:

```python
from nexios import NexiosApp
from nexios.testclient import TestClient

app = NexiosApp()

@app.get("/")
async def home(request, response):
    return response.json({"message": "Hello"})

client = TestClient(app)

def test_home():
    result = client.get("/")
    assert result.status_code == 200
    assert result.json() == {"message": "Hello"}
```

This is the right reference when the user asks for test examples or a testing strategy.

## CLI

Nexios also documents a CLI workflow:

```bash
pip install nexios[cli]
nexios --help
nexios run
nexios dev
nexios urls
nexios ping /health
nexios shell
```

Teach the CLI as the productivity layer around app execution, route inspection, and development mode.

## Static Files

```python
from nexios.static import StaticFiles

static_files = StaticFiles(directory="static")
app.register(static_files, prefix="/static")
```

This is useful when the app needs to serve CSS, JS, images, or uploaded assets.

## Templating

Nexios documents a Jinja2-based templating workflow:

```python
from nexios.templating import TemplateEngine, render

engine = TemplateEngine()
engine.setup_environment()

@app.get("/")
async def home(request, response):
    return await render("home.html", {"title": "Welcome"}, request=request)
```

Teach templating as the HTML-rendering path for apps that are not API-only.

## Other Common Concepts

These topics also appear in the Nexios docs and should be mentioned when relevant:

- Request info and request metadata access
- Handler hooks and class-based extension points
- Routers and sub-app organization
- Concurrency guidance for async I/O
- Cookies, sessions, and browser-focused security

If the user asks for one of these specifically, answer with the same teaching pattern used throughout this skill: plain-language explanation first, then a compact example.
