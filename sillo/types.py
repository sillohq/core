from __future__ import annotations

import typing
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from sillo.core.http.request import Request
from sillo.core.http.response import Responder as Response
from sillo.core.http.response import StreamingResponse

from .websockets import WebSocket

# Type alias for route model arguments — accepts any of:
#   - a single Pydantic model class
#   - a dict mapping int keys (e.g. status codes) to Pydantic model classes
#   - a nested dict mapping int keys to another dict of int -> dict

Schema = type[BaseModel] | type[list[BaseModel]]

ArgsType = Any
Scope = typing.MutableMapping[str, typing.Any]
Message = typing.MutableMapping[str, typing.Any]

Receive = typing.Callable[[], typing.Awaitable[Message]]
Send = typing.Callable[[Message], typing.Awaitable[None]]
RequestResponseEndpoint = typing.Callable[
    [], typing.Awaitable[Response | StreamingResponse]
]

MiddlewareType = typing.Callable[
    [Request, Response, RequestResponseEndpoint],
    typing.Awaitable[Response | StreamingResponse],
]

WsHandlerType = typing.Callable[[WebSocket], typing.Awaitable[None]]
HandlerType = Callable[..., Any]
ExceptionHandlerType = Callable[[Request, Response, Exception], Response]

ASGIApp = typing.Callable[[Scope, Receive, Send], typing.Awaitable[Any]]
