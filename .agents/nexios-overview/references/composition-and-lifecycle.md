# Nexios Composition And Lifecycle

Use this reference for the structural concepts that shape larger Nexios apps.

## Table of Contents

1. [Middleware](#middleware)
2. [Class-Based Middleware](#class-based-middleware)
3. [Dependency Injection](#dependency-injection)
4. [Shared Dependencies](#shared-dependencies)
5. [Startup and Shutdown](#startup-and-shutdown)
6. [Lifespan](#lifespan)
7. [Events](#events)

## Middleware

Function-style middleware is great for teaching pipeline flow:

```python
from datetime import datetime

async def timing_middleware(request, response, next):
    request.state.started_at = datetime.utcnow()
    result = await next()
    response.set_header("X-Processed", "true")
    return result

app.add_middleware(timing_middleware)
```

Important documented gotcha:

- Middleware must return either `await next()` or a response object. Forgetting to return can leave the request hanging.

### Early Exit Middleware

```python
async def require_session(request, response, next):
    if "session_id" not in request.cookies:
        return response.json({"error": "Missing session"}).status(400)
    return await next()
```

## Class-Based Middleware

Use class-based middleware when the logic has clear pre/post stages:

```python
from nexios.middleware import BaseMiddleware

class RequestLogger(BaseMiddleware):
    async def process_request(self, request, response, cnext):
        print("Incoming:", request.method, request.url)
        return await cnext()

    async def process_response(self, request, response):
        response.set_header("X-Logged", "1")
        return response
```

## Dependency Injection

Use `Depend(...)` to keep handlers clean:

```python
from nexios import Depend

def get_settings():
    return {"debug": True, "version": "1.0.0"}

@app.get("/config")
async def show_config(request, response, settings: dict = Depend(get_settings)):
    return response.json(settings)
```

### Sub-Dependencies

```python
async def get_db_config():
    return {"dsn": "sqlite:///app.db"}

async def get_db(config: dict = Depend(get_db_config)):
    return Database(**config)

@app.get("/users")
async def list_users(request, response, db = Depend(get_db)):
    users = await db.query("SELECT * FROM users")
    return response.json(users)
```

### Generator Dependencies

Use this pattern for resources that need cleanup:

```python
def get_resource():
    resource = acquire()
    try:
        yield resource
    finally:
        release(resource)
```

This is a good pattern for sessions, connections, or temporary resources.

## Shared Dependencies

Nexios documents app-level and router-level dependencies.

### App-Level

```python
from nexios import NexiosApp, Depend

def global_dep():
    return "global-value"

app = NexiosApp(dependencies=[Depend(global_dep)])
```

### Router-Level

```python
from nexios.routing import Router

def router_dep():
    return "router-value"

api = Router(prefix="/api", dependencies=[Depend(router_dep)])
```

Use these patterns for shared auth, config, or database helpers.

## Startup and Shutdown

Use startup hooks for initialization:

```python
@app.on_startup
async def startup():
    print("Application starting")
```

Use shutdown hooks for cleanup:

```python
@app.on_shutdown
async def shutdown():
    print("Application shutting down")
```

Teaching note:

- Startup is a good place for connection pools, caches, and resource initialization.
- Shutdown is the place for cleanup and graceful release.

## Lifespan

When the user wants one place for startup and shutdown:

```python
from contextlib import asynccontextmanager
from nexios import NexiosApp

@asynccontextmanager
async def app_lifespan(app):
    print("App started")
    yield
    print("App shutting down")

app = NexiosApp(lifespan=app_lifespan)
```

Teach lifespan as the structured alternative to separate startup/shutdown decorators.

## Events

Nexios documents an event system for side effects and loose coupling:

```python
@app.events.on("user.created")
async def handle_user_created(user):
    print(f"Created user: {user['name']}")

@app.post("/users")
async def create_user(request, response):
    payload = await request.json
    await app.events.emit("user.created", payload)
    return response.json(payload, status_code=201)
```

Best teaching frame:

- Use events for notifications, analytics, emails, or logging
- Do not use them for critical request-path data mutations when the main handler depends on the result
