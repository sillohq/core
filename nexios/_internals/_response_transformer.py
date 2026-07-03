from __future__ import annotations

import typing

from nexios.context import set_context, reset_context, Context
from nexios.encoding import jsonable_encoder
from nexios.http import Request, Response
from nexios.http.response import BaseResponse, NexiosResponse, JSONResponse
from nexios.types import ASGIApp, Receive, Scope, Send


def serialize_response(func_result: typing.Any) -> BaseResponse:
    if isinstance(func_result, (BaseResponse, NexiosResponse)):
        return func_result
    encoded = jsonable_encoder(func_result)
    if isinstance(encoded, str):
        return BaseResponse(body=encoded, content_type="text/plain")
    return JSONResponse(content=encoded)


def request_response(
    func: typing.Callable[[Request, Response], typing.Awaitable[Response]],
) -> ASGIApp:

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        request = Request(scope, receive, send)
        response_manager = Response(request)

        ctx = Context(
            request=request,
            app=request.app,
            base_app=getattr(request, "base_app", None),
        )
        token = set_context(ctx)
        try:
            func_result = await func(request, response_manager, **request.path_params)
        finally:
            reset_context(token)

        response = serialize_response(func_result)
        return await response(scope, receive, send)

    return app
