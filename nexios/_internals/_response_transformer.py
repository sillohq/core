import typing
from enum import Enum

from pydantic import BaseModel

from nexios.context import Context, set_context, reset_context
from nexios.http import Request, Response
from nexios.http.response import BaseResponse
from nexios.types import ASGIApp, Receive, Scope, Send


def _process_response(
    response_manager: Response, func_result: typing.Any
) -> BaseResponse:
    """
    Process the response from the function
    """
    if isinstance(func_result, str):
        response_manager.text(func_result)
    elif isinstance(func_result, (dict, list, int, float)):
        response_manager.json(typing.cast(typing.Any, func_result))

    elif isinstance(func_result, BaseResponse):
        response_manager.make_response(func_result)
    elif isinstance(func_result, BaseModel):
        response_manager.json(func_result.model_dump())
    elif isinstance(func_result, Enum):
        response_manager.json(func_result.value)
    elif isinstance(func_result, bytes):
        response_manager.resp(func_result)

    return response_manager.get_response()


def request_response(
    func: typing.Callable[[Request, Response], typing.Awaitable[Response]],
) -> ASGIApp:
    """
    Takes a function or coroutine `func(request) -> response`,
    and returns an ASGI application.
    """

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
        response = _process_response(response_manager, func_result)
        return await response(scope, receive, send)

    return app
