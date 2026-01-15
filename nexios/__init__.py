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

import warnings
from typing import AsyncContextManager, Callable, Optional

from typing_extensions import Annotated, Doc

from .application import NexiosApp
from .config import set_config
from .config.base import MakeConfig
from .dependencies import Depend
from .middleware.cors import CORSMiddleware
from .middleware.csrf import CSRFMiddleware
from .routing import Router
from .session.middleware import SessionMiddleware
from .types import ExceptionHandlerType


def get_application(
    config: Annotated[
        MakeConfig,
        Doc(
            """
            This subclass is derived from the MakeConfig class and is responsible for managing 
            configurations within the Nexios framework. It takes arguments in the form of 
            dictionaries, allowing for structured and flexible configuration handling. By using 
            dictionaries, this subclass makes it easy to pass multiple configuration values at 
            once, reducing complexity and improving maintainability.

            One of the key advantages of this approach is its ability to dynamically update and 
            modify settings without requiring changes to the core codebase. This is particularly 
            useful in environments where configurations need to be frequently adjusted, such as 
            database settings, API credentials, or feature flags. The subclass can also validate 
            the provided configuration data, ensuring that incorrect or missing values are handled 
            properly.

            Additionally, this design allows for merging and overriding configurations, making it 
            adaptable for various use cases. Whether used for small projects or large-scale 
            applications, this subclass ensures that configuration management remains efficient 
            and scalable. By extending MakeConfig, it leverages existing functionality while 
            adding new capabilities tailored to Nexios. This makes it an essential component for 
            maintaining structured and well-organized application settings.
            """
        ),
    ] = None,
    title: Annotated[
        Optional[str],
        Doc(
            """
            The title of the API, used in the OpenAPI documentation.
            """
        ),
    ] = None,
    version: Annotated[
        Optional[str],
        Doc(
            """
            The version of the API, used in the OpenAPI documentation.
            """
        ),
    ] = None,
    description: Annotated[
        Optional[str],
        Doc(
            """
            A brief description of the API, used in the OpenAPI documentation.
            """
        ),
    ] = None,
    server_error_handler: Annotated[
        Optional[ExceptionHandlerType],
        Doc(
            """
            A function in Nexios responsible for handling server-side exceptions by logging errors, 
            reporting issues, or initiating recovery mechanisms. It prevents crashes by intercepting 
            unexpected failures, ensuring the application remains stable and operational. This 
            function provides a structured approach to error management, allowing developers to 
            define custom handling strategies such as retrying failed requests, sending alerts, or 
            gracefully degrading functionality. By centralizing error processing, it improves 
            maintainability and observability, making debugging and monitoring more efficient. 
            Additionally, it ensures that critical failures do not disrupt the entire system, 
            allowing services to continue running while appropriately managing faults and failures.
            """
        ),
    ] = None,
    lifespan: Optional[Callable[["NexiosApp"], AsyncContextManager[bool]]] = None,
    routes: Optional[list[Router]] = None,
    dependencies: Optional[list[Depend]] = None,
) -> NexiosApp:
    """
    Initializes and returns a `Nexios` application instance, serving as the core entry point for
    building web applications.

    Nexios is a lightweight, asynchronous Python framework designed for speed, flexibility, and
    ease of use. This function sets up the necessary configurations and routing mechanisms,
    allowing developers to define routes, handle requests, and manage responses efficiently.

    ## Example Usage

    ```python
    from nexios import Nexios
    config = MakeConfig({
        "debug" : True
    })
    app = get_application(config = config)
    ```

    Returns:
        Nexios: An instance of the Nexios application, ready to register routes and handle requests.

    See Also:
        - [Nexios Documentation](https://example.com/nexios-docs)
    """
    warnings.warn(
        "get_application is deprecated. Please use NexiosApp instead.",
        DeprecationWarning,
    )
    set_config(config)
    app = NexiosApp(
        server_error_handler=server_error_handler,
        config=config,
        title=title,
        version=version,
        description=description,
        lifespan=lifespan,
        routes=routes,
        dependencies=dependencies,
    )

    return app


__all__ = ["MakeConfig", "Router", "NexiosApp", "get_application", "Depend"]
