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

from ._utils import get_route_path,MatchStatus
from .base import BaseRouter
from .grouping import Group


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

    def match(self, scope:Scope) -> typing.Tuple[Any, Any]:
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
                matched_params[key] = self.route_info.convertor[  # type:ignore
                    key
                ].convert(value)
            return MatchStatus.FULL, matched_params
        return MatchStatus.NONE, {}

    async def handle(self, scope: Scope, receive: Receive, send: Send) -> None:
        """
        Handles the WebSocket connection by calling the route's handler with middleware.
        """
        # Create the base handler
        async def handler_app(scope: Scope, receive: Receive, send: Send) -> None:
            websocket_session = WebSocket(scope, receive=receive, send=send)
            await self.handler(websocket_session)
        
        app = handler_app
        
        for middleware_cls in reversed(self.middleware):
            app = middleware_cls(app)
        
        app = WebSocketErrorMiddleware(app)
        
        await app(scope, receive, send)


    def __repr__(self) -> str:
        return f"<WSRoute {self.raw_path}>"



WebsocketRoutes = WebsocketRoute  # for backwards compatibility
