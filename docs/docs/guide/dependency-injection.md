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

# Dependency Injection in Nexios

Nexios provides a modern, flexible, and powerful dependency injection (DI) system for clean, testable code. Dependencies are resolved automatically, support nesting, and can use parameter extractors for request data.

## Basic Example

```python
from nexios import NexiosApp, Depend

app = NexiosApp()

def get_settings():
    return {"debug": True, "version": "1.0.0"}

@app.get("/config")
async def show_config(request, response, settings: dict = Depend(get_settings)):
    return settings
```

- Use `Depend()` to mark a parameter as a dependency
- Dependencies can be sync or async functions, or classes

---

## What is Dependency Injection?

Dependency Injection (DI) is a design pattern that allows decoupling components by injecting their dependencies rather than hardcoding them. In Nexios, you declare what your handlers need, and the framework handles the rest.

**Key Benefits:**
- **Simplicity**: No complex containers or annotations
- **Testability**: Easy to override for isolated testing
- **Reusability**: Share logic across handlers

---

## Quick Start: Basic Dependency

```python
from nexios import NexiosApp, Depend

app = NexiosApp()

def get_database():
    return DatabaseConnection()

@app.get("/users")
async def list_users(request, response, db = Depend(get_database)):
    return await db.query("SELECT * FROM users")
```

---

## Getting Request Data: Use Parameter Extractors

For accessing query parameters, headers, and cookies in dependencies, **use parameter extractors** instead of Context:

### Recommended: Query, Header, Cookie

```python
from nexios import Depend, Query, Header, Cookie

def get_pagination(page: int = Query(1), limit: int = Query(10)):
    return {"page": page, "limit": limit}

def get_auth_data(authorization: str = Header()):
    return {"token": authorization}

def get_user_preferences(theme: str = Cookie("dark")):
    return {"theme": theme}

@app.get("/dashboard")
async def dashboard(
    request, response,
    pagination: dict = Depend(get_pagination),
    auth: dict = Depend(get_auth_data),
    prefs: dict = Depend(get_user_preferences)
):
    return {**pagination, **auth, **prefs}
```

**Benefits:**
- Automatic type conversion
- Clean, declarative syntax
- Works in deeply nested dependencies
- Self-documenting parameters

### Legacy: Context (Not Recommended)

```python
from nexios import Depend
from nexios.dependencies import Context

def get_pagination(context: Context = None):
    page = context.request.query_params.get("page", "1")
    limit = context.request.query_params.get("limit", "10")
    return {"page": int(page), "limit": int(limit)}
```

**Why not Context for request data?**
- Manual type conversion required
- More verbose code
- Less maintainable

::: tip
For request data (query, headers, cookies), use `Query`, `Header`, and `Cookie` parameter extractors. Reserve `Context` for advanced cases where you need direct access to the full request object.
:::

---

## Chaining & Sub-Dependencies

Dependencies can depend on other dependencies:

```python
def get_db_config():
    return {"host": "localhost", "port": 5432}

def get_db_connection(config: dict = Depend(get_db_config)):
    return Database(**config)

@app.get("/users")
async def list_users(request, response, db = Depend(get_db_connection)):
    return await db.query("SELECT * FROM users")
```

---

## Resource Management with Yield

For resources needing cleanup, use generator dependencies:

```python
def get_db_session():
    session = db.connect()
    try:
        yield session
    finally:
        session.close()

async def get_async_resource():
    resource = await acquire()
    try:
        yield resource
    finally:
        await resource.release()

@app.get("/data")
async def get_data(request, response, session = Depend(get_db_session)):
    return await session.query("SELECT * FROM data")
```

Cleanup code in the `finally` block runs after every request, even on exceptions.

---

## App-level and Router-level Dependencies

Apply dependencies to all routes in an app or router:

### App-level Dependency

```python
from nexios import NexiosApp, Depend

def get_tenant():
    return {"tenant_id": "default"}

app = NexiosApp(dependencies=[Depend(get_tenant)])

@app.get("/config")
async def config(request, response, tenant: dict = Depend(get_tenant)):
    return tenant
```

### Router-level Dependency

```python
from nexios import Router, Depend

router = Router(prefix="/api", dependencies=[Depend(get_auth)])

@router.get("/protected")
async def protected(request, response, auth = Depend(get_auth)):
    return auth
```

---

## Using Classes as Dependencies

Classes with `__call__` work as dependencies:

```python
class AuthService:
    def __init__(self, secret_key: str):
        self.secret_key = secret_key

    async def __call__(self, token: str = Header()):
        return await self.verify_token(token)

auth = AuthService(secret_key="my-secret")

@app.get("/profile")
async def profile(request, response, user = Depend(auth)):
    return {"message": f"Welcome {user.name}"}
```

---

## Real-World Example: Auth with Parameter Extractors

```python
from nexios import NexiosApp, Depend, Query, Header, Cookie

app = NexiosApp()

def get_db():
    db = connect_db()
    try:
        yield db
    finally:
        db.close()

def get_auth_user(authorization: str = Header()):
    if not authorization:
        return None
    return verify_token(authorization)

def get_pagination(page: int = Query(1), limit: int = Query(10)):
    return {"page": page, "limit": limit}

def get_user_preferences(theme: str = Cookie("dark")):
    return {"theme": theme}

@app.get("/dashboard")
async def dashboard(
    request, response,
    db = Depend(get_db),
    user = Depend(get_auth_user),
    pagination = Depend(get_pagination),
    prefs = Depend(get_user_preferences)
):
    if not user:
        return {"error": "Unauthorized"}

    data = db.get_dashboard(user.id)
    return {**data, **pagination, **prefs}
```

---

## Advanced Patterns

- **Dependency Caching**: Use `functools.lru_cache` for expensive dependencies
- **Conditional Dependencies**: Use default values to make dependencies optional
- **Validation**: Combine with Pydantic for dependency validation

---

For more, see the [Request Parameters](/guide/request-parameters) guide and API reference.
