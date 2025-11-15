# Nexios Core Concepts

Nexios is a modern, async-first Python web framework built on ASGI. It combines high performance, developer-friendly features, and a clean, maintainable architecture. This page introduces the fundamental concepts that make Nexios powerful and easy to use.

## Framework Philosophy

Nexios is designed around several core principles:

### 1. **Simplicity First**

Nexios prioritizes simplicity in its API. Common tasks are straightforward, while advanced features remain accessible.

```python
@app.get("/users/{user_id}")
async def get_user(request, response user_id):
    return {"id": user_id, "name": "John Doe"}

# Simple middleware addition
app.add_middleware(CORSMiddleware())
```

### 2. **Performance by Default**

Every design decision in Nexios considers performance. The framework is optimized for high-throughput applications without sacrificing developer experience.

### 3. **Type Safety Throughout**

Full type hint support means better IDE integration, fewer runtime errors, and more maintainable code.

```python
from nexios.http import Request, Response
from typing import Dict, Any

@app.get("/api/data")
async def get_data(request: Request, response: Response):
    return {"status": "success"}
```

### 4. **Production Ready**

Built-in features for security, monitoring, and deployment mean you can focus on business logic rather than infrastructure.

### 5. **Developer Experience**

Excellent tooling, clear error messages, and comprehensive documentation make development enjoyable and efficient.

---

## Understanding ASGI

ASGI (Asynchronous Server Gateway Interface) is the foundation that enables Nexios to handle concurrent connections efficiently.

### What is ASGI?

ASGI defines how web servers communicate with Python web applications. It improves on WSGI by supporting:

- **Async/await** for non-blocking operations
- **Concurrent requests**
- **WebSocket support**
- **HTTP/2 support**
- **Lifespan protocol** for startup/shutdown

### ASGI vs WSGI

| Feature     | WSGI                       | ASGI                              |
| ----------- | -------------------------- | --------------------------------- |
| Concurrency | Synchronous, one at a time | Asynchronous, concurrent requests |
| WebSockets  | Not supported              | Native support                    |
| HTTP/2      | Limited support            | Full support                      |
| Performance | Good for simple apps       | Excellent for high-load apps      |
| Complexity  | Simple                     | More complex, more powerful       |

::: tip Why ASGI Matters
ASGI enables Nexios to:

- Handle thousands of concurrent connections
- Provide real-time features (WebSockets)
- Scale efficiently
- Support modern web standards
  :::

---

## Framework Architecture

Nexios uses a layered architecture:

### 1. ASGI Foundation Layer

Handles the low-level ASGI protocol and provides the interface between your app and the web server.

```python
async def __call__(self, scope, receive, send):
    if scope["type"] == "http":
        await self.handle_http_request(scope, receive, send)
    elif scope["type"] == "websocket":
        await self.handle_websocket(scope, receive, send)
```

### 2. Middleware Layer

Middleware allows you to add cross-cutting concerns (security, CORS, sessions, logging).

```python
from nexios.middleware import CORSMiddleware, SecurityMiddleware

app.add_middleware(CORSMiddleware())
app.add_middleware(SecurityMiddleware())
```

### 3. Routing Layer

Route map HTTP requests to handler functions.

```python
@app.get("/users/{user_id:int}")
async def get_user(request, response):
    user_id = request.path_params.user_id  # Already an int
    return response.json({"id": user_id})
```

### 4. Handler & Response Layer

Handlers process requests and return responses. Nexios automatically serializes responses.

```python
@app.get("/api/data")
async def get_data(request, response):
    return response.json({"status": "success"})
```

---

## Dependency Injection

Nexios supports dependency injection for clean, testable code.

```python
from nexios import Depend

async def get_database():
    return Database()

async def get_current_user(request, db=Depend(get_database)):
    token = request.headers.get("Authorization")
    if not token:
        raise HTTPException(401, "Unauthorized")
    user = await db.get_user_by_token(token)
    if not user:
        raise HTTPException(401, "Invalid token")
    return user

@app.get("/profile")
async def get_profile(request, response, user=Depend(get_current_user)):
    return response.json({"id": user.id, "name": user.name})
```

---

## Performance Considerations

- **Use async for I/O**: Always use async database drivers and HTTP clients.
- **Avoid blocking operations**: Blocking code will block the event loop.
- **Connection pooling**: Reuse connections for better performance.
- **Cache expensive operations**: Use caching for repeated computations.

---

## Security

Nexios includes built-in security features:

- CORS protection
- CSRF protection
- Security headers
- Input validation
- Authentication (multiple backends)

::: warning Security Best Practices

- Validate all inputs
- Use HTTPS in production
- Implement proper authentication
- Rate limit to prevent abuse
- Log security events
  :::

---

## Testing

Nexios makes testing easy with built-in tools.

```python
import pytest
from nexios.testing import Client

@pytest.fixture
def client():
    return Client(app)

def test_get_user(client):
    response = client.get("/users/123")
    assert response.status_code == 200
    assert response.json()["id"] == 123
```

---

## Why Use Nexios?

- **Simple**: Intuitive API, minimal boilerplate.
- **Fast**: ASGI-based, async-first, optimized routing.
- **Flexible**: Custom middleware, authentication, database, and more.
- **Modern**: Built for Python 3.9+, uses type hints, async/await.
- **Production Ready**: Security, monitoring, and deployment features included.

---
