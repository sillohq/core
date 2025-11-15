---
title: Dependency Injection in Nexios
description: Learn how to use dependency injection in Nexios
head:
  - - meta
    - property: og:title
      content: Dependency Injection in Nexios
  - - meta
    - property: og:description
      content: Learn how to use dependency injection utilities in Nexios
---

#  Robust Dependency Injection in Nexios

Nexios provides a modern, flexible, and powerful dependency injection (DI) system inspired by the best of FastAPI and Starlette, but with its own unique features. This guide will help you master DI in Nexios, from simple use cases to advanced patterns.

---

##  What is Dependency Injection?

Dependency Injection is a design pattern that allows you to declare external resources, services, or logic ("dependencies") that your route handlers or other dependencies need. Nexios will automatically resolve and inject these dependencies for you.

**Benefits:**
- Separation of concerns
- Reusability
- Testability
- Cleaner code

---

##  Quick Start: Basic Dependency

```python
from nexios import NexiosApp, Depend

app = NexiosApp()

def get_settings():
    return {"debug": True, "version": "1.0.0"}

@app.get("/config")
async def show_config(request, response, settings: dict = Depend(get_settings)):
    return settings
```

- Use `Depend()` to mark a parameter as a dependency.
- Dependencies can be sync or async functions, or even classes.

---

##  Chaining & Sub-Dependencies

Dependencies can depend on other dependencies, forming a tree:

```python
async def get_db_config():
    return {"host": "localhost", "port": 5432}

async def get_db_connection(config: dict = Depend(get_db_config)):
    return Database(**config)

@app.get("/users")
async def list_users(req, res, db: Database = Depend(get_db_connection)):
    return await db.query("SELECT * FROM users")
```

---

##  Resource Management with Yield (Generators)

For resources that need cleanup (e.g., DB sessions), use generator or async generator dependencies. Nexios will handle cleanup automatically:

```python
# Synchronous generator dependency

def get_resource():
    resource = acquire()
    try:
        yield resource
    finally:
        release(resource)

# Async generator dependency
async def get_async_resource():
    resource = await acquire_async()
    try:
        yield resource
    finally:
        await release_async(resource)

@app.get("/resource")
async def use_resource(req, res, r=Depend(get_resource)):
    ...

@app.get("/async-resource")
async def use_async_resource(req, res, r=Depend(get_async_resource)):
    ...
```

- Cleanup code in the `finally` block is always executed after the request, even if an exception occurs.
- Both sync and async generator dependencies are supported.

---

##  App-level and Router-level Dependencies

Nexios supports dependencies that apply to all routes in the app or in a router. This is useful for things like authentication, database sessions, or any logic you want to share across multiple routes.

- **App-level dependencies**: Set with the `dependencies` argument on `NexiosApp`. These run for every request to the app.
- **Router-level dependencies**: Set with the `dependencies` argument on `Router`. These run for every request to routes registered on that router.

### Example: App-level Dependency

```python
from nexios import NexiosApp, Depend

def global_dep():
    # This will run for every request
    return "global-value"

app = NexiosApp(dependencies=[Depend(global_dep)])

@app.get("/foo")
async def foo(req, res, value=Depend(global_dep)):
    return res.text(value)
```

### Example: Router-level Dependency

```python
from nexios import Router, Depend

def router_dep():
    return "router-value"

router = Router(prefix="/api", dependencies=[Depend(router_dep)])

@router.get("/bar")
async def bar(req, res, value=Depend(router_dep)):
    return res.text(value)
```

### Combining App, Router, and Route Dependencies

All levels are resolved and injected in order:

```python
app = NexiosApp(dependencies=[Depend(global_dep)])
router = Router(prefix="/api", dependencies=[Depend(router_dep)])

@router.get("/combo")
async def combo(req, res, g=Depend(global_dep), r=Depend(router_dep), custom=Depend(lambda: "custom")):
    return {"app": g, "router": r, "custom": custom}

app.mount_router(router)
```

---

##  Using Classes as Dependencies

Classes can act as dependencies through their `__call__` method:

```python
class AuthService:
    def __init__(self, secret_key: str):
        self.secret_key = secret_key
    async def __call__(self, token: str = Header(...)):
        return await self.verify_token(token)

auth = AuthService(secret_key="my-secret")

@app.get("/protected")
async def protected_route(req, res, user = Depend(auth)):
    return {"message": f"Welcome {user.name}"}
```

---

##  Context-Aware Dependencies

Dependencies can access request context, which includes the request, user, and more. This is useful for logging, tracing, or user-specific logic.

```python
from nexios.dependencies import Context

@app.get("/context-demo")
async def context_demo(req, res, context: Context = None):
    return {"path": context.request.url.path}
```

You can also use `context=Context()` as a parameter, and Nexios will inject the current context automatically.

---

##  Deep Context Propagation

Nexios supports context propagation through deeply nested dependencies:

```python
async def dep_a(context=Context()):
    return f"A: {context.request.url.path}"

async def dep_b(a=Depend(dep_a), context=Context()):
    return f"B: {a}, {context.request.url.path}"

@app.get("/deep-context")
async def deep_context(req, res, b=Depend(dep_b)):
    return {"result": b}
```

---

##  Testing Dependencies

You can override dependencies for testing:

```python
async def get_test_db():
    return TestDatabase()

app.dependency_overrides[get_db] = get_test_db
```

---

##  Best Practices

- **Single Responsibility**: Each dependency should have one clear purpose
- **Type Hints**: Use type hints for better IDE support and error detection
- **Resource Management**: Use `yield` for resources that need cleanup
- **Error Handling**: Handle dependency errors gracefully
- **Documentation**: Document what each dependency provides
- **Testing**: Design dependencies to be easily testable
- **Performance**: Avoid expensive operations in dependencies
- **Use Context**: Leverage context for request/user-specific logic

---

##  Advanced Patterns

- **Dependency Caching**: Use `functools.lru_cache` for expensive dependencies
- **Custom Scopes**: Implement your own scoping rules for advanced use cases
- **Pydantic Models**: Use Pydantic for validation in dependencies

---

##  Real-World Example: Auth, DB, and Caching

```python
from nexios import NexiosApp, Depend
from nexios.dependencies import Context

app = NexiosApp()

def get_db():
    db = connect_db()
    try:
        yield db
    finally:
        db.close()

def get_cache():
    cache = connect_cache()
    try:
        yield cache
    finally:
        cache.close()

class AuthService:
    def __init__(self, secret):
        self.secret = secret
    async def __call__(self, context=Context()):
        token = context.request.headers.get("Authorization")
        return self.verify_token(token)

@app.get("/dashboard")
async def dashboard(req, res, db=Depend(get_db), cache=Depend(get_cache), user=Depend(AuthService("s3cr3t"))):
    data = await db.get_dashboard(user.id)
    cached = await cache.get(f"dashboard:{user.id}")
    return {"data": data, "cached": cached}
```

---

For more, see the API reference and advanced guides.