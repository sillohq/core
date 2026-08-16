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
#: An exception handler. Must be ``async``.
#:
#: The dispatcher in ``sillo.exception_handler`` does ``await handler(...)``
#: unconditionally, and every built-in handler is a coroutine function, so
#: the awaitable is part of the contract rather than an accepted alternative.
#: Declaring the return as a bare ``Response`` described neither the built-ins
#: nor anything an application can actually register: every ``async`` handler
#: -- the only kind that works -- was reported as the wrong type, and the
#: dispatcher needed a ``ty: ignore[invalid-await]`` to await its own alias.
ExceptionHandlerType = Callable[
    [Request, Response, Exception], typing.Awaitable[Response]
]

#: An exception handler for one specific exception type.
#:
#: The same shape as :data:`ExceptionHandlerType`, but parameterised by the
#: exception it handles, so that
#:
#:     async def on_not_found(request, response, exc: NotFound) -> Response
#:
#: registers against ``NotFound`` without being reported as incompatible.
#: Callables are contravariant in their parameters, so a handler narrowed to
#: a subclass is *not* a valid ``Callable[..., Exception, ...]`` -- which is
#: correct in general and useless here, because the registration call is
#: exactly what pairs the handler with its own exception class.
ExcT = typing.TypeVar("ExcT", bound=Exception)
ExceptionHandlerFor = Callable[[Request, Response, ExcT], typing.Awaitable[Response]]

ASGIApp = typing.Callable[[Scope, Receive, Send], typing.Awaitable[Any]]
