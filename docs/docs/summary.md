# Nexios Comprehensive Guide

This guide provides an in-depth exploration of the Nexios framework, combining core concepts, advanced features, and best practices into a single resource.

## Getting Started

Nexios is designed to be the fastest and most developer-friendly async Python web framework.

::: code-group

```bash [uv]
uv pip install nexios
```

```bash [pip]
pip install nexios
```

:::

### Your First Application

Create a `main.py` file to start your journey.

::: code-group

```python [main.py]
from nexios import NexiosApp
import uvicorn

app = NexiosApp()

@app.get("/")
async def home(request, response):
    return response.json({"message": "Hello from Nexios!"})

if __name__ == "__main__":
    # Run with hot reload enabled
    uvicorn.run("main:app", reload=True)
```

:::

---

## Routing System

Nexios provides a powerful routing engine that supports path parameters, type validation, and nested routers.

### Basic & Parameterized Routing

You can define routes with typed parameters. Nexios automatically validates and converts these parameters.

```python
from nexios import NexiosApp

@app.get("/items/{item_id:int}")
async def get_item(request, response):
    # item_id is guaranteed to be an integer
    item_id = request.path_params.item_id
    return response.json({"item": item_id})
```

**Supported Types:**

- `str`: Default string (matches up to `/`)
- `int`: Integers
- `float`: Floating point numbers
- `uuid`: UUID strings
- `slug`: Hyphenated alphanumeric strings
- `path`: Matches the rest of the path (including `/`)

### Grouping & Nesting

Organize your application using `Router`. You can nest routers arbitrarily deep.

::: code-group

```python [Feature Router]
from nexios.routing import Router

# Create a router for user operations
user_router = Router(prefix="/users", tags=["Users"])

@user_router.get("/")
async def list_users(req, res):
    return res.json([{"name": "Alice"}, {"name": "Bob"}])

@user_router.post("/")
async def create_user(req, res):
    return res.status(201).json({"status": "created"})
```

```python [Main App]
from nexios import NexiosApp
# Import user_router from your feature module

app = NexiosApp()
app.mount_router(user_router)
```

:::

---

## Request & Response

### Handling Request Data

Nexios makes it easy to access body data, forms, and files.

```python
@app.post("/submit")
async def submit_data(req, res):
    # JSON Body
    if req.headers.get("content-type") == "application/json":
        data = await req.json
    
    # Form Data
    form = await req.form
    username = form.get("username")
    
    # File Uploads
    files = await req.files
    uploaded_file = files.get("avatar")
    
    return res.text("Received")
```

### Sending Responses

The `response` object provides a fluent API for sending various content types.

::: code-group

```python [JSON]
return response.status(200).json({"success": True})
```

```python [HTML]
return response.html("<h1>Welcome</h1>")
```

```python [File]
return response.file("/path/to/invoice.pdf", filename="invoice.pdf")
```

```python [Redirect]
return response.redirect(url="/login")
```

:::

---

## Middleware

Middleware allows you to intercept requests and responses globally or per-route.

### Creating Middleware

You can write middleware as functions or classes. Class-based middleware is recommended for complex logic.

::: code-group

```python [Class-Based (Recommended)]
from nexios.middleware import BaseMiddleware

class TimingMiddleware(BaseMiddleware):
    async def process_request(self, req, res, next):
        import time
        req.state.start_time = time.time()
        await next()
    
    async def process_response(self, req, res):
        import time
        duration = time.time() - req.state.start_time
        res.headers["X-Process-Time"] = str(duration)
        return res
```

```python [Function-Based]
async def simple_middleware(req, res, next):
    print("Before")
    await next()
    print("After")
```

:::

**Registering Middleware:**

```python
app.add_middleware(TimingMiddleware)
```

---

## Authentication & Permissions

Nexios has a built-in authentication system with support for custom backends and fine-grained permissions.

### Setup Authentication

First, configure the middleware with a backend (e.g., JWT).

```python
from nexios.auth.middleware import AuthenticationMiddleware
from nexios.auth.backends import JWTBackend

# Configure JWT Backend
jwt_backend = JWTBackend()

app.add_middleware(AuthenticationMiddleware(backend=jwt_backend))
```

### Protecting Routes

Use decorators to enforce authentication and permissions.

::: code-group

```python [Require Auth]
from nexios.auth.decorators import auth

@app.get("/private")
@auth()
async def private_route(req, res):
    return res.json({"user": req.user.identity})
```

```python [Require Permissions]
from nexios.auth.decorators import has_permission

@app.delete("/users/{id}")
@has_permission("users.delete")
async def delete_user(req, res):
    return res.json({"status": "deleted"})
```

:::

---

## Security

Nexios prioritizes security with a suite of built-in protections conveniently bundled in `SecurityMiddleware`.

```python
from nexios.middleware import SecurityMiddleware

app.add_middleware(SecurityMiddleware(
    # HTTPS Enforcement
    ssl_redirect=True,
    hsts_enabled=True,
    
    # XSS & Content Protection
    xss_protection=True,
    csp_enabled=True,
    
    # Clickjacking Protection
    frame_options="DENY"
))
```

### CORS Configuration

Manage Cross-Origin Resource Sharing effortlessly.

```python
from nexios.config import MakeConfig
from nexios.middleware.cors import CorsConfig

config = MakeConfig(
    cors=CorsConfig(
        allow_origins=["https://yourdomain.com", "http://localhost:3000"],
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
        allow_credentials=True
    )
)
```

---

## Dependency Injection

Keep your handlers clean and testable by injecting dependencies.

```python
from nexios import Depend

# Dependency Provider
def get_database():
    db = DatabaseConnection()
    try:
        yield db
    finally:
        db.close()

# Handler using Dependency
@app.get("/items")
async def list_items(req, res, db = Depend(get_database)):
    items = db.query("SELECT * FROM items")
    return res.json(items)
```

Nexios supports:

- **Async & Sync Providers**: Automatically handled.
- **Sub-dependencies**: Dependencies can require other dependencies.
- **Resource Cleanup**: Use `yield` to close resources after the request (like DB connections).

### Using Contexts

For deeper integrations, Nexios provides a `Context` object that allows you to access application-level or request-level data within your dependencies.

```python
from nexios import Context

def get_config(ctx: Context):
    # Access the app instance
    debug_mode = ctx.app.debug
    
    # Access the current request
    client_host = ctx.request.client.host
    
    return {"debug": debug_mode, "client": client_host}

@app.get("/info", dependencies=[Depend(get_config)])
async def info(req, res): ...
```

---

## Templating

Nexios provides a powerful templating system built on top of Jinja2.

### Basic Usage

First, ensure you have the templating extras installed:

```bash
pip install nexios[templating]
```

Then configure the template engine in your app:

```python
from nexios import NexiosApp
from nexios.templating import render, TemplateEngine

app = NexiosApp()
engine = TemplateEngine()
engine.setup_environment()

@app.get("/")
async def home(request, response):
    return await render("home.html", {"title": "Welcome"}, request=request)
```

For more advanced features like custom filters, inheritance, and async rendering, refer to the [Templating Documentation](/v2/guide/templating/index).

---

## WebSockets & Channels

Build real-time applications with native WebSocket support.

### Basic WebSocket

```python
from nexios.websockets.base import WebSocketDisconnect

@app.ws("/echo")
async def echo_endpoint(ws):
    await ws.accept()
    try:
        while True:
            message = await ws.receive_text()
            await ws.send_text(f"Echo: {message}")
    except WebSocketDisconnect:
        print("Client disconnected")
```

### Channels (Advanced)

`Channel` provides a robust wrapper for structured communication, automatic serialization, and heartbeats.

```python
from nexios.websockets.channels import Channel, PayloadTypeEnum

@app.ws("/data-stream")
async def data_stream(ws):
    await ws.accept()
    
    channel = Channel(
        websocket=ws,
        payload_type=PayloadTypeEnum.JSON,
        expires=3600  # Auto-expire after 1 hour
    )
    
    try:
        while True:
            # high-level receive that returns parsed data
            data = await channel.receive()
            
            if data.get("action") == "ping":
                # Heartbeat management
                channel.touch()
                await channel.send({"action": "pong"})
            else:
                await channel.send({"processed": data})
                
    finally:
        await channel.close()
```

---

## OpenAPI Documentation

Nexios automatically generates OpenAPI specifications and interactive documentation (Swagger UI / ReDoc).

### defining Models

Use Pydantic models to define schemas for requests and responses.

::: code-group

```python [Request Model]
from pydantic import BaseModel

class ProductCreate(BaseModel):
    name: str
    price: float
    is_offer: bool = None
```

```python [Response Model]
class ProductResponse(ProductCreate):
    id: int
    created_at: str
```

:::

### API Endpoint

Document your endpoint using the models.

```python
@app.post("/products", request_model=ProductCreate, responses={201: ProductResponse})
async def create_product(req, res):
    # req.body is already validated against ProductCreate
    payload = req.body
    
    # Business logic...
    new_product = {"id": 1, **payload.dict(), "created_at": "2023-01-01"}
    
    return res.status(201).json(new_product)
```

Visit `/docs` (Swagger) or `/redoc` (ReDoc) to see your interactive API documentation.
