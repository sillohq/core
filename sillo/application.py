from __future__ import annotations
from sillo.core.helpers.async_helpers import is_async_callable
from sillo.openapi import License
from sillo.openapi import Contact

from typing import (
    TYPE_CHECKING,
    Any,
    AsyncContextManager,
    Awaitable,
    Callable,
    ContextManager,
    Dict,
    List,
    Literal,
    Optional,
    Sequence,
    Type,
    Union,
)

from typing_extensions import Annotated, Doc

from sillo._internals._middleware import (
    ASGIRequestResponseBridge,
)
from sillo.core.encoding import CUSTOM_ENCODERS, register_encoder

from sillo._internals._middleware import DefineMiddleware as Middleware
from sillo.core.dependencies import Depend
from sillo.events import EventEmitter
from sillo.exception_handler import ExceptionHandlerType, ExceptionMiddleware
from sillo.logging import create_logger
from sillo.core.error import (
    ServerErrHandlerType,
    ServerErrorMiddleware,
)
from sillo.objects import URLPath
from sillo.openapi._builder import APIDocumentation
from sillo.openapi.config import OpenAPIConfig
from sillo.openapi.models import HTTPBearer, Parameter, Server
from sillo.core.routing.base import BaseRoute
from pathlib import Path
from sillo.core.routing import Route, Router, WebsocketRoute
from .types import (
    ASGIApp,
    ArgsType,
    HandlerType,
    Message,
    MiddlewareType,
    Receive,
    Scope,
    Send,
    WsHandlerType,
)

if TYPE_CHECKING:
    from sillo.core.http import Request, Response

import warnings

try:
    import uvicorn  # type: ignore[import-untyped]
except ImportError:
    uvicorn = None  # type: ignore[assignment]  # ty: ignore[invalid-assignment]

allowed_methods_default = ["get", "post", "delete", "put", "patch", "options"]

logger = create_logger("sillo")
lifespan_manager = Callable[
    ["silloApp"], Union[AsyncContextManager[Any], ContextManager[Any]]
]


class silloApp:
    """
    Core application class for the sillo ASGI web framework.

    This class serves as the central entry point for building asynchronous
    web applications and APIs. It integrates routing, middleware, dependency
    injection, OpenAPI documentation generation, lifespan management, and
    WebSocket support into a single cohesive interface.

    The application follows the ASGI specification and can be served by any
    compliant ASGI server such as uvicorn, granian, or daphne. It provides
    both decorator-based and programmatic route registration patterns.

    Attributes:
        debug: Whether debug mode is enabled for detailed error output.
        dependencies: Global dependency injection definitions.
        custom_encoders: Mapping of types to custom JSON encoder callables.
        http_middleware: Ordered list of HTTP middleware instances.
        startup_handlers: List of async callables executed on application startup.
        shutdown_handlers: List of async callables executed on application shutdown.
        server_error_handler: Optional handler for unhandled server exceptions.
        route_class: The route class used for constructing route instances.
        app: The root router instance managing all registered routes.
        exceptions_handler: The middleware handling registered exception mappings.
        router: Reference to the root router for convenience access.
        state: A shared dictionary for storing application-level state.
        openapi_config: Configuration object for OpenAPI schema generation.
        openapi: The API documentation builder instance.
        events: The event emitter for application-level event broadcasting.
        title: The display title of the application.
    """

    def __init__(
        self,
        debug: Annotated[
            bool,
            Doc("""
                    Whether to enable debug mode.
                    """),
        ] = True,
        title: Annotated[
            Optional[str],
            Doc("""
                    The title of the API, used in the OpenAPI documentation.
                    """),
        ] = None,
        version: Annotated[
            Optional[str],
            Doc("""
                    The version of the API, used in the OpenAPI documentation.
                    """),
        ] = None,
        description: Annotated[
            Optional[str],
            Doc("""
                    A brief description of the API, used in the OpenAPI documentation.
                    """),
        ] = None,
        contact: Annotated[
            Optional[Contact],
            Doc("""
                    Contact information for the API, used in the OpenAPI documentation.
                    """),
        ] = None,
        license: Annotated[
            Optional[License],
            Doc("""
                    License information for the API, used in the OpenAPI documentation.
                    """),
        ] = None,
        servers: Annotated[
            Optional[List[Server]],
            Doc("""
                    A list of servers for the API, used in the OpenAPI documentation.
                    """),
        ] = None,
        terms_of_service: Annotated[
            Optional[str],
            Doc("""
                    A URL to the terms of service for the API, used in the OpenAPI documentation.
                    """),
        ] = None,
        swagger_docs: Annotated[
            str,
            Doc("""
                    A URL to the Swagger UI documentation for the API, used in the OpenAPI documentation.
                    """),
        ] = "/docs",
        redoc_docs: Annotated[
            str,
            Doc("""
                    A URL to the Redoc documentation for the API, used in the OpenAPI documentation.
                    """),
        ] = "/redoc",
        openapi_url: Annotated[
            str,
            Doc(
                "A  URL to the OpenAPI Specification for the API, used in the OpenAPI documentation."
            ),
        ] = "/openapi.json",
        server_error_handler: Annotated[
            Optional[ServerErrHandlerType],
            Doc(
                """
                        A function in sillo responsible for handling server-side exceptions by logging errors, reporting issues, or initiating recovery mechanisms. It prevents crashes by intercepting unexpected failures, ensuring the application remains stable and operational. This function provides a structured approach to error management, allowing developers to define custom handling strategies such as retrying failed requests, sending alerts, or gracefully degrading functionality. By centralizing error processing, it improves maintainability and observability, making debugging and monitoring more efficient. Additionally, it ensures that critical failures do not disrupt the entire system, allowing services to continue running while appropriately managing faults and failures."""
            ),
        ] = None,
        lifespan: Annotated[
            Optional[lifespan_manager],
            Doc("""
                    A function in sillo responsible for handling ASGI lifespan protocol events. It handles the startup and shutdown events emitted by the ASGI server. It allows you to perform actions such as initializing resources, opening connections, and tearing down resources during application startup and shutdown.

                    This function is called when the application starts and when it shuts down. It receives a `Receive` function to receive lifespan events and a `Send` function to send lifespan events.

                    The `lifespan_manager` function takes two arguments: `self` and `receive` and `send`. It returns an `AsyncContextManager` that can be used to manage the lifespan of the application.

                    You can use this function to perform actions such as connecting to a database, initializing a cache, or registering a signal handler.
                """),
        ] = None,
        routes: Annotated[
            Sequence[BaseRoute],
            Doc("""
                    A list of routes for the application. These routes define the URLs that the application will handle and the handlers that will be called when those URLs are accessed.

                    Each route is an instance of the `Route` class and defines the URL path, the handler function, and any additional middleware or dependencies that should be applied to that route.

                    You can add routes to the application using the `add_route` method of the `Router` class.
                """),
        ] = [],
        dependencies: Annotated[
            Optional[list[Depend]],
            Doc("""
                    A list of dependencies for the application. These dependencies are used to resolve dependencies within the application.

                    A dependency is a function that takes a `Request` object and returns the value that should be injected into the dependency.

                    You can add dependencies to the application using the `add_dependency` method of the `Router` class.
                """),
        ] = None,
        route_class: Annotated[
            Type[Route],
            Doc("""
                    The class used to create routes. This can be a custom route class that inherits from `Route`.
                """),
        ] = Route,
        strict_validation: Annotated[
            bool,
            Doc("""
                    Validate every declared parameter with Pydantic, including those
                    written in the pre-Pydantic style that only supply a default.
                    Missing or malformed values then return 422 instead of the
                    historical 500. Off by default so existing applications keep
                    their current behavior; recommended for new applications.
                """),
        ] = False,
    ) -> None:
        """
        Initialize the sillo application with all core subsystems.

        Constructs the root router, configures OpenAPI documentation settings,
        registers default security schemes, sets up the event emitter, and
        wires internal bookkeeping structures such as middleware lists and
        lifecycle handler queues. The ``setup`` method is called at the end
        of initialization to mount built-in documentation routes.

        Args:
            debug: Whether to enable debug mode. When ``True``, detailed
                error traces are included in responses. Defaults to ``True``.
            title: The display title used in generated OpenAPI documentation.
                Falls back to ``"sillo API"`` when not provided.
            version: The semantic version string shown in OpenAPI output.
                Defaults to ``"1.0.0"`` when not provided.
            description: A human-readable description of the API surfaced in
                OpenAPI documentation. Defaults to ``"sillo Asgi framework"``.
            contact: Optional contact information embedded in the OpenAPI schema.
            license: Optional license metadata embedded in the OpenAPI schema.
            servers: An optional list of server entries for the OpenAPI schema.
            terms_of_service: Optional URL pointing to the API terms of service.
            swagger_docs: The URL path at which the Swagger UI is served.
                Defaults to ``"/docs"``.
            redoc_docs: The URL path at which the Redoc UI is served.
                Defaults to ``"/redoc"``.
            openapi_url: The URL path serving the raw OpenAPI JSON schema.
                Defaults to ``"/openapi.json"``.
            server_error_handler: An optional callable invoked when an
                unhandled exception occurs during request processing.
            lifespan: An optional async context manager factory for managing
                application startup and shutdown lifecycle events.
            routes: An initial sequence of route objects to register with the
                root router. Defaults to an empty list.
            dependencies: An optional list of global dependency injection
                definitions applied across all routes.
            route_class: The class used to instantiate new routes. Allows
                substitution of a custom ``Route`` subclass. Defaults to
                :class:`Route`.
            strict_validation: When ``True``, parameters declared in the
                pre-Pydantic style are validated too, so a missing or malformed
                value produces a 422 rather than a 500. Defaults to ``False``
                to preserve the behavior of existing applications.

        Returns:
            None

        Raises:
            None
        """
        self.debug = debug
        self.dependencies = dependencies or []
        self.custom_encoders: Dict[type, Callable[[Any], Any]] = {}

        self.http_middleware: List[Middleware] = []
        self.startup_handlers: List[Callable[[], Awaitable[None]]] = []
        self.shutdown_handlers: List[Callable[[], Awaitable[None]]] = []
        self.server_error_handler = server_error_handler

        self.route_class = route_class
        self.strict_validation = strict_validation
        self.app = Router(
            routes=routes,
            dependencies=self.dependencies,
            route_class=self.route_class,
            strict_validation=strict_validation,
        )
        self.exceptions_handler = ExceptionMiddleware()
        self.router = self.app
        self.route = self.router.route
        self.lifespan_context: Optional[lifespan_manager] = lifespan
        self.state: dict[str, Any] = {}

        self.openapi_config = OpenAPIConfig(
            title=title or "sillo API",
            version=version or "1.0.0",
            description=description or "sillo Asgi framework",
            license=license,
            contact=contact,
            servers=servers,
            termsOfService=terms_of_service,
        )

        self.openapi_config.add_security_scheme(
            "bearerAuth", HTTPBearer(type="http", scheme="bearer", bearerFormat="JWT")
        )

        self.openapi = APIDocumentation(
            config=self.openapi_config,
            swagger_url=swagger_docs,
            redoc_url=redoc_docs,
            openapi_url=openapi_url,
        )

        self.events = EventEmitter()
        self.title = title or "sillo API"
        self.setup()

    def setup(self) -> None:
        """
        Register built-in documentation routes for OpenAPI, Swagger UI, and Redoc.

        This method is invoked automatically during application initialization
        to mount three internal GET endpoints that serve the raw OpenAPI JSON
        schema, the interactive Swagger UI, and the Redoc documentation viewer.
        All three routes are excluded from the generated OpenAPI schema to
        prevent recursive documentation entries. The routes respect the
        application's mount path by reading ``root_path`` from the ASGI scope.

        Args:
            None

        Returns:
            None

        Raises:
            None
        """

        @self.get(self.openapi.openapi_url, exclude_from_schema=True)
        async def serve_openapi(request: "Request", response: "Response"):
            root_path = request.scope.get("root_path", "")

            return response.json(
                self.openapi.get_openapi(self.router, current_prefix=root_path)
            )

        @self.get(self.openapi.swagger_url, exclude_from_schema=True)
        async def swagger_ui(request: "Request", response: "Response"):
            # Get the current mount path from the request scope
            root_path = request.scope.get("root_path", "")
            openapi_url = root_path + self.openapi.openapi_url
            return response.html(self.openapi._generate_swagger_ui(openapi_url))

        @self.get(self.openapi.redoc_url, exclude_from_schema=True)
        async def redoc_ui(request: "Request", response: "Response"):
            # Get the current mount path from the request scope
            root_path = request.scope.get("root_path", "")
            openapi_url = root_path + self.openapi.openapi_url
            return response.html(self.openapi._generate_redoc_ui(openapi_url))

    def on_startup(
        self, handler: Callable[[], Awaitable[None]]
    ) -> Callable[[], Awaitable[None]]:
        """
        Registers a startup handler that executes when the application starts.

        This method allows you to define functions that will be executed before
        the application begins handling requests. It is useful for initializing
        resources such as database connections, loading configuration settings,
        or preparing caches.

        The provided function must be asynchronous (`async def`) since it
        will be awaited during the startup phase.

        Args:
            handler (Callable): An asynchronous function to be executed at startup.

        Returns:
            Callable: The same handler function, allowing it to be used as a decorator.

        Example:
            ```python

            @app.on_startup
            async def connect_to_db():
                global db
                db = await Database.connect("postgres://user:password@localhost:5432/mydb")
                print("Database connection established.")

            @app.on_startup
            async def cache_warmup():
                global cache
                cache = await load_initial_cache()
                print("Cache warmed up and ready.")
            ```

        In this example:
        - `connect_to_db` establishes a database connection before the app starts.
        - `cache_warmup` preloads data into a cache for faster access.

        These functions will be executed in the order they are registered when the
        application starts.
        """
        self.startup_handlers.append(handler)
        return handler

    def on_shutdown(
        self, handler: Callable[[], Awaitable[None]]
    ) -> Callable[[], Awaitable[None]]:
        """
        Registers a shutdown handler that executes when the application is shutting down.

        This method allows you to define functions that will be executed when the
        application is stopping. It is useful for cleaning up resources such as
        closing database connections, saving application state, or gracefully
        terminating background tasks.

        The provided function must be asynchronous (`async def`) since it will be
        awaited during the shutdown phase.

        Args:
            handler (Callable): An asynchronous function to be executed during shutdown.

        Returns:
            Callable: The same handler function, allowing it to be used as a decorator.

        Example:
            ```python
            app = NexioApp()

            @app.on_shutdown
            async def disconnect_db():
                global db
                await db.disconnect()
                print("Database connection closed.")

            @app.on_shutdown
            async def clear_cache():
                global cache
                await cache.clear()
                print("Cache cleared before shutdown.")
            ```

        In this example:
        - `disconnect_db` ensures that the database connection is properly closed.
        - `clear_cache` removes cached data to free up memory before the app stops.

        These functions will be executed in the order they are registered when the
        application is shutting down.
        """
        self.shutdown_handlers.append(handler)
        return handler

    async def _startup(self) -> None:
        """
        Execute all registered startup handlers sequentially.

        Iterates through the ``startup_handlers`` list and invokes each
        handler in registration order. Both async and sync callables are
        supported; async handlers are awaited while sync handlers are
        called directly. This method is invoked by the ASGI lifespan
        protocol when no custom lifespan context manager is configured.

        Args:
            None

        Returns:
            None

        Raises:
            Exception: Propagates any exception raised by a startup handler
                to the caller, which typically results in a
                ``lifespan.startup.failed`` ASGI message.
        """
        for handler in self.startup_handlers:
            if is_async_callable(handler):
                await handler()
            else:
                handler()

    async def _shutdown(self) -> None:
        """
        Execute all registered shutdown handlers sequentially.

        Iterates through the ``shutdown_handlers`` list and invokes each
        handler in registration order. Both async and sync callables are
        supported; async handlers are awaited while sync handlers are
        called directly. This method is invoked by the ASGI lifespan
        protocol when no custom lifespan context manager is configured.

        Args:
            None

        Returns:
            None

        Raises:
            Exception: Propagates any exception raised by a shutdown handler
                to the caller, which typically results in a
                ``lifespan.shutdown.failed`` ASGI message.
        """
        for handler in self.shutdown_handlers:
            if is_async_callable(handler):
                await handler()
            else:
                handler()

    @staticmethod
    def _is_async_context_manager(obj: Any) -> bool:
        """
        Determine whether an object implements the async context manager protocol.

        Checks for the presence of both ``__aenter__`` and ``__aexit__``
        dunder methods on the provided object. This is used internally by
        the lifespan handler to decide whether to await or synchronously
        invoke the context manager entry and exit methods.

        Args:
            obj: Any Python object to inspect for async context manager
                protocol compliance.

        Returns:
            bool: ``True`` if the object implements both ``__aenter__``
                and ``__aexit__``, ``False`` otherwise.

        Raises:
            None
        """
        return hasattr(obj, "__aenter__") and hasattr(obj, "__aexit__")

    async def handle_lifespan(self, receive: Receive, send: Send) -> None:
        """
        Handle the ASGI lifespan protocol for application startup and shutdown.

        Listens for ``lifespan.startup`` and ``lifespan.shutdown`` messages
        from the ASGI server. On startup, either the custom lifespan context
        manager is entered or the registered startup handlers are executed.
        On shutdown, the corresponding cleanup is performed. State returned
        from the lifespan context manager is merged into ``self.state``.

        Args:
            receive: An async callable that yields ASGI scope messages from
                the server. Used to receive lifespan event notifications.
            send: An async callable that sends ASGI messages back to the
                server, such as startup complete or shutdown failed signals.

        Returns:
            None

        Raises:
            None: Exceptions during startup or shutdown are caught internally
                and communicated via ``lifespan.startup.failed`` or
                ``lifespan.shutdown.failed`` messages.
        """

        while True:
            message: Message = await receive()
            if message["type"] == "lifespan.startup":
                try:
                    if self.lifespan_context:
                        # If a lifespan context manager is provided, use it
                        self.lifespan_manager: Any = self.lifespan_context(self)
                        if self._is_async_context_manager(self.lifespan_manager):
                            returned_state = await self.lifespan_manager.__aenter__()  # ty: ignore[unresolved-attribute]
                        else:
                            returned_state = self.lifespan_manager.__enter__()  # ty: ignore[unresolved-attribute]
                        if returned_state:
                            self.state.update(returned_state)
                    else:
                        # Otherwise, fall back to the default startup handlers
                        await self._startup()
                    await send({"type": "lifespan.startup.complete"})
                except Exception as e:
                    await send({"type": "lifespan.startup.failed", "message": str(e)})
                    return

            elif message["type"] == "lifespan.shutdown":
                try:
                    if self.lifespan_context:
                        # If a lifespan context manager is provided, use it
                        if self._is_async_context_manager(self.lifespan_manager):
                            await self.lifespan_manager.__aexit__(None, None, None)  # ty: ignore[unresolved-attribute]
                        else:
                            self.lifespan_manager.__exit__(None, None, None)  # ty: ignore[unresolved-attribute]
                    else:
                        # Otherwise, fall back to the default shutdown handlers
                        await self._shutdown()
                    await send({"type": "lifespan.shutdown.complete"})
                    return
                except Exception as e:
                    await send({"type": "lifespan.shutdown.failed", "message": str(e)})
                    return

    def use(
        self,
        middleware: Annotated[
            MiddlewareType,
            Doc(
                "A callable middleware function that processes requests and responses."
            ),
        ],
    ) -> None:
        """
        Adds middleware to the application.

        Middleware functions are executed in the request-response lifecycle, allowing
        modifications to requests before they reach the route handler and responses
        before they are sent back to the client.

        Args:
            middleware (MiddlewareType): A callable that takes a `Request`, `Response`,
            and a `Callable` (next middleware or handler) and returns a `Response`.

        Returns:
            None

        Example:
            ```python
            def logging_middleware(request: Request, response: Response, next_call: Callable) -> Response:
                print(f"Request received: {request.method} {request.url}")
                return next_call()

            app.use(logging_middleware)
            ```
        """

        self.http_middleware.insert(
            0,
            Middleware(ASGIRequestResponseBridge, dispatch=middleware),
        )

    def add_encoder(
        self,
        type_: type,
        encoder: Callable[[Any], Any],
    ) -> None:
        """Register a custom JSON encoder for a type across the application.

        Registered encoders are applied automatically whenever sillo serializes
        a response to JSON — including values returned directly from handlers.
        They are merged on top of the built-in type encoders and also feed the
        global :func:`sillo.encoding.register_encoder` registry.

        Args:
            type_: The Python type (or abstract base) to encode.
            encoder: Callable receiving an instance of ``type_`` and returning a
                JSON-serializable value.

        Example:
            ```python
            from decimal import Decimal

            app.add_encoder(Decimal, lambda d: float(d))

            @app.get("/price")
            async def price(request, response):
                return {"total": Decimal("19.99")}
            ```
        """

        self.custom_encoders[type_] = encoder
        CUSTOM_ENCODERS[type_] = encoder
        register_encoder(type_, encoder)

    def add_ws_route(
        self,
        route: Optional[
            Annotated[
                WebsocketRoute,
                Doc("An instance of the Route class representing a WebSocket route."),
            ]
        ] = None,
        path: Optional[str] = None,
        handler: Optional[WsHandlerType] = None,
    ) -> None:
        """
        Adds a WebSocket route to the application.

        This method registers a WebSocket route, allowing the application to handle WebSocket connections.

        Args:
            route (Route): The WebSocket route configuration.

        Returns:
            None

        Example:
            ```python
            route = Route("/ws/chat", chat_handler)
            app.add_ws_route(route)
            ```
        """

        if route:
            if (not path or path == route.raw_path) and (
                not handler or handler == route.handler
            ):
                self.router.add_ws_route(route)
                return

        if path is None or handler is None:
            raise ValueError(
                "path and handler are required when 'route' is not provided."
            )

        self.router.add_ws_route(WebsocketRoute(path, handler))

    def frontend(
        self,
        path: str = "/",
        directory: Union[str, "Path"] = "dist",
        fallback: "Optional[Union[str, bool]]" = "auto",
        name: Optional[str] = None,
        cache_control: Optional[str] = None,
    ) -> None:
        """Mount a frontend SPA build directory with fallback routing.

        Convenience wrapper that delegates to ``self.router.frontend()``.
        API routes registered *before* this call take precedence.

        Args:
            path: URL path prefix (default ``"/"``).
            directory: Path to the built frontend directory.
            fallback: ``"auto"`` (default), an explicit filename, or ``None``/``False``.
            name: Optional route group name.
            cache_control: Optional ``Cache-Control`` header.

        Example::

            app = silloApp()

            @app.get("/api/health")
            async def health(request, response):
                return response.json({"status": "ok"})

            # Serve the SPA at the root — API routes take precedence
            app.frontend("/", directory="./frontend/dist")
        """
        self.router.frontend(
            path=path,
            directory=directory,
            fallback=fallback,
            name=name,
            cache_control=cache_control,
        )

    def mount_router(self, router: Router, name: Optional[str] = None) -> None:
        """
        Mounts a router and all its routes to the application using the router's prefix.

        This method allows integrating another `Router` instance, registering all its
        defined routes into the current application. It is useful for modularizing routes
        and organizing large applications.

        Args:
            router (Router): The `Router` instance whose routes will be added.

        Returns:
            None

        Example:
            ```python
            user_router = Router(prefix="/users")

            @user_router.route("/list", methods=["GET"])
            def get_users(request, response):
                 response.json({"users": ["Alice", "Bob"]})

            app.mount_router(user_router)  # Mounts the user routes into the main app
            ```
        """
        self.router.mount_router(router, name=name)

    def handle_request(self, scope: Scope, receive: Receive, send: Send):
        """
        Build the middleware chain and dispatch an incoming ASGI request.

        Constructs a layered middleware stack consisting of the server error
        middleware, all registered HTTP middleware, and the exception handler
        middleware. The chain is assembled in reverse order so that the
        outermost layer processes the request first. The root router is used
        as the innermost application in the chain.

        Args:
            scope: The ASGI connection scope dictionary containing metadata
                about the incoming request such as type, path, and headers.
            receive: An async callable that yields ASGI messages from the
                client, such as request body chunks.
            send: An async callable that sends ASGI messages back to the
                client, such as response headers and body chunks.

        Returns:
            An awaitable coroutine representing the fully wrapped ASGI
            application invocation that processes the request through
            all middleware layers and returns a response.

        Raises:
            None: Exceptions are handled by the middleware layers in the
                chain, specifically the server error and exception middleware.
        """
        app = self.app
        middleware = (
            [
                Middleware(
                    ASGIRequestResponseBridge,
                    dispatch=ServerErrorMiddleware(
                        handler=self.server_error_handler, debug=self.debug
                    ),
                )
            ]
            + self.http_middleware
            + [Middleware(ASGIRequestResponseBridge, dispatch=self.exceptions_handler)]
        )
        for cls, args, kwargs in reversed(middleware):
            app = cls(app, *args, **kwargs)
        return app(scope, receive, send)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """
        ASGI application entry point invoked by the server for every connection.

        Injects the application instance, base application reference, and
        global state dictionary into the ASGI scope for downstream access.
        Dispatches the connection to the appropriate handler based on the
        scope type: lifespan connections are routed to ``handle_lifespan``,
        while HTTP and WebSocket connections are routed to ``handle_request``.

        Args:
            scope: The ASGI connection scope dictionary containing metadata
                such as the connection type, path, headers, and query string.
            receive: An async callable that yields ASGI messages from the
                client throughout the connection lifecycle.
            send: An async callable that sends ASGI messages back to the
                client, such as response start, body, and disconnect signals.

        Returns:
            None

        Raises:
            None: Exceptions are caught and handled by the middleware layers
                within ``handle_request`` or by the lifespan error handling
                within ``handle_lifespan``.
        """
        scope["app"] = self
        scope["base_app"] = self
        scope["global_state"] = self.state

        if scope["type"] == "lifespan":
            await self.handle_lifespan(receive, send)
        elif scope["type"] in ["http", "websocket"]:
            await self.handle_request(scope, receive, send)

    def get(
        self,
        path: Annotated[
            str,
            Doc("""
                URL path pattern for the GET endpoint.
                Supports path parameters using {param} syntax.
                Example: '/users/{user_id}'
            """),
        ],
        handler: Annotated[
            Optional[HandlerType],
            Doc("""
                Async handler function for GET requests.
                Receives (request, response) and returns response or raw data.
                
                Example:
                async def get_user(request, response):
                    user = await get_user_from_db(request.path_params['user_id'])
                    return response.json(user)
            """),
        ] = None,
        name: Annotated[
            Optional[str],
            Doc("""
                Unique route identifier for URL generation.
                Example: 'get-user-by-id'
            """),
        ] = None,
        summary: Annotated[
            Optional[str],
            Doc("""
                Brief summary for OpenAPI documentation.
                Example: 'Retrieves a user by ID'
            """),
        ] = None,
        description: Annotated[
            Optional[str],
            Doc("""
                Detailed description for OpenAPI documentation.
                Example: 'Returns full user details including profile information'
            """),
        ] = None,
        responses: Annotated[
            Optional[ArgsType],
            Doc("""
                Response models by status code.
                Example: 
                {
                    200: UserSchema,
                    404: {"description": "User not found"},
                    500: {"description": "Server error"}
                }
            """),
        ] = None,
        request_model: Annotated[
            Optional[ArgsType],
            Doc("""
                Pydantic model for request validation (query params).
                Example:
                class UserQuery(BaseModel):
                    active_only: bool = True
                    limit: int = 100
            """),
        ] = None,
        middleware: Annotated[
            List[Any],
            Doc("""
                List of route-specific middleware functions.
                Example: [auth_required, rate_limit]
            """),
        ] = [],
        tags: Annotated[
            Optional[List[str]],
            Doc("""
                OpenAPI tags for grouping related endpoints.
                Example: ["Users", "Public"]
            """),
        ] = None,
        security: Annotated[
            Optional[List[Dict[str, List[str]]]],
            Doc("""
                Security requirements for OpenAPI docs.
                Example: [{"BearerAuth": []}]
            """),
        ] = None,
        operation_id: Annotated[
            Optional[str],
            Doc("""
                Unique operation identifier for OpenAPI.
                Example: 'users.get_by_id'
            """),
        ] = None,
        deprecated: Annotated[
            bool,
            Doc("""
                Mark endpoint as deprecated in docs.
                Example: True
            """),
        ] = False,
        parameters: Annotated[
            List[Parameter],
            Doc("""
                Additional OpenAPI parameter definitions.
                Example: [Parameter(name="fields", in_="query", description="Fields to include")]
            """),
        ] = [],
        exclude_from_schema: Annotated[
            bool,
            Doc("""
                Exclude this route from OpenAPI docs.
                Example: True for internal endpoints
            """),
        ] = False,
        auth: Annotated[
            Optional[Any],
            Doc("Route-level :class:`sillo.auth.useAuth` gate."),
        ] = None,
        **kwargs: Annotated[
            Any,
            Doc("""
                Additional route metadata.
                Example: {"x-internal": True}
            """),
        ],
    ) -> Callable[..., Any]:
        """
        Register a GET endpoint with comprehensive OpenAPI support.

        Examples:
            1. Basic GET endpoint:
            @router.get("/users")
            async def get_users(request: Request, response: Response):
                users = await get_all_users()
                return response.json(users)

            2. GET with path parameter and response model:
            @router.get(
                "/users/{user_id}",
                responses={
                    200: UserResponse,
                    404: {"description": "User not found"}
                }
            )
            async def get_user(request: Request, response: Response):
                user_id = request.path_params['user_id']
                user = await get_user_by_id(user_id)
                if not user:
                    return response.status(404).json({"error": "User not found"})
                return response.json(user)

            3. GET with query parameters:
            class UserQuery(BaseModel):
                active: bool = True
                limit: int = 100

            @router.get("/users/search", request_model=UserQuery)
            async def search_users(request: Request, response: Response):
                query = request.query_params
                users = await search_users(
                    active=query['active'],
                    limit=query['limit']
                )
                return response.json(users)
        """

        return self.route(
            path=path,
            handler=handler,
            methods=["GET"],
            name=name,
            summary=summary,
            description=description,
            responses=responses,
            request_model=request_model,
            request_content_type="application/json",
            middleware=middleware,
            tags=tags,
            security=security,
            operation_id=operation_id,
            deprecated=deprecated,
            parameters=parameters,
            exclude_from_schema=exclude_from_schema,
            auth=auth,
            **kwargs,
        )

    def post(
        self,
        path: Annotated[
            str,
            Doc("""
                URL path pattern for the POST endpoint.
                Example: '/api/v1/users'
            """),
        ],
        handler: Annotated[
            Optional[HandlerType],
            Doc("""
                Async handler function for POST requests.
                Example:
                async def create_user(request, response):
                    user_data = request.json
                    return response.json(user_data, status=201)
            """),
        ] = None,
        name: Annotated[
            Optional[str],
            Doc("""
                Unique route name for URL generation.
                Example: 'api-v1-create-user'
            """),
        ] = None,
        summary: Annotated[
            Optional[str],
            Doc("""
                Brief endpoint summary.
                Example: 'Create new user'
            """),
        ] = None,
        description: Annotated[
            Optional[str],
            Doc("""
                Detailed endpoint description.
                Example: 'Creates new user with provided data'
            """),
        ] = None,
        responses: Annotated[
            Optional[ArgsType],
            Doc("""
                Response schemas by status code.
                Example: {
                    201: UserSchema,
                    400: {"description": "Invalid input"},
                    409: {"description": "User already exists"}
                }
            """),
        ] = None,
        request_model: Annotated[
            Optional[ArgsType],
            Doc("""
                Model for request body validation.
                Example:
                class UserCreate(BaseModel):
                    username: str
                    email: EmailStr
                    password: str
            """),
        ] = None,
        request_content_type: Annotated[
            Literal[
                "application/json",
                "multipart/form-data",
                "application/x-www-form-urlencoded",
            ],
            Doc(
                "Content type for the request body in OpenAPI docs. Defaults to 'application/json'."
            ),
        ] = "application/json",
        middleware: Annotated[
            List[Any],
            Doc("""
                Route-specific middleware.
                Example: [rate_limit(10), validate_content_type('json')]
            """),
        ] = [],
        tags: Annotated[
            Optional[List[str]],
            Doc("""
                OpenAPI tags for grouping.
                Example: ["User Management"]
            """),
        ] = None,
        security: Annotated[
            Optional[List[Dict[str, List[str]]]],
            Doc("""
                Security requirements.
                Example: [{"BearerAuth": []}]
            """),
        ] = None,
        operation_id: Annotated[
            Optional[str],
            Doc("""
                Unique operation ID.
                Example: 'createUser'
            """),
        ] = None,
        deprecated: Annotated[
            bool,
            Doc("""
                Mark as deprecated.
                Example: False
            """),
        ] = False,
        parameters: Annotated[
            List[Parameter],
            Doc("""
                Additional parameters.
                Example: [Parameter(name="X-Request-ID", in_="header")]
            """),
        ] = [],
        exclude_from_schema: Annotated[
            bool,
            Doc("""
                Hide from OpenAPI docs.
                Example: False
            """),
        ] = False,
        auth: Annotated[
            Optional[Any],
            Doc("Route-level :class:`sillo.auth.useAuth` gate."),
        ] = None,
        **kwargs: Annotated[
            Any,
            Doc("""
                Additional metadata.
                Example: {"x-audit-log": True}
            """),
        ],
    ) -> Callable[..., Any]:
        """
        Register a POST endpoint with the application.

        Examples:
            1. Simple POST endpoint:
            @router.post("/messages")
            async def create_message(request, response):
                message = await Message.create(**request.json)
                return response.json(message, status=201)

            2. POST with request validation:
            class ProductCreate(BaseModel):
                name: str
                price: float
                category: str

            @router.post(
                "/products",
                request_model=ProductCreate,
                responses={201: ProductSchema}
            )
            async def create_product(request, response):
                product = await Product.create(**request.validated_data)
                return response.json(product, status=201)

            3. POST with file upload:
            @router.post("/upload")
            async def upload_file(request, response):
                file = request.files.get('file')
                # Process file upload
                return response.json({"filename": file.filename})
        """
        return self.route(
            path=path,
            methods=["POST"],
            handler=handler,
            name=name,
            summary=summary,
            description=description,
            responses=responses,
            request_model=request_model,
            request_content_type=request_content_type,
            middleware=middleware,
            tags=tags,
            security=security,
            operation_id=operation_id,
            deprecated=deprecated,
            parameters=parameters,
            exclude_from_schema=exclude_from_schema,
            auth=auth,
            **kwargs,
        )

    def delete(
        self,
        path: Annotated[
            str,
            Doc("""
                URL path pattern for the DELETE endpoint.
                Example: '/api/v1/users/{id}'
            """),
        ],
        handler: Annotated[
            Optional[HandlerType],
            Doc("""
                Async handler function for DELETE requests.
                Example:
                async def delete_user(request, response):
                    user_id = request.path_params['id']
                    return response.json({"deleted": user_id})
            """),
        ] = None,
        name: Annotated[
            Optional[str],
            Doc("""
                Unique route name for URL generation.
                Example: 'api-v1-delete-user'
            """),
        ] = None,
        summary: Annotated[
            Optional[str],
            Doc("""
                Brief endpoint summary.
                Example: 'Delete user account'
            """),
        ] = None,
        description: Annotated[
            Optional[str],
            Doc("""
                Detailed endpoint description.
                Example: 'Permanently deletes user account and all associated data'
            """),
        ] = None,
        responses: Annotated[
            Optional[ArgsType],
            Doc("""
                Response schemas by status code.
                Example: {
                    204: None,
                    404: {"description": "User not found"},
                    403: {"description": "Forbidden"}
                }
            """),
        ] = None,
        request_model: Annotated[
            Optional[ArgsType],
            Doc("""
                Model for request validation.
                Example:
                class DeleteConfirmation(BaseModel):
                    confirm: bool
            """),
        ] = None,
        middleware: Annotated[
            List[Any],
            Doc("""
                Route-specific middleware.
                Example: [admin_required, confirm_action]
            """),
        ] = [],
        tags: Annotated[
            Optional[List[str]],
            Doc("""
                OpenAPI tags for grouping.
                Example: ["User Management"]
            """),
        ] = None,
        security: Annotated[
            Optional[List[Dict[str, List[str]]]],
            Doc("""
                Security requirements.
                Example: [{"BearerAuth": []}]
            """),
        ] = None,
        operation_id: Annotated[
            Optional[str],
            Doc("""
                Unique operation ID.
                Example: 'deleteUser'
            """),
        ] = None,
        deprecated: Annotated[
            bool,
            Doc("""
                Mark as deprecated.
                Example: False
            """),
        ] = False,
        parameters: Annotated[
            List[Parameter],
            Doc("""
                Additional parameters.
                Example: [Parameter(name="confirm", in_="query")]
            """),
        ] = [],
        exclude_from_schema: Annotated[
            bool,
            Doc("""
                Hide from OpenAPI docs.
                Example: False
            """),
        ] = False,
        auth: Annotated[
            Optional[Any],
            Doc("Route-level :class:`sillo.auth.useAuth` gate."),
        ] = None,
        **kwargs: Annotated[
            Any,
            Doc("""
                Additional metadata.
                Example: {"x-destructive": True}
            """),
        ],
    ) -> Callable[..., Any]:
        """
        Register a DELETE endpoint with the application.

        Examples:
            1. Simple DELETE endpoint:
            @router.delete("/users/{id}")
            async def delete_user(request, response):
                await User.delete(request.path_params['id'])
                return response.status(204)

            2. DELETE with confirmation:
            @router.delete(
                "/account",
                responses={
                    204: None,
                    400: {"description": "Confirmation required"}
                }
            )
            async def delete_account(request, response):
                if not request.query_params.get('confirm'):
                    return response.status(400)
                await request.user.delete()
                return response.status(204)

            3. Soft DELETE:
            @router.delete("/posts/{id}")
            async def soft_delete_post(request, response):
                await Post.soft_delete(request.path_params['id'])
                return response.json({"status": "archived"})
        """
        return self.route(
            path=path,
            methods=["DELETE"],
            handler=handler,
            name=name,
            summary=summary,
            description=description,
            responses=responses,
            request_model=request_model,
            middleware=middleware,
            tags=tags,
            security=security,
            operation_id=operation_id,
            deprecated=deprecated,
            parameters=parameters,
            exclude_from_schema=exclude_from_schema,
            request_content_type="application/json",
            **kwargs,
        )

    def put(
        self,
        path: Annotated[
            str,
            Doc("""
                URL path pattern for the PUT endpoint.
                Example: '/api/v1/users/{id}'
            """),
        ],
        handler: Annotated[
            Optional[HandlerType],
            Doc("""
                Async handler function for PUT requests.
                Example:
                async def update_user(request, response):
                    user_id = request.path_params['id']
                    return response.json({"updated": user_id})
            """),
        ] = None,
        name: Annotated[
            Optional[str],
            Doc("""
                Unique route name for URL generation.
                Example: 'api-v1-update-user'
            """),
        ] = None,
        summary: Annotated[
            Optional[str],
            Doc("""
                Brief endpoint summary.
                Example: 'Update user details'
            """),
        ] = None,
        description: Annotated[
            Optional[str],
            Doc("""
                Detailed endpoint description.
                Example: 'Full update of user resource'
            """),
        ] = None,
        responses: Annotated[
            Optional[ArgsType],
            Doc("""
                Response schemas by status code.
                Example: {
                    200: UserSchema,
                    400: {"description": "Invalid input"},
                    404: {"description": "User not found"}
                }
            """),
        ] = None,
        request_model: Annotated[
            Optional[ArgsType],
            Doc("""
                Model for request body validation.
                Example:
                class UserUpdate(BaseModel):
                    email: Optional[EmailStr]
                    password: Optional[str]
            """),
        ] = None,
        middleware: Annotated[
            List[Any],
            Doc("""
                Route-specific middleware.
                Example: [owner_required, validate_etag]
            """),
        ] = [],
        tags: Annotated[
            Optional[List[str]],
            Doc("""
                OpenAPI tags for grouping.
                Example: ["User Management"]
            """),
        ] = None,
        security: Annotated[
            Optional[List[Dict[str, List[str]]]],
            Doc("""
                Security requirements.
                Example: [{"BearerAuth": []}]
            """),
        ] = None,
        operation_id: Annotated[
            Optional[str],
            Doc("""
                Unique operation ID.
                Example: 'updateUser'
            """),
        ] = None,
        deprecated: Annotated[
            bool,
            Doc("""
                Mark as deprecated.
                Example: False
            """),
        ] = False,
        parameters: Annotated[
            List[Parameter],
            Doc("""
                Additional parameters.
                Example: [Parameter(name="If-Match", in_="header")]
            """),
        ] = [],
        exclude_from_schema: Annotated[
            bool,
            Doc("""
                Hide from OpenAPI docs.
                Example: False
            """),
        ] = False,
        auth: Annotated[
            Optional[Any],
            Doc("Route-level :class:`sillo.auth.useAuth` gate."),
        ] = None,
        request_content_type: Annotated[
            Literal[
                "application/json",
                "application/x-www-form-urlencoded",
                "multipart/form-data",
            ],
            Doc("""
                Request content type.
                Example: 'application/json'
            """),
        ] = "application/json",
        **kwargs: Annotated[
            Any,
            Doc("""
                Additional metadata.
                Example: {"x-idempotent": True}
            """),
        ],
    ) -> Callable[..., Any]:
        """
        Register a PUT endpoint with the application.

        Examples:
            1. Simple PUT endpoint:
            @router.put("/users/{id}")
            async def update_user(request, response):
                user_id = request.path_params['id']
                await User.update(user_id, **request.json)
                return response.json({"status": "updated"})

            2. PUT with full resource replacement:
            @router.put(
                "/articles/{slug}",
                request_model=ArticleUpdate,
                responses={
                    200: ArticleSchema,
                    404: {"description": "Article not found"}
                }
            )
            async def replace_article(request, response):
                article = await Article.replace(
                    request.path_params['slug'],
                    request.validated_data
                )
                return response.json(article)

            3. PUT with conditional update:
            @router.put("/resources/{id}")
            async def update_resource(request, response):
                if request.headers.get('If-Match') != expected_etag:
                    return response.status(412)
                # Process update
                return response.json({"status": "success"})
        """
        return self.route(
            path=path,
            methods=["PUT"],
            handler=handler,
            name=name,
            summary=summary,
            description=description,
            responses=responses,
            request_model=request_model,
            request_content_type=request_content_type,
            middleware=middleware,
            tags=tags,
            security=security,
            operation_id=operation_id,
            deprecated=deprecated,
            parameters=parameters,
            exclude_from_schema=exclude_from_schema,
            auth=auth,
            **kwargs,
        )

    def patch(
        self,
        path: Annotated[
            str,
            Doc("""
                URL path pattern for the PATCH endpoint.
                Example: '/api/v1/users/{id}'
            """),
        ],
        handler: Annotated[
            Optional[HandlerType],
            Doc("""
                Async handler function for PATCH requests.
                Example:
                async def partial_update_user(request, response):
                    user_id = request.path_params['id']
                    return response.json({"updated": user_id})
            """),
        ] = None,
        name: Annotated[
            Optional[str],
            Doc("""
                Unique route name for URL generation.
                Example: 'api-v1-partial-update-user'
            """),
        ] = None,
        summary: Annotated[
            Optional[str],
            Doc("""
                Brief endpoint summary.
                Example: 'Partially update user details'
            """),
        ] = None,
        description: Annotated[
            Optional[str],
            Doc("""
                Detailed endpoint description.
                Example: 'Partial update of user resource'
            """),
        ] = None,
        responses: Annotated[
            Optional[ArgsType],
            Doc("""
                Response schemas by status code.
                Example: {
                    200: UserSchema,
                    400: {"description": "Invalid input"},
                    404: {"description": "User not found"}
                }
            """),
        ] = None,
        request_model: Annotated[
            Optional[ArgsType],
            Doc("""
                Model for request body validation.
                Example:
                class UserPatch(BaseModel):
                    email: Optional[EmailStr] = None
                    password: Optional[str] = None
            """),
        ] = None,
        middleware: Annotated[
            List[Any],
            Doc("""
                Route-specific middleware.
                Example: [owner_required, validate_patch]
            """),
        ] = [],
        tags: Annotated[
            Optional[List[str]],
            Doc("""
                OpenAPI tags for grouping.
                Example: ["User Management"]
            """),
        ] = None,
        security: Annotated[
            Optional[List[Dict[str, List[str]]]],
            Doc("""
                Security requirements.
                Example: [{"BearerAuth": []}]
            """),
        ] = None,
        operation_id: Annotated[
            Optional[str],
            Doc("""
                Unique operation ID.
                Example: 'partialUpdateUser'
            """),
        ] = None,
        deprecated: Annotated[
            bool,
            Doc("""
                Mark as deprecated.
                Example: False
            """),
        ] = False,
        parameters: Annotated[
            List[Parameter],
            Doc("""
                Additional parameters.
                Example: [Parameter(name="fields", in_="query")]
            """),
        ] = [],
        exclude_from_schema: Annotated[
            bool,
            Doc("""
                Hide from OpenAPI docs.
                Example: False
            """),
        ] = False,
        auth: Annotated[
            Optional[Any],
            Doc("Route-level :class:`sillo.auth.useAuth` gate."),
        ] = None,
        request_content_type: Annotated[
            Literal[
                "application/json",
                "application/x-www-form-urlencoded",
                "multipart/form-data",
            ],
            Doc("""
                Request content type.
                Example: 'application/json'
            """),
        ] = "application/json",
        **kwargs: Annotated[
            Any,
            Doc("""
                Additional metadata.
                Example: {"x-partial-update": True}
            """),
        ],
    ) -> Callable[..., Any]:
        """
        Register a PATCH endpoint with the application.

        Examples:
            1. Simple PATCH endpoint:
            @router.patch("/users/{id}")
            async def update_user(request, response):
                user_id = request.path_params['id']
                await User.partial_update(user_id, **request.json)
                return response.json({"status": "updated"})

            2. PATCH with JSON Merge Patch:
            @router.patch(
                "/articles/{id}",
                request_model=ArticlePatch,
                responses={200: ArticleSchema}
            )
            async def patch_article(request, response):
                article = await Article.patch(
                    request.path_params['id'],
                    request.validated_data
                )
                return response.json(article)

            3. PATCH with selective fields:
            @router.patch("/profile")
            async def update_profile(request, response):
                allowed_fields = {'bio', 'avatar_url'}
                data = await request.json
                updates = {k: v for k, v in data.items()
                        if k in allowed_fields}
                await Profile.update(request.user.id, **updates)
                return response.json(updates)
        """
        return self.route(
            path=path,
            methods=["PATCH"],
            handler=handler,
            name=name,
            summary=summary,
            description=description,
            responses=responses,
            request_model=request_model,
            request_content_type=request_content_type,
            middleware=middleware,
            tags=tags,
            security=security,
            operation_id=operation_id,
            deprecated=deprecated,
            parameters=parameters,
            exclude_from_schema=exclude_from_schema,
            auth=auth,
            **kwargs,
        )

    def options(
        self,
        path: Annotated[
            str,
            Doc("""
                URL path pattern for the OPTIONS endpoint.
                Example: '/api/v1/users'
            """),
        ],
        handler: Annotated[
            Optional[HandlerType],
            Doc("""
                Async handler function for OPTIONS requests.
                Example:
                async def user_options(request, response):
                    response.headers['Allow'] = 'GET, POST, OPTIONS'
                    return response
            """),
        ] = None,
        name: Annotated[
            Optional[str],
            Doc("""
                Unique route name for URL generation.
                Example: 'api-v1-user-options'
            """),
        ] = None,
        summary: Annotated[
            Optional[str],
            Doc("""
                Brief endpoint summary.
                Example: 'Get supported operations'
            """),
        ] = None,
        description: Annotated[
            Optional[str],
            Doc("""
                Detailed endpoint description.
                Example: 'Returns supported HTTP methods and CORS headers'
            """),
        ] = None,
        responses: Annotated[
            Optional[ArgsType],
            Doc("""
                Response schemas by status code.
                Example: {
                    200: None,
                    204: None
                }
            """),
        ] = None,
        request_model: Annotated[
            Optional[ArgsType],
            Doc("""
                Model for request validation.
                Example:
                class OptionsQuery(BaseModel):
                    detailed: bool = False
            """),
        ] = None,
        middleware: Annotated[
            List[Any],
            Doc("""
                Route-specific middleware.
                Example: [cors_middleware]
            """),
        ] = [],
        tags: Annotated[
            Optional[List[str]],
            Doc("""
                OpenAPI tags for grouping.
                Example: ["CORS"]
            """),
        ] = None,
        security: Annotated[
            Optional[List[Dict[str, List[str]]]],
            Doc("""
                Security requirements.
                Example: []
            """),
        ] = None,
        operation_id: Annotated[
            Optional[str],
            Doc("""
                Unique operation ID.
                Example: 'userOptions'
            """),
        ] = None,
        deprecated: Annotated[
            bool,
            Doc("""
                Mark as deprecated.
                Example: False
            """),
        ] = False,
        parameters: Annotated[
            List[Parameter],
            Doc("""
                Additional parameters.
                Example: [Parameter(name="Origin", in_="header")]
            """),
        ] = [],
        exclude_from_schema: Annotated[
            bool,
            Doc("""
                Hide from OpenAPI docs.
                Example: True
            """),
        ] = False,
        auth: Annotated[
            Optional[Any],
            Doc("Route-level :class:`sillo.auth.useAuth` gate."),
        ] = None,
        **kwargs: Annotated[
            Any,
            Doc("""
                Additional metadata.
                Example: {"x-cors": True}
            """),
        ],
    ) -> Callable[..., Any]:
        """
        Register an OPTIONS endpoint with the application.

        Examples:
            1. Simple OPTIONS endpoint:
            @router.options("/users")
            async def user_options(request, response):
                response.headers['Allow'] = 'GET, POST, OPTIONS'
                return response

            2. CORS OPTIONS handler:
            @router.options("/{path:path}")
            async def cors_options(request, response):
                response.headers.update({
                    'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE',
                    'Access-Control-Allow-Headers': 'Content-Type',
                    'Access-Control-Max-Age': '86400'
                })
                return response.status(204)

            3. Detailed OPTIONS response:
            @router.options("/resources")
            async def resource_options(request, response):
                return response.json({
                    "methods": ["GET", "POST"],
                    "formats": ["application/json"],
                    "limits": {"max_size": "10MB"}
                })
        """
        return self.route(
            path=path,
            methods=["OPTIONS"],
            handler=handler,
            name=name,
            summary=summary,
            description=description,
            responses=responses,
            request_model=request_model,
            middleware=middleware,
            tags=tags,
            security=security,
            operation_id=operation_id,
            deprecated=deprecated,
            parameters=parameters,
            exclude_from_schema=exclude_from_schema,
            request_content_type="application/json",
            **kwargs,
        )

    def head(
        self,
        path: Annotated[
            str,
            Doc("""
                URL path pattern for the HEAD endpoint.
                Example: '/api/v1/resources/{id}'
            """),
        ],
        handler: Annotated[
            Optional[HandlerType],
            Doc("""
                Async handler function for HEAD requests.
                Example:
                async def check_resource(request, response):
                    exists = await Resource.exists(request.path_params['id'])
                    return response.status(200 if exists else 404)
            """),
        ] = None,
        name: Annotated[
            Optional[str],
            Doc("""
                Unique route name for URL generation.
                Example: 'api-v1-check-resource'
            """),
        ] = None,
        summary: Annotated[
            Optional[str],
            Doc("""
                Brief endpoint summary.
                Example: 'Check resource existence'
            """),
        ] = None,
        description: Annotated[
            Optional[str],
            Doc("""
                Detailed endpoint description.
                Example: 'Returns headers only to check if resource exists'
            """),
        ] = None,
        responses: Annotated[
            Optional[ArgsType],
            Doc("""
                Response schemas by status code.
                Example: {
                    200: None,
                    404: None
                }
            """),
        ] = None,
        request_model: Annotated[
            Optional[ArgsType],
            Doc("""
                Model for request validation.
                Example:
                class ResourceCheck(BaseModel):
                    check_children: bool = False
            """),
        ] = None,
        middleware: Annotated[
            List[Any],
            Doc("""
                Route-specific middleware.
                Example: [cache_control('public')]
            """),
        ] = [],
        tags: Annotated[
            Optional[List[str]],
            Doc("""
                OpenAPI tags for grouping.
                Example: ["Resource Management"]
            """),
        ] = None,
        security: Annotated[
            Optional[List[Dict[str, List[str]]]],
            Doc("""
                Security requirements.
                Example: [{"ApiKeyAuth": []}]
            """),
        ] = None,
        operation_id: Annotated[
            Optional[str],
            Doc("""
                Unique operation ID.
                Example: 'checkResource'
            """),
        ] = None,
        deprecated: Annotated[
            bool,
            Doc("""
                Mark as deprecated.
                Example: False
            """),
        ] = False,
        parameters: Annotated[
            List[Parameter],
            Doc("""
                Additional parameters.
                Example: [Parameter(name="X-Check-Type", in_="header")]
            """),
        ] = [],
        exclude_from_schema: Annotated[
            bool,
            Doc("""
                Hide from OpenAPI docs.
                Example: False
            """),
        ] = False,
        auth: Annotated[
            Optional[Any],
            Doc("Route-level :class:`sillo.auth.useAuth` gate."),
        ] = None,
        **kwargs: Annotated[
            Any,
            Doc("""
                Additional metadata.
                Example: {"x-head-only": True}
            """),
        ],
    ) -> Callable[..., Any]:
        """
        Register a HEAD endpoint with the application.

        Examples:
            1. Simple HEAD endpoint:
            @router.head("/resources/{id}")
            async def check_resource(request, response):
                exists = await Resource.exists(request.path_params['id'])
                return response.status(200 if exists else 404)

            2. HEAD with cache headers:
            @router.head("/static/{path:path}")
            async def check_static(request, response):
                path = request.path_params['path']
                if not static_file_exists(path):
                    return response.status(404)
                response.headers['Last-Modified'] = get_last_modified(path)
                return response.status(200)

            3. HEAD with metadata:
            @router.head("/documents/{id}")
            async def document_metadata(request, response):
                doc = await Document.metadata(request.path_params['id'])
                if not doc:
                    return response.status(404)
                response.headers['X-Document-Size'] = str(doc.size)
                return response.status(200)
        """
        return self.route(
            path=path,
            methods=["HEAD"],
            handler=handler,
            name=name,
            summary=summary,
            description=description,
            responses=responses,
            request_model=request_model,
            request_content_type="application/json",
            middleware=middleware,
            tags=tags,
            security=security,
            operation_id=operation_id,
            deprecated=deprecated,
            parameters=parameters,
            exclude_from_schema=exclude_from_schema,
            auth=auth,
            **kwargs,
        )

    def add_route(
        self,
        route: Annotated[
            Optional[BaseRoute],
            Doc("An instance of the Route class representing an HTTP route."),
        ] = None,
        path: Annotated[
            Optional[str],
            Doc("""
                URL path pattern for the HEAD endpoint.
                Example: '/api/v1/resources/{id}'
            """),
        ] = None,
        methods: Annotated[
            List[str],
            Doc("""
                List of HTTP methods this route should handle.
                Common methods: ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD']
                Defaults to all standard methods if not specified.
            """),
        ] = allowed_methods_default,
        handler: Annotated[
            Optional[HandlerType],
            Doc("""
                Async handler function for HEAD requests.
                Example:
                async def check_resource(request, response):
                    exists = await Resource.exists(request.path_params['id'])
                    return response.status(200 if exists else 404)
            """),
        ] = None,
        name: Annotated[
            Optional[str],
            Doc("""
                Unique route name for URL generation.
                Example: 'api-v1-check-resource'
            """),
        ] = None,
        summary: Annotated[
            Optional[str],
            Doc("""
                Brief endpoint summary.
                Example: 'Check resource existence'
            """),
        ] = None,
        description: Annotated[
            Optional[str],
            Doc("""
                Detailed endpoint description.
                Example: 'Returns headers only to check if resource exists'
            """),
        ] = None,
        responses: Annotated[
            Optional[ArgsType],
            Doc("""
                Response schemas by status code.
                Example: {
                    200: None,
                    404: None
                }
            """),
        ] = None,
        request_model: Annotated[
            Optional[ArgsType],
            Doc("""
                Model for request validation.
                Example:
                class ResourceCheck(BaseModel):
                    check_children: bool = False
            """),
        ] = None,
        request_content_type: Annotated[
            Literal[
                "application/json",
                "application/x-www-form-urlencoded",
                "multipart/form-data",
            ],
            Doc("""
                Request content type.
                Example: 'application/json'
            """),
        ] = "application/json",
        middleware: Annotated[
            List[Any],
            Doc("""
                Route-specific middleware.
                Example: [cache_control('public')]
            """),
        ] = [],
        tags: Annotated[
            Optional[List[str]],
            Doc("""
                OpenAPI tags for grouping.
                Example: ["Resource Management"]
            """),
        ] = None,
        security: Annotated[
            Optional[List[Dict[str, List[str]]]],
            Doc("""
                Security requirements.
                Example: [{"ApiKeyAuth": []}]
            """),
        ] = None,
        operation_id: Annotated[
            Optional[str],
            Doc("""
                Unique operation ID.
                Example: 'checkResource'
            """),
        ] = None,
        deprecated: Annotated[
            bool,
            Doc("""
                Mark as deprecated.
                Example: False
            """),
        ] = False,
        parameters: Annotated[
            List[Parameter],
            Doc("""
                Additional parameters.
                Example: [Parameter(name="X-Check-Type", in_="header")]
            """),
        ] = [],
        exclude_from_schema: Annotated[
            bool,
            Doc("""
                Hide from OpenAPI docs.
                Example: False
            """),
        ] = False,
        auth: Annotated[
            Optional[Any],
            Doc("Route-level :class:`sillo.auth.useAuth` gate."),
        ] = None,
        **kwargs: Annotated[
            Any,
            Doc("""
                Additional metadata.
                Example: {"x-head-only": True}
            """),
        ],
    ) -> None:
        """
        Adds an HTTP route to the application.

        This method registers an HTTP route, allowing the application to handle requests for a specific URL path.

        Args:
            route (Route): The HTTP route configuration.

        Returns:
            None

        Example:
            ```python
            route = Route("/home", home_handler, methods=["GET", "POST"])
            app.add_route(route)
            ```
        """
        if not route:
            if (not path) or (not handler):
                raise ValueError(
                    "path and handler are required if route is not provided"
                )
            route = Route(
                path=path,
                handler=handler,
                methods=methods,
                name=name,
                summary=summary,
                description=description,
                responses=responses,
                request_model=request_model,
                request_content_type=request_content_type,
                middleware=middleware,
                tags=tags,
                security=security,
                operation_id=operation_id,
                deprecated=deprecated,
                parameters=parameters,
                exclude_from_schema=exclude_from_schema,
                **kwargs,
            )
        self.router.add_route(route)

    def add_exception_handler(
        self,
        exc_class_or_status_code: Union[Type[Exception], int],
        handler: Optional[ExceptionHandlerType] = None,
    ) -> Any:
        """
        Register a custom exception handler for specific exception types or status codes.

        Maps an exception class or HTTP status code to a handler function that
        produces a response when the specified error occurs during request
        processing. Can be used as a direct method call or as a decorator
        when the handler argument is omitted.

        Args:
            exc_class_or_status_code: Either an exception class (subclass of
                ``Exception``) or an integer HTTP status code to handle.
                For example, ``ValueError`` or ``404``.
            handler: An optional callable that accepts ``(request, response,
                exception)`` and returns a ``Response``. When ``None``, a
                decorator is returned instead for deferred registration.

        Returns:
            Any: When ``handler`` is ``None``, returns a decorator that
                accepts the handler function. When ``handler`` is provided,
                returns ``None`` after registering the handler directly.

        Raises:
            None
        """
        if handler is None:
            # If handler is not given yet, return a decorator
            def decorator(func: ExceptionHandlerType) -> Any:
                self.exceptions_handler.add_exception_handler(
                    exc_class_or_status_code, func
                )
                return func

            return decorator
        else:
            # Normal direct handler registration
            self.exceptions_handler.add_exception_handler(
                exc_class_or_status_code, handler
            )

    def url_for(self, _name: str, **path_params: Any) -> URLPath:
        """
        Generate a URL path for a named route with the given path parameters.

        Looks up a route by its registered name and interpolates the
        provided path parameters into the route's URL pattern to produce
        a concrete ``URLPath`` instance. This is useful for reverse URL
        generation in redirects, hypermedia responses, and templates.

        Args:
            _name: The unique name assigned to the route during registration.
                This corresponds to the ``name`` argument passed to route
                decorators or the ``add_route`` method.
            **path_params: Keyword arguments representing the path parameters
                to substitute into the route's URL pattern. For example,
                ``user_id=42`` for a route pattern ``/users/{user_id}``.

        Returns:
            URLPath: A URL path object containing the fully resolved URL
                string with all path parameters interpolated.

        Raises:
            KeyError: If the named route is not found in the router or if
                required path parameters are missing from the arguments.
        """
        return self.router.url_for(_name, **path_params)

    def wrap_asgi(
        self,
        middleware_cls: Annotated[
            Callable[[ASGIApp], Any],
            Doc(
                "An ASGI middleware class or callable that takes an app as its first argument and returns an ASGI app"
            ),
        ],
        **kwargs: Any,
    ) -> None:
        """
        Wraps the entire application with an ASGI middleware.

        This method allows adding middleware at the ASGI level, which intercepts all requests
        (HTTP, WebSocket, and Lifespan) before they reach the application.

        Args:
            middleware_cls: An ASGI middleware class or callable that follows the ASGI interface
            *args: Additional positional arguments to pass to the middleware
            **kwargs: Additional keyword arguments to pass to the middleware

        Returns:
            silloApp: The application instance for method chaining


        """
        self.app = middleware_cls(self.app, **kwargs)
        return

    def get_all_routes(self) -> List[Route]:
        """
        Returns all routes registered in the application.

        This method retrieves a list of all HTTP and WebSocket routes defined in the application.

        Returns:
            List[Route]: A list of all registered routes.

        Example:
            ```python
            routes = app.get_all_routes()
            for route in routes:
                print(route.path, route.methods)
            ```
        """
        return self.router.get_all_routes()

    def ws_route(
        self,
        path: Annotated[
            str,
            Doc("""
                URL path pattern for the WebSocket route.
                Example: '/ws/chat/{room_id}'
            """),
        ],
        handler: Annotated[
            Optional[WsHandlerType],
            Doc("""
                Async handler function for WebSocket connections.
                Example:
                async def chat_handler(websocket, path):
                    await websocket.send("Welcome to the chat!")
            """),
        ] = None,
    ):
        """
        Register a WebSocket route with the application.

        Args:
            path (str): URL path pattern for the WebSocket route.
            handler (Callable): Async handler function for WebSocket connections.
                Example: async def chat_handler(websocket, path): pass

        Returns:
            Callable: A decorator to register the WebSocket route.
        """
        return self.router.ws_route(
            path=path,
            handler=handler,
        )

    def register(
        self,
        app: ASGIApp,
        prefix: str = "",
    ) -> None:
        """
        Register an external ASGI application under an optional URL prefix.

        Delegates to the root router's ``register`` method to mount a
        sub-application or external ASGI app at a given prefix path. This
        is useful for integrating third-party ASGI components or mounting
        independent sub-applications within the main sillo application.

        Args:
            app: An ASGI application callable conforming to the standard
                ``(scope, receive, send)`` interface that will handle
                requests matching the specified prefix.
            prefix: An optional URL path prefix under which the sub-application
                is mounted. Defaults to an empty string, meaning the app
                handles requests at the root level.

        Returns:
            None

        Raises:
            None
        """
        self.router.register(app, prefix)

    def __str__(self) -> str:
        """
        Return a human-readable string representation of the application.

        Produces a descriptive string containing the application's title,
        useful for logging, debugging, and development server output.

        Args:
            None

        Returns:
            str: A string in the format ``<silloApp: {title}>`` where
                ``{title}`` is the application's configured title.

        Raises:
            None
        """
        return f"<silloApp: {self.title}>"

    def run(
        self,
        host: str = "127.0.0.1",
        port: int = 8000,
        reload: bool = False,
    ):
        """
        Run the application using uvicorn.

        Note: For production, consider using the sillo CLI or ASGI servers directly:
        - sillo run --host 0.0.0.0 --port 8000
        - uvicorn app:app --host 0.0.0.0 --port 8000
        - granian app:app --host 0.0.0.0 --port 8000

        Args:
            host (str): Host address to bind.
            port (int): Port number to bind.
            reload (bool): Enable auto-reload.
            **kwargs: Additional keyword arguments for uvicorn.
        """
        warnings.warn(
            "app.run() is inefficient and only for testing. For development and production, use:\n"
            "- sillo run --host 0.0.0.0 --port 8000\n"
            "- uvicorn app:app --host 0.0.0.0 --port 8000\n"
            "- granian app:app --host 0.0.0.0 --port 8000",
            UserWarning,
            stacklevel=2,
        )

        if uvicorn is None:
            raise RuntimeError(
                "uvicorn not found. Install it with: pip install uvicorn\n"
                "Or use the sillo CLI: sillo run"
            )
        logger.info(f"Starting server with uvicorn: {host}:{port}")
        uvicorn.run(self, host=host, port=port, reload=reload)
