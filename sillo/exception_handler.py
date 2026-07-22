from __future__ import annotations

import traceback
import typing

from pydantic import ValidationError

from sillo import logging
from sillo.auth.exceptions import AuthenticationFailed, AuthErrorHandler
from sillo.exceptions import HTTPException, NotFoundException
from sillo.handlers.not_found import handle_404_error
from sillo.http import Request, Response
from sillo.types import ExceptionHandlerType

logger = logging.getLogger("sillo")


def _lookup_exception_handler(
    exc_handlers: typing.Dict[int | typing.Type[Exception], ExceptionHandlerType],
    exc: Exception,
):
    for cls in type(exc).__mro__:
        if cls in exc_handlers:
            return exc_handlers[cls]  # ty: ignore[invalid-argument-type]
    return None


async def wrap_http_exceptions(
    request: Request,
    response: Response,
    call_next: typing.Callable[..., typing.Awaitable[Response]],
    exception_handlers: typing.Dict[int | typing.Type[Exception], ExceptionHandlerType],
    status_handlers: typing.Dict[int, ExceptionHandlerType],
):
    try:
        exception_handlers, status_handlers = exception_handlers, status_handlers
    except KeyError:
        exception_handlers, status_handlers = {}, {}

    try:
        return await call_next()
    except Exception as exc:
        handler: typing.Union[ExceptionHandlerType, None] = None

        if isinstance(exc, HTTPException):
            handler: typing.Optional[ExceptionHandlerType] = status_handlers.get(
                exc.status_code
            )
            if handler:
                return await handler(request, response, exc)

        if handler is None:
            handler = _lookup_exception_handler(exception_handlers, exc)
            if not handler:
                error = traceback.format_exc()
                logger.error(error)
                raise exc
            return await handler(request, response, exc)


class ExceptionMiddleware:
    def __init__(self) -> None:
        self.debug = False
        self._status_handlers: typing.Dict[int, ExceptionHandlerType] = {}
        self._exception_handlers = {
            HTTPException: self.http_exception,
            AuthenticationFailed: AuthErrorHandler,
            NotFoundException: handle_404_error,
            ValidationError: pydantic_validation_error_handler,
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
            self._exception_handlers[exc_class_or_status_code] = handler  # ty: ignore[invalid-assignment]

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
            exception_handlers=self._exception_handlers,  # ty :ignore
            status_handlers=self._status_handlers,
        )

    async def http_exception(
        self, request: Request, response: Response, exc: HTTPException
    ) -> Response:
        assert isinstance(exc, HTTPException)
        if exc.status_code in {204, 304}:
            return response.empty(status_code=exc.status_code, headers=exc.headers)
        return response.json(
            exc.detail, status_code=exc.status_code, headers=exc.headers
        )


async def pydantic_validation_error_handler(
    request: Request, response: Response, exc: ValidationError
) -> Response:
    errors = exc.errors()
    error_dict = {}
    for e in errors:
        loc, msg = e["loc"], e["msg"]
        if len(loc) == 1:
            error_dict[loc[0]] = msg
        elif len(loc) == 2:
            if loc[0] not in error_dict:
                error_dict[loc[0]] = {}
            error_dict[loc[0]][loc[1]] = msg
        else:
            error_dict[".".join(map(str, loc))] = msg
    return response.json(
        {"error": "Validation Error", "errors": error_dict},
        status_code=422,
    )
