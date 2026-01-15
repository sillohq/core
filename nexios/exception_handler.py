from __future__ import annotations

import traceback
import typing

from nexios import logging
from nexios._internals._response_transformer import (
    _process_response,  # type: ignore[import] #
)
from nexios.auth.exceptions import AuthenticationFailed, AuthErrorHandler
from nexios.config import get_config
from nexios.exceptions import HTTPException, NotFoundException
from nexios.handlers.not_found import handle_404_error
from nexios.http import Request, Response
from nexios.types import ExceptionHandlerType

logger = logging.getLogger("nexios")


def _lookup_exception_handler(
    exc_handlers: typing.Dict[typing.Any[int, Exception], ExceptionHandlerType],
    exc: Exception,
):
    for cls in type(exc).__mro__:
        if cls in exc_handlers:  # type: ignore
            return exc_handlers[cls]
    return None


async def wrap_http_exceptions(
    request: Request,
    response: Response,
    call_next: typing.Callable[..., typing.Awaitable[Response]],
    exception_handlers: typing.Dict[type[Exception], ExceptionHandlerType],
    status_handlers: typing.Dict[int, ExceptionHandlerType],
) -> typing.Any:
    try:
        exception_handlers, status_handlers = exception_handlers, status_handlers
    except KeyError:
        exception_handlers, status_handlers = {}, {}

    try:
        return await call_next()
    except Exception as exc:
        handler: typing.Union[ExceptionHandlerType, None] = None  # type: ignore

        if isinstance(exc, HTTPException):
            handler: typing.Optional[ExceptionHandlerType] = status_handlers.get(
                exc.status_code
            )  # type: ignore
            if handler:
                return _process_response(
                    response, await handler(request, response, exc)
                )  # type: ignore

        if handler is None:  # type: ignore
            handler = _lookup_exception_handler(exception_handlers, exc)
            if not handler:
                error = traceback.format_exc()
                logger.error(error)
                raise exc
            return _process_response(response, await handler(request, response, exc))


class ExceptionMiddleware:
    def __init__(self) -> None:
        try:
            self.debug = (
                get_config().debug or False
            )  # TODO: We ought to handle 404 cases if debug is set.
        except Exception:
            self.debug = True
        self._status_handlers: typing.Dict[int, ExceptionHandlerType] = {}
        self._exception_handlers: dict[
            typing.Type[Exception], typing.Callable[..., typing.Awaitable[None]]
        ] = {
            HTTPException: self.http_exception,
            AuthenticationFailed: AuthErrorHandler,
            NotFoundException: handle_404_error,
        }

    def add_exception_handler(
        self,
        exc_class_or_status_code: typing.Union[int, type[Exception]],
        handler: ExceptionHandlerType,
    ) -> None:
        if isinstance(exc_class_or_status_code, int):
            self._status_handlers[exc_class_or_status_code] = handler
        else:
            assert issubclass(exc_class_or_status_code, Exception)
            self._exception_handlers[exc_class_or_status_code] = handler  # type:ignore

    async def __call__(
        self,
        request: Request,
        response: Response,
        call_next: typing.Callable[[], typing.Awaitable[Response]],
    ):
        if len(self._exception_handlers) == 0 and len(self._status_handlers) == 0:
            return await call_next()
        return await wrap_http_exceptions(
            request=request,
            response=response,
            call_next=call_next,
            exception_handlers=self._exception_handlers,
            status_handlers=self._status_handlers,
        )

    async def http_exception(
        self, request: Request, response: Response, exc: HTTPException
    ) -> typing.Any:
        assert isinstance(exc, HTTPException)
        if exc.status_code in {204, 304}:  # type:ignore
            return response.empty(status_code=exc.status_code, headers=exc.headers)
        return response.json(
            exc.detail, status_code=exc.status_code, headers=exc.headers
        )
