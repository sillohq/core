import asyncio
import typing
from enum import Enum

from pydantic import BaseModel

from nexios.dependencies import Context, current_context
from nexios.http import Request, Response
from nexios.http.response import BaseResponse
from nexios.types import ASGIApp, Receive, Scope, Send
from nexios.utils.async_helpers import is_async_callable
from nexios.utils.concurrency import run_in_threadpool


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
    return response_manager.get_response()


async def request_response(
    func: typing.Callable[[Request, Response], typing.Awaitable[Response]],
) -> ASGIApp:
    """
    Takes a function or coroutine `func(request) -> response`,
    and returns an ASGI application.
    """
    assert asyncio.iscoroutinefunction(func), "Endpoints must be async"

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        request = Request(scope, receive, send)

        # Get or create response manager for this request
        # __new__ automatically returns existing instance if available
        response_manager = Response(request)

        ctx = Context(
            request=request,
            user=getattr(request, "user", None),
            app=request.app,
            base_app=getattr(request, "base_app", None),
        )
        token = current_context.set(ctx)
        try:
            if is_async_callable(func):
                func_result = await func(
                    request, response_manager, **request.path_params
                )
            else:
                func_result = await run_in_threadpool(
                    func, request, response_manager, **request.path_params
                )
        finally:
            current_context.reset(token)
        response = _process_response(response_manager, func_result)
        response_manager.set_body(response.body)
        return await response(scope, receive, send)

    return app
