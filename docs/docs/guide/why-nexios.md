---
title: Why Nexios?
description: Nexios is a modern, async-first Python web framework designed with performance, developer experience, and clean architecture in mind. Here's why you might want to choose Nexios for your next project.
head:
  - - meta
    - property: og:title
      content: Why Nexios?
  - - meta
    - property: og:description
      content: Nexios is a modern, async-first Python web framework designed with performance, developer experience, and clean architecture in mind. Here's why you might want to choose Nexios for your next project.
---

# ❓ Why Nexios?

Nexios is a modern, async-first Python web framework designed with performance, developer experience, and clean architecture in mind. Here's why you might want to choose Nexios for your next project.

## ✨ Key Advantages

### 1. True Async Performance

Unlike other frameworks that add async as an afterthought, Nexios is built from the ground up with async/await:
- Native ASGI support
- No sync-to-async bridges
- Efficient connection pooling
- Non-blocking I/O throughout

```python
# Everything is async by default
@app.get("/users")
async def list_users(request, response):
    async with db.transaction():
        users = await db.fetch_all("SELECT * FROM users")
        return response.json(users)
```

### 2. Clean Architecture

Nexios promotes clean code practices through:
- Dependency injection
- Clear separation of concerns
- Domain-driven design patterns
- Testable components


```python
from nexios import Depend

class UserService:
    async def get_user(self, user_id: int):
        return await self.db.fetch_one(
            "SELECT * FROM users WHERE id = ?", 
            [user_id]
        )

@app.get("/users/{user_id:int}")
async def get_user(
    request, 
    response,
    user_id,
    user_service = Depend(UserService)
):
    user = await user_service.get_user(
       user_id
    )
    return response.json(user)
```

### 3. Modern Authentication

Nexios provides a modern authentication system:
- Multiple auth backends (JWT, Session, OAuth)
- Role-based access control
- Custom authentication flows
- Secure by default

```python
from nexios.auth.middleware import AuthenticationMiddleware
from nexios.auth.backends.jwt import JWTAuthBackend
from nexios.auth.decorator import auth

async def get_user_from_payload(**payload):
    return await db.fetch_one(
        "SELECT * FROM users WHERE id = ?",
        [payload["sub"]]
    )

app.add_middleware(
    AuthenticationMiddleware(
        backend=JWTAuthBackend(get_user_from_payload)
    )
)

@app.get("/protected")
@auth(["jwt"])
async def protected(request, response):
    return response.json({"user": request.user})
```

### 4. Developer Experience

We prioritize developer experience with:
- Clear error messages
- Auto-reloading in development
- Comprehensive type hints
- Intuitive APIs
- Excellent documentation

```python
from nexios import NexiosApp, MakeConfig
from nexios.middleware import CORSMiddleware

# Clear configuration
app = NexiosApp(
    config=MakeConfig(
        debug=True,
       cors = {
        allowed_origins = ["https//localhost:5000","api.nexios.hub"]
       }
    )
)

# Middleware with sensible defaults
app.add_middleware(CORSMiddleware())
```

### 5. WebSocket Support


First-class WebSocket support for real-time applications:
- Channels system
- Pub/sub patterns
- Authentication
- Connection management

```python
from nexios.websockets import Channel

chat = Channel("chat")

@app.websocket("/ws/chat/{room}")
async def chat_room(websocket, room: str):
    await chat.connect(websocket)
    try:
        while True:
            msg = await websocket.receive_json()
            await chat.broadcast({
                "room": room,
                "message": msg
            })
    except WebSocketDisconnect:
        await chat.disconnect(websocket)
```

### 6. Production Ready


Built for production use with:
- Connection pooling
- Rate limiting
- Load shedding
- Health checks
- Monitoring hooks
- Error tracking

```python
from nexios.middleware import (
    SecurityMiddleware
)

# Production configuration
app = NexiosApp(
    config=MakeConfig(
        debug=False,
        security={
            "ssl_redirect": True,
            "hsts_enabled": True
        }
    )
)

# Production middleware stack
app.add_middleware(SecurityMiddleware())

```

## 🏆 Comparison with Other Frameworks

### vs FastAPI

- **Async Design**: While both are async, Nexios is built async-first without any sync compatibility layers
- **Clean Architecture**: Nexios promotes domain-driven design and clean architecture patterns
- **Authentication**: More flexible authentication system with multiple backends
- **WebSockets**: Better WebSocket support with channels system
- **Performance**: Lower overhead and memory usage

### vs Django

- **Lightweight**: No ORM or admin interface overhead
- **Async First**: Native async support without sync/async bridges
- **Modern**: Built for modern Python features and patterns
- **Flexible**: Less opinionated about project structure
- **Fast**: Significantly better performance for API workloads

### vs Flask

- **Async**: Native async support vs sync-first design
- **Modern**: Built for Python 3.9+ with modern features
- **Scalable**: Better support for large applications
- **WebSocket**: Native WebSocket support
- **Type Safe**: Comprehensive type hints

## 🌟 Real World Use Cases

Nexios is particularly well-suited for:

1. **Microservices**
   - Low overhead
   - Fast startup
   - Easy deployment
   - Health checks

2. **Real-time Applications**
   - WebSocket support
   - Pub/sub patterns
   - Event streaming
   - Chat systems

3. **High-performance APIs**
   - Async database operations
   - Connection pooling
   - Efficient routing
   - Low latency

4. **Enterprise Applications**
   - Authentication
   - Role-based access
   - Audit logging
   - Monitoring

## 🚀 Getting Started

Ready to try Nexios? Check out our [Quick Start Guide](/guide/getting-started) or dive into the [Examples](/api-examples/).

::: tip Community
Join our growing community:
- [GitHub Discussions](https://github.com/nexios-labs/nexios/discussions)
- [Discord Server](https://discord.gg/nexios)
- [Twitter Updates](https://x.com/nexios-labs)
:::

::: warning Python Version
Nexios requires Python 3.9 or higher to leverage modern language features.
::: 