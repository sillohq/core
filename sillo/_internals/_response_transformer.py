from __future__ import annotations

import typing

from sillo.context import set_context, reset_context, Context
from sillo.encoding import jsonable_encoder
from sillo.http import Request, Response
from sillo.http.response import BaseResponse, silloResponse, JSONResponse
from sillo.types import ASGIApp, Receive, Scope, Send


def serialize_response(func_result: typing.Any) -> BaseResponse:
    if isinstance(func_result, (BaseResponse, silloResponse)):
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
