import asyncio
import typing
import warnings
from typing import Any, Callable, Dict, List, Optional

from typing_extensions import Annotated, Doc

from nexios._internals._route_builder import RouteBuilder
from nexios.types import (
    ASGIApp,
    Receive,
    Scope,
    Send,
    WsHandlerType,
    WsMiddlewareType,
)
from nexios.websockets import WebSocket
from nexios.websockets.errors import WebSocketErrorMiddleware

from ._utils import get_route_path
from .base import BaseRouter


class WebsocketRoute:
    def __init__(
        self,
        path: str,
        handler: WsHandlerType,
        middleware: typing.List[WsMiddlewareType] = [],
    ):
        assert callable(handler), "Route handler must be callable"
        assert asyncio.iscoroutinefunction(handler), "Route handler must be async"
        self.raw_path = path
        self.handler: WsHandlerType = handler
        self.middleware = middleware
        self.route_info = RouteBuilder.create_pattern(path)
        self.pattern = self.route_info.pattern
        self.param_names = self.route_info.param_names
        self.route_type = self.route_info.route_type
        self.router_middleware = None

    def match(self, path: str) -> typing.Tuple[Any, Any]:
        """
        Match a path against this route's pattern and return captured parameters.

        Args:
            path: The URL path to match.

        Returns:
            Optional[Dict[str, Any]]: A dictionary of captured parameters if the path matches,
            otherwise None.
        """
        match = self.pattern.match(path)
        if match:
            matched_params = match.groupdict()
            for key, value in matched_params.items():
                matched_params[key] = self.route_info.convertor[  # type:ignore
                    key
                ].convert(value)
            return match, matched_params
        return None, None

    async def handle(self, scope: Scope, receive: Receive, send: Send) -> None:
        """
        Handles the WebSocket connection by calling the route's handler.

        Args:
            websocket: The WebSocket connection.
            params: The extracted route parameters.
        """
        websocket_session = WebSocket(scope, receive=receive, send=send)
        await self.handler(websocket_session)

    def __repr__(self) -> str:
        return f"<WSRoute {self.raw_path}>"


class WebsocketRouter(BaseRouter):
    def __init__(
        self,
        prefix: Optional[str] = None,
        middleware: Optional[List[Any]] = [],
        routes: Optional[List[WebsocketRoute]] = [],
    ):
        self.prefix = prefix
        self.routes: List[WebsocketRoute] = routes or []
        self.middleware: List[Callable[[ASGIApp], ASGIApp]] = []
        self.sub_routers: Dict[str, ASGIApp] = {}
        if self.prefix and not self.prefix.startswith("/"):
            warnings.warn("WSRouter prefix should start with '/'")
            self.prefix = f"/{self.prefix}"

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
        middleware: List[WsMiddlewareType] = [],
    ) -> None:
        """
        Adds a WebSocket route to the application.

        This method registers a WebSocket route, allowing the application to handle WebSocket connections.

        Args:
            route: Either a pre-constructed WebsocketRoute instance or None
            path: The URL path for the WebSocket route (required if route is None)
            handler: The WebSocket handler function (required if route is None)
            middleware: List of middleware for this route

        Returns:
            None

        Example:
            ```python
            # Using with a pre-constructed route
            route = WebsocketRoute("/ws/chat", chat_handler)
            app.add_ws_route(route)

            # Or directly with path and handler
            app.add_ws_route(path="/ws/chat", handler=chat_handler)
            ```
        """
        if route is not None:
            self.routes.append(route)
        elif path is not None and handler is not None:
            self.routes.append(WebsocketRoute(path, handler, middleware=middleware))
        else:
            raise ValueError("Either route or both path and handler must be provided")

    def add_ws_middleware(self, middleware: type[ASGIApp]) -> None:  # type: ignore[override]
        """Add middleware to the WebSocket router"""
        self.middleware.insert(0, middleware)  # type: ignore

    def ws_route(
        self,
        path: Annotated[
            str, Doc("The WebSocket route path. Must be a valid URL pattern.")
        ],
        handler: Annotated[
            Optional[WsHandlerType],
            Doc("The WebSocket handler function. Must be an async function."),
        ] = None,
        middleware: Annotated[
            List[WsMiddlewareType],
            Doc("List of middleware to be executes before the router handler"),
        ] = [],
    ) -> Any:
        """
        Registers a WebSocket route.

        This decorator is used to define WebSocket routes in the application, allowing handlers
        to manage WebSocket connections. When a WebSocket client connects to the given path,
        the specified handler function will be executed.

        Returns:
            Callable: The original WebSocket handler function.

        Example:
            ```python

            @app.ws_route("/ws/chat")
            async def chat_handler(websocket):
                await websocket.accept()
                while True:
                    message = await websocket.receive_text()
                    await websocket.send_text(f"Echo: {message}")
            ```
        """
        if handler:
            return self.add_ws_route(
                WebsocketRoute(path, handler, middleware=middleware)
            )

        def decorator(handler: WsHandlerType) -> WsHandlerType:
            self.add_ws_route(WebsocketRoute(path, handler, middleware=middleware))
            return handler

        return decorator

    def build_middleware_stack(  # type:ignore
        self, scope: Scope, receive: Receive, send: Send
    ) -> ASGIApp:  # type:ignore
        app = self.app
        for mdw in reversed(self.middleware):
            app = mdw(app)  # type:ignore[assignment]
        return app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "websocket":
            return
        app = self.build_middleware_stack(scope, receive, send)
        app = WebSocketErrorMiddleware(app)
        await app(scope, receive, send)

    async def app(self, scope: Scope, receive: Receive, send: Send) -> None:
        url = get_route_path(scope)
        for mount_path, sub_app in self.sub_routers.items():
            if url.startswith(mount_path):
                scope["path"] = url[len(mount_path) :]
                scope["root_path"] = scope.get("root_path", "") + mount_path

                await sub_app(scope, receive, send)
                return
        for route in self.routes:
            match, params = route.match(url)
            if match:
                scope["route_params"] = params
                await route.handle(scope, receive, send)
                return
        await send({"type": "websocket.close", "code": 404})

    def wrap_asgi(
        self,
        middleware_cls: Annotated[
            Callable[[ASGIApp], Any],
            Doc(
                "An ASGI middleware class or callable that takes an app as its first argument and returns an ASGI app"
            ),
        ],
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
            NexiosApp: The application instance for method chaining


        """
        self.app = middleware_cls(self.app)

    def mount_router(self, app: "WSRouter") -> None:  # type:ignore
        """
        Mount an ASGI application (e.g., another Router) using its prefix.

        Args:
            app: The ASGI application (e.g., another Router) to mount.
        """
        path = app.prefix
        path = path.rstrip("/")

        if path == "":
            self.sub_routers[path] = app
            return
        if not path.startswith("/"):
            path = f"/{path}"

        self.sub_routers[path] = app

    def __repr__(self) -> str:
        return f"<WSRouter prefix='{self.prefix}' routes={len(self.routes)}>"

WebsocketRoutes = WebsocketRoute #for backwards compatibility
WSRouter = WebsocketRouter #for backwards compatibility