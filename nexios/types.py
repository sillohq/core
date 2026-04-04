from __future__ import annotations

import typing
from typing import Any, Callable

from nexios.http.response import StreamingResponse

from .http.request import Request
from .http.response import NexiosResponse as Response
from .websockets import WebSocket

AppType = typing.TypeVar("AppType")

Scope = typing.MutableMapping[str, typing.Any]
Message = typing.MutableMapping[str, typing.Any]

Receive = typing.Callable[[], typing.Awaitable[Message]]
Send = typing.Callable[[Message], typing.Awaitable[None]]
RequestResponseEndpoint = typing.Callable[
    [], typing.Awaitable[typing.Union[Response, StreamingResponse]]
]

MiddlewareType = typing.Callable[
    [Request, Response, RequestResponseEndpoint],
    typing.Awaitable[typing.Union[Response, StreamingResponse]],
]

WsHandlerType = typing.Callable[[WebSocket], typing.Awaitable[None]]
HandlerType = Callable[..., Any]
ExceptionHandlerType = Callable[[Request, Response, Exception], typing.Any]

ASGIApp = typing.Callable[[Scope, Receive, Send], typing.Awaitable[Any]]
