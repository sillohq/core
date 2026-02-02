import asyncio
import typing
from typing import Any

from typing_extensions import Annotated, Doc

from nexios._internals._route_builder import RouteBuilder
from nexios.types import (
    Receive,
    Scope,
    Send,
    WsHandlerType,
)
from nexios.websockets import WebSocket
from nexios.websockets.errors import WebSocketErrorMiddleware

from ._utils import MatchStatus, get_route_path


class WebsocketRoute:
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
        async def echo_handler(websocket: WebSocket):
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
        async def chat_handler(websocket: WebSocket):
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
        async def file_upload_handler(websocket: WebSocket):
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
                
                The handler function receives a WebSocket object and should:
                1. Accept the connection with await websocket.accept()
                2. Handle incoming messages in a loop
                3. Send responses as needed
                4. Handle disconnections gracefully
                
                Function signature: async def handler(websocket: WebSocket) -> None
                
                The WebSocket object provides methods for:
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
        assert callable(handler), "Route handler must be callable"
        assert asyncio.iscoroutinefunction(handler), "Route handler must be async"
        self.raw_path = path
        self.handler: WsHandlerType = handler
        self.route_info = RouteBuilder.create_pattern(path)
        self.pattern = self.route_info.pattern
        self.param_names = self.route_info.param_names
        self.route_type = self.route_info.route_type
        self.router_middleware = None

    def match(self, scope: Scope) -> typing.Tuple[Any, Any]:
        """
        Match a path against this route's pattern and return captured parameters.

        Args:
            path: The URL path to match.

        Returns:
            Optional[Dict[str, Any]]: A dictionary of captured parameters if the path matches,
            otherwise None.
        """
        path = get_route_path(scope)
        match = self.pattern.match(path)
        if match:
            matched_params = match.groupdict()
            for key, value in matched_params.items():
                matched_params[key] = self.route_info.convertor[  # type: ignore
                    key
                ].convert(value)
            return MatchStatus.FULL, matched_params
        return MatchStatus.NONE, {}

    async def handle(self, scope: Scope, receive: Receive, send: Send) -> None:
        """
        Handles the WebSocket connection by calling the route's handler.
        """

        # Create the base handler
        async def handler_app(scope: Scope, receive: Receive, send: Send) -> None:
            websocket_session = WebSocket(scope, receive=receive, send=send)
            await self.handler(websocket_session)

        app = WebSocketErrorMiddleware(handler_app)

        await app(scope, receive, send)

    def __repr__(self) -> str:
        return f"<WSRoute {self.raw_path}>"


WebsocketRoutes = WebsocketRoute  # for backwards compatibility
