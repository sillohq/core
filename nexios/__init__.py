"""
Nexios - A Modern, High-Performance Python Web Framework

Nexios is a powerful ASGI web framework that combines high performance with developer-friendly features.
Built on proven design patterns while introducing modern capabilities like dependency injection,
automatic OpenAPI documentation, and comprehensive middleware support.

Key Features:
- ASGI-based for high performance and async/await support
- Built-in dependency injection system
- Automatic OpenAPI/Swagger documentation
- Comprehensive middleware system (CORS, CSRF, Sessions)
- WebSocket support with type safety
- Pydantic integration for request/response validation
- Flexible routing with path parameters and type conversion
- Extensive testing utilities

Quick Start:
    from nexios import NexiosApp, MakeConfig

    app = NexiosApp(
        config=MakeConfig({"debug": True}),
        title="My API",
        version="1.0.0"
    )

    @app.get("/hello/{name}")
    async def hello(request, response, name: str):
        return response.json({"message": f"Hello, {name}!"})

    if __name__ == "__main__":
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8000)

Common Patterns:

1. Dependency Injection:
    from nexios import Depend

    async def get_db():
        return Database()

    @app.get("/items")
    async def list_items(request, response, db=Depend(get_db)):
        items = await db.query("SELECT * FROM items")
        return response.json(items)

2. Request Validation:
    from pydantic import BaseModel

    class Item(BaseModel):
        name: str
        price: float

    @app.post("/items")
    async def create_item(request, response):
        item = Item(**await request.json)
        return response.json(item)

3. Custom Middleware:
    from nexios.middleware import BaseMiddleware

    class LoggingMiddleware(BaseMiddleware):
        async def __call__(self, request, response, call_next):
            print(f"Request to {request.url}")
            return await call_next()

4. WebSocket Handling:
    @app.ws_route("/ws")
    async def websocket_handler(websocket):
        try:
            while True:
                data = await websocket.receive_text()
                await websocket.send_text(f"Echo: {data}")
        except Exception:
            await websocket.close()

For more examples and detailed documentation, visit:
https://nexios.readthedocs.io/

Note: This framework builds upon concepts from Starlette and other ASGI frameworks
while providing additional features and a more intuitive API design.
"""

from nexios.routing import Route, Router

from .application import NexiosApp
from .config import set_config
from .config.base import MakeConfig
from .dependencies import Depend

__all__ = [
    "NexiosApp",
    "set_config",
    "Depend",
    "MakeConfig",
    "Router",
    "Route",
]
