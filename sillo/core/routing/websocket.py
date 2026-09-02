import inspect
from collections.abc import Callable
from typing import TYPE_CHECKING, Annotated, Any, cast

from typing_extensions import Doc

from sillo.core.dependencies.base import Dependant, get_dependant, solve_dependencies
from sillo.objects.routing import URLPath
from sillo.route_builder import RouteBuilder
from sillo.types import (
    Receive,
    Scope,
    Send,
    WsHandlerType,
)
from sillo.websockets import WebSocketContext
from sillo.websockets.errors import WebSocketErrorMiddleware

from ._utils import MatchStatus, get_route_path
from .base import BaseRoute

if TYPE_CHECKING:
    from sillo.core.http import HttpContext


class WebsocketRoute(BaseRoute):
    """
    WebSocket route configuration for handling real-time bidirectional communication.

    WebsocketRoute defines a WebSocket endpoint that can handle persistent connections
    between clients and the server. Unlike HTTP routes, WebSocket routes maintain
    an open connection that allows both the client and server to send messages
    at any time.

    Features:
    - Path parameter extraction (same as HTTP routes)
    - Automatic connection lifecycle management
    - Error handling and connection cleanup
    - Support for binary and text messages

    Examples:
        1. Basic WebSocket echo server:
        ```python
        async def echo_handler(websocket: WebSocketContext):
            await websocket.accept()
            try:
                while True:
                    message = await websocket.receive_text()
                    await websocket.send_text(f"Echo: {message}")
            except WebSocketDisconnect:
                pass

        ws_route = WebsocketRoute("/ws/echo", echo_handler)
        app.add_ws_route(ws_route)
        ```

        2. Chat room with path parameters:
        ```python
        async def chat_handler(websocket: WebSocketContext):
            room_id = websocket.path_params['room_id']
            await websocket.accept()

            # Add user to chat room
            await chat_manager.add_user(room_id, websocket)

            try:
                while True:
                    message = await websocket.receive_text()
                    # Broadcast to all users in room
                    await chat_manager.broadcast(room_id, message)
            except WebSocketDisconnect:
                await chat_manager.remove_user(room_id, websocket)

        ws_route = WebsocketRoute("/ws/chat/{room_id}", chat_handler)
        app.add_ws_route(ws_route)
        ```

        3. Binary data handling:
        ```python
        async def file_upload_handler(websocket: WebSocketContext):
            await websocket.accept()

            try:
                while True:
                    # Receive binary data
                    data = await websocket.receive_bytes()

                    # Process file chunk
                    file_id = await process_file_chunk(data)

                    # Send confirmation
                    await websocket.send_json({
                        "status": "chunk_received",
                        "file_id": file_id
                    })
            except WebSocketDisconnect:
                pass

        ws_route = WebsocketRoute("/ws/upload", file_upload_handler)
        app.add_ws_route(ws_route)
        ```
    """

    def __init__(
        self,
        path: Annotated[
            str,
            Doc("""
                URL path pattern for the WebSocket endpoint.
                
                Supports the same path parameter syntax as HTTP routes:
                - Static paths: "/ws/chat"
                - Path parameters: "/ws/room/{room_id}"
                - Regex parameters: "/ws/files/{path:.*}"
                
                Examples:
                - "/ws" - Simple WebSocket endpoint
                - "/ws/chat/{room_id}" - Chat room with room ID parameter
                - "/ws/user/{user_id}/notifications" - User-specific notifications
                """),
        ],
        handler: Annotated[
            WsHandlerType,
            Doc("""
                Async function to handle WebSocket connections.
                
                The handler function receives a WebSocketContext object and should:
                1. Accept the connection with await websocket.accept()
                2. Handle incoming messages in a loop
                3. Send responses as needed
                4. Handle disconnections gracefully
                
                Function signature: async def handler(websocket: WebSocketContext) -> None
                
                The WebSocketContext object provides methods for:
                - websocket.accept(): Accept the connection
                - websocket.receive_text(): Receive text messages
                - websocket.receive_bytes(): Receive binary messages
                - websocket.receive_json(): Receive JSON messages
                - websocket.send_text(): Send text messages
                - websocket.send_bytes(): Send binary messages
                - websocket.send_json(): Send JSON messages
                - websocket.close(): Close the connection
                """),
        ],
    ):
        """Initialize a WebSocket route with path pattern and handler.

        Creates a new WebSocket route that matches incoming WebSocketContext
        upgrade requests against the provided path pattern. The handler
        function is invoked with a WebSocketContext object when a client connects
        to a matching path.

        The path pattern is compiled into a regex using RouteBuilder for
        efficient matching and parameter extraction. Both synchronous and
        asynchronous validation checks are performed on the handler.

        The handler's signature is analysed the same way an HTTP route's is,
        so it may declare ``Depend(...)`` parameters. ``Depend(get_context=True)``
        injects the live ``WebSocketContext``.

        Args:
            path: URL path pattern for the WebSocket endpoint. Supports
                dynamic parameters using curly brace syntax.
            handler: Async function to handle WebSocket connections. Must
                be a coroutine function whose first parameter is the
                ``WebSocketContext``; further parameters may be path
                parameters or ``Depend(...)`` markers.

        Raises:
            AssertionError: If handler is not callable or is not an async
                coroutine function.
        """
        assert callable(handler), "Route handler must be callable"
        assert inspect.iscoroutinefunction(handler), "Route handler must be async"
        self.raw_path = path
        self.handler: WsHandlerType = handler
        self.dependant: Dependant = get_dependant(handler)
        self.route_info = RouteBuilder.create_pattern(path)
        self.pattern = self.route_info.pattern
        self.param_names = self.route_info.param_names
        self.route_type = self.route_info.route_type
        self.router_middleware = None

    def match(self, scope: Scope) -> tuple[Any, Any]:
        """Match a WebSocket request path against this route's URL pattern.

        Extracts the path from the ASGI scope and attempts to match it
        against the compiled regex pattern. When a match is found, path
        parameters are extracted and converted to their appropriate types
        using the route info convertors.

        Unlike HTTP routes, WebSocket routes do not check the request
        method since WebSocket connections use a special upgrade mechanism
        rather than standard HTTP methods.

        Args:
            scope: ASGI scope containing the request path and connection
                metadata used for route matching.

        Returns:
            A tuple of (MatchStatus, dict) containing the match status
            and any captured path parameters. Returns MatchStatus.FULL
            with parameters on success, or MatchStatus.NONE with an
            empty dict on failure.
        """
        # The path alone is not enough. An HTTP request to a path that also
        # carries a WebSocket route would otherwise match it, and be handed a
        # scope `WebSocketContext` refuses -- so a PUT to an endpoint that
        # serves both became a 500 instead of the 405 the HTTP route was
        # already prepared to give.
        if scope.get("type") != "websocket":
            return MatchStatus.NONE, {}

        path = get_route_path(scope)
        match = self.pattern.match(path)
        if match:
            matched_params = match.groupdict()
            for key, value in matched_params.items():
                matched_params[key] = self.route_info.convertor[key].convert(value)
            return MatchStatus.FULL, matched_params
        return MatchStatus.NONE, {}

    async def handle(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Handle an incoming WebSocket connection by invoking the route handler.

        Creates a WebSocket session object from the ASGI connection triple
        and passes it to the route's handler function. The handler is wrapped
        in a WebSocketErrorMiddleware to ensure proper error handling and
        connection cleanup when exceptions occur during the WebSocket session.

        This method sets up the full lifecycle of a WebSocket connection
        including creation of the session object, handler invocation, and
        error handling with automatic cleanup.

        Args:
            scope: ASGI scope containing WebSocket connection information
                including path, headers, and query parameters.
            receive: ASGI receive callable for reading incoming WebSocketContext
                messages from the client.
            send: ASGI send callable for transmitting WebSocket messages
                back to the client.
        """

        # Create the base handler
        async def handler_app(scope: Scope, receive: Receive, send: Send) -> None:
            """Serve as the base ASGI application for this WebSocket route.

            Creates a ``WebSocketContext`` session object from the raw ASGI
            connection triple and passes it to the route's handler function.
            This inner function is wrapped by ``WebSocketErrorMiddleware``
            to ensure proper error handling and connection cleanup when
            exceptions occur during the WebSocket session lifecycle.

            Args:
                scope: ASGI scope dictionary containing WebSocket connection
                    metadata including path, headers, and query parameters.
                receive: ASGI receive callable for reading incoming WebSocketContext
                    messages from the client.
                send: ASGI send callable for transmitting WebSocket messages
                    back to the client.

            Returns:
                None. All communication happens through the WebSocket session
                object passed to the handler.
            """
            ctx = WebSocketContext(scope, receive=receive, send=send)
            cleanups: list[Callable[[], Any]] = []
            try:
                # The handler's Depend(...) parameters are solved by the same
                # engine an HTTP route uses. It is typed for HttpContext, but
                # only reads members both contexts share via BaseContext
                # (headers, query params, cookies, path params) plus the
                # HTTP-only form body, which a socket handler never declares.
                # A generator dependency registers its teardown on `cleanups`.
                injected = await solve_dependencies(
                    self.dependant, cast("HttpContext", ctx), {}, cleanups
                )
                # Path parameters reach the handler as keyword arguments, the
                # same way they do on an HTTP route -- from `ctx.path_params`,
                # which the router writes into the scope under "route_params".
                # A parameter also produced by DI (a validated marker) wins, so
                # the raw captured value is dropped to avoid a duplicate kwarg.
                path_kwargs = {
                    k: v for k, v in ctx.path_params.items() if k not in injected
                }
                await self.handler(ctx, **path_kwargs, **injected)
            finally:
                for cleanup in reversed(cleanups):
                    result = cleanup()
                    if inspect.isawaitable(result):
                        await result

        app = WebSocketErrorMiddleware(handler_app)

        await app(scope, receive, send)

    def url_path_for(self, name: str, **path_params: dict[str, Any]) -> URLPath:
        """Generate a URL path for this WebSocket route by name.

        Performs reverse URL resolution for WebSocket routes by substituting
        the provided path parameters into the route's raw path pattern. The
        method validates that the requested name matches this route's name
        before performing the substitution.

        This enables applications to generate WebSocket connection URLs
        dynamically without hardcoding URL patterns throughout the codebase.

        Args:
            name: The name of the route to generate a URL for. Must match
                this route's name attribute for the lookup to succeed.
            **path_params: Path parameters to substitute into the URL
                pattern. Keys correspond to parameter names defined in
                the route path using curly brace syntax.

        Returns:
            A URLPath object containing the resolved path string for
            the WebSocket endpoint.

        Raises:
            ValueError: If the provided name does not match this route's
                name attribute.
        """
        if name != self.name:
            raise ValueError(
                f"Route name '{name}' does not match this route's name '{self.name}'"
            )

        # Build the path with parameters
        path = self.raw_path
        for param_name, param_value in path_params.items():
            if f"{{{param_name}}}" in path:
                path = path.replace(f"{{{param_name}}}", str(param_value))

        return URLPath(path=path)

    def __repr__(self) -> str:
        """Return a detailed string representation of this WebSocket route.

        Produces a human-readable string that includes the route class
        identifier and the raw path pattern. This is useful for debugging
        and logging purposes, providing a quick overview of the WebSocketContext
        route's configuration.

        Returns:
            A formatted string in the form ``<WSRoute /path>`` showing
            the path pattern of this WebSocket route.
        """
        return f"<WSRoute {self.raw_path}>"


WebsocketRoutes = WebsocketRoute  # for backwards compatibility
