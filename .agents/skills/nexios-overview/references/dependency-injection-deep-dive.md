# Nexios Dependency Injection Deep Dive

Use this reference when the request is specifically about `Depend(...)`, dependency trees, cleanup, or context-aware injection.

## Table of Contents

1. [Mental Model](#mental-model)
2. [Basic Dependency](#basic-dependency)
3. [Sub-Dependencies](#sub-dependencies)
4. [Generator Dependencies](#generator-dependencies)
5. [Context-Aware Injection](#context-aware-injection)
6. [App and Router Dependencies](#app-and-router-dependencies)
7. [Class Dependencies](#class-dependencies)

## Mental Model

Nexios DI is explicit and function-centered. Teach it as:

- Declare what the handler needs
- Wrap reusable providers with `Depend(...)`
- Let Nexios resolve the dependency tree per request

That framing is better than describing it as a large container system.

## Basic Dependency

```python
from nexios import NexiosApp, Depend

app = NexiosApp()

def get_settings():
    return {"debug": True, "version": "1.0.0"}

@app.get("/config")
async def show_config(request, response, settings: dict = Depend(get_settings)):
    return response.json(settings)
```

Teach this as the default entry point for DI in Nexios.

## Sub-Dependencies

Dependencies can depend on other dependencies:

```python
async def get_db_config():
    return {"host": "localhost", "port": 5432}

async def get_db_connection(config: dict = Depend(get_db_config)):
    return Database(**config)

@app.get("/users")
async def list_users(request, response, db = Depend(get_db_connection)):
    return response.json(await db.query("SELECT * FROM users"))
```

Use this when the user needs layered resource construction.

## Generator Dependencies

Use generator or async generator dependencies for cleanup:

```python
def get_resource():
    resource = acquire()
    try:
        yield resource
    finally:
        release(resource)

async def get_async_resource():
    resource = await acquire_async()
    try:
        yield resource
    finally:
        await release_async(resource)
```

Teaching point:

- Put cleanup in `finally`
- Use this pattern for connections, sessions, and temporary resources

## Context-Aware Injection

Nexios docs also describe injecting request-aware context.

```python

from nexios.dependencies import Context

def get_user(ctx = Context()):
    request = ctx.request
    token = request.headers.get("token")
    return get_user_from_token(token)



@app.get("/context-demo")
async def context_demo(request, response, user = Depend(get_user)):
    return response.json({"user": user.data()})
```

Deeper propagation:

```python
async def dep_a(context=Context()):
    return f"A: {context.request.url.path}"

async def dep_b(a=Depend(dep_a), context=Context()):
    return f"B: {a}, {context.request.url.path}"

@app.get("/deep-context")
async def deep_context(request, response, b=Depend(dep_b)):
    return response.json({"result": b})
```

Teach this as the clean way to access request-specific state without global variables.

## App And Router Dependencies

### App-Level

```python
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

Use these patterns for shared auth, DB access, tenancy, or configuration.

## Class Dependencies

Classes can act as dependencies too:

```python
class AuthService:
    def __init__(self, secret_key: str):
        self.secret_key = secret_key

    async def __call__(self, token: str):
        return await self.verify_token(token)

auth = AuthService(secret_key="my-secret")

@app.get("/protected")
async def protected_route(request, response, user = Depend(auth)):
    return response.json({"message": f"Welcome {user.name}"})
```

Use class dependencies when stateful services or reusable verifiers make the example clearer than plain functions.
