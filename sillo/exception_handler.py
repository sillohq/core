"""Exception handling middleware and utilities for the sillo framework.

This module provides the exception handling pipeline that catches exceptions
raised during request processing and converts them into appropriate HTTP
responses. It includes a middleware class, handler lookup utilities, and
built-in handlers for common exception types like ``HTTPException``,
``ValidationError``, and authentication failures.
"""

from __future__ import annotations

import traceback
import typing

from pydantic import ValidationError

from sillo import logging
from sillo.auth.exceptions import AuthenticationFailed, AuthErrorHandler
from sillo.exceptions import HTTPException, NotFoundException
from sillo.handlers.not_found import handle_404_error
from sillo.core.http import Request, Response
from sillo.types import ExceptionHandlerType

logger = logging.getLogger("sillo")


def _lookup_exception_handler(
    exc_handlers: typing.Dict[int | typing.Type[Exception], ExceptionHandlerType],
    exc: Exception,
):
    """Look up the appropriate exception handler by walking the exception's MRO.

    Searches the exception handler registry for a handler matching the
    exception's class or any of its base classes. The search follows the
    Method Resolution Order (MRO), ensuring that the most specific handler
    is found first.

    Args:
        exc_handlers: A dictionary mapping exception classes (or status codes)
            to their handler callables. The keys are exception types, not
            instances.
        exc: The exception instance to find a handler for. The handler lookup
            walks ``type(exc).__mro__`` to find the most specific match.

    Returns:
        The handler callable if a matching handler is found, or ``None`` if
        no handler is registered for the exception's class or any of its
        base classes.

    Note:
        This function enables polymorphic exception handling: registering a
        handler for a base exception class (e.g., ``Exception``) will catch
        all subclass instances unless a more specific handler is registered.
        The MRO walk ensures correct method resolution semantics.
    """
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
    """Wrap request processing with exception handling for HTTP and custom exceptions.

    This async function executes the next middleware/handler in the chain and
    catches any exceptions that arise. It first checks status-code-based handlers
    for ``HTTPException`` instances, then falls back to class-based exception
    handler lookup via MRO traversal. Unhandled exceptions are logged and re-raised.

    Args:
        request: The incoming HTTP request object containing scope, headers,
            and other request metadata.
        response: The response object used to construct the HTTP response.
            Handlers receive this to build their response output.
        call_next: An async callable representing the next middleware or
            handler in the processing chain. Calling it continues request
            processing.
        exception_handlers: A dictionary mapping exception classes to their
            handler callables. Handlers are looked up via MRO traversal.
        status_handlers: A dictionary mapping HTTP status codes (int) to
            handler callables. Used specifically for ``HTTPException``
            instances to match on their ``status_code`` attribute.

    Returns:
        The ``Response`` object returned by either the successful ``call_next``
        invocation or by an exception handler.

    Raises:
        Exception: If no handler is found for the raised exception, the
            original exception is re-raised after logging the full traceback.

    Note:
        This function is the core of the exception handling pipeline. It is
        called by ``ExceptionMiddleware.__call__`` and should not typically
        be invoked directly by application code. The try/except around the
        variable assignment is a defensive guard against KeyError in edge cases.
    """
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
                return await handler(request, response, exc)  # ty: ignore[invalid-await]

        if handler is None:
            handler = _lookup_exception_handler(exception_handlers, exc)
            if not handler:
                error = traceback.format_exc()
                logger.error(error)
                raise exc
            return await handler(request, response, exc)


class ExceptionMiddleware:
    """Middleware that catches exceptions during request processing and returns error responses.

    This middleware sits in the ASGI middleware stack and intercepts exceptions
    raised by downstream handlers. It maintains two registries: one mapping
    exception classes to handler functions, and another mapping HTTP status
    codes to handler functions. Built-in handlers are pre-registered for
    ``HTTPException``, ``AuthenticationFailed``, ``NotFoundException``, and
    Pydantic ``ValidationError``.

    Attributes:
        debug: A boolean flag indicating whether debug mode is enabled. When
            True, additional error details may be included in responses.
            Defaults to False.
        _status_handlers: Internal dictionary mapping HTTP status codes to
            exception handler callables.
        _exception_handlers: Internal dictionary mapping exception classes to
            exception handler callables. Pre-populated with default handlers.

    Note:
        Applications can register custom exception handlers via the
        ``add_exception_handler`` method or the application-level
        ``add_exception_handler`` convenience method. Custom handlers
        override the built-in defaults for their respective exception types.
    """

    def __init__(self) -> None:
        """Initialize the ExceptionMiddleware with default exception handlers.

        Sets up the middleware with an empty status handler registry and
        pre-populates the exception handler registry with built-in handlers
        for common framework exception types.

        Args:
            No arguments.

        Returns:
            None. This is a constructor method.

        Note:
            The default handlers registered are:
            - ``HTTPException`` -> ``self.http_exception`` (JSON error response)
            - ``AuthenticationFailed`` -> ``AuthErrorHandler`` (auth error response)
            - ``NotFoundException`` -> ``handle_404_error`` (404 page/response)
            - ``ValidationError`` -> ``pydantic_validation_error_handler`` (422 response)
        """
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
        """Register a custom exception handler for a specific exception class or status code.

        Adds a handler function to the appropriate internal registry. If the
        key is an integer, it is treated as an HTTP status code and added to
        the status handler registry. If it is an exception class, it is added
        to the exception class handler registry.

        Args:
            exc_class_or_status_code: Either an integer HTTP status code
                (e.g., 404, 500) or an exception class (e.g., ``ValueError``,
                ``HTTPException``). Determines which internal registry the
                handler is added to.
            handler: An async callable with signature
                ``async (request, response, exc) -> Response`` that handles
                the exception and produces an HTTP response.

        Returns:
            None. This method modifies internal state as a side effect.

        Raises:
            AssertionError: If ``exc_class_or_status_code`` is not an integer
                and not a subclass of ``Exception``.

        Note:
            Registering a handler for an exception class that already has a
            handler will replace the existing handler. This allows applications
            to override the built-in default handlers.
        """
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
        """Process the request through the exception handling pipeline.

        This is the ASGI middleware entry point. If no handlers are registered,
        it passes through to the next middleware directly. Otherwise, it
        delegates to ``wrap_http_exceptions`` which provides the full exception
        catching and handling logic.

        Args:
            request: The incoming HTTP request object.
            response: The response builder object for constructing responses.
            call_next: An async callable that continues processing to the next
                middleware or route handler in the chain.

        Returns:
            The ``Response`` object from either the successful handler or an
            exception handler.

        Note:
            The optimization of skipping ``wrap_http_exceptions`` when no
            handlers are registered avoids the overhead of try/except blocks
            in the common case where no custom exception handling is needed.
        """
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
        """Handle an HTTPException by producing an appropriate error response.

        Converts an ``HTTPException`` into an HTTP response. For status codes
        204 (No Content) and 304 (Not Modified), an empty response is returned.
        For all other status codes, a JSON response containing the exception's
        detail message is returned.

        Args:
            request: The incoming HTTP request that triggered the exception.
            response: The response builder object used to construct the error
                response.
            exc: The ``HTTPException`` instance to handle. Contains the status
                code, detail message, and optional headers.

        Returns:
            A ``Response`` object with the appropriate status code, headers,
            and body. Either an empty response (for 204/304) or a JSON response
            containing the exception detail.

        Note:
            The 204 and 304 status codes are special-cased because HTTP
            specifications prohibit response bodies for these codes. The
            exception's headers (e.g., ``WWW-Authenticate``) are always
            included in the response regardless of the status code.
        """
        assert isinstance(exc, HTTPException)
        if exc.status_code in {204, 304}:
            return response.empty(status_code=exc.status_code, headers=exc.headers)
        return response.json(
            exc.detail, status_code=exc.status_code, headers=exc.headers
        )


async def pydantic_validation_error_handler(
    request: Request, response: Response, exc: ValidationError
) -> Response:
    """Handle a Pydantic ValidationError by producing a structured 422 error response.

    Converts a Pydantic ``ValidationError`` into a JSON response with HTTP
    status 422 (Unprocessable Entity). The response body contains a structured
    error dictionary that maps field paths to their validation error messages,
    making it easy for API clients to identify and fix invalid input.

    Args:
        request: The incoming HTTP request that triggered the validation error.
        response: The response builder object used to construct the error
            response with JSON body and appropriate status code.
        exc: The Pydantic ``ValidationError`` instance containing one or more
            field-level validation errors with location tuples and messages.

    Returns:
        A ``Response`` object with status 422 and a JSON body containing:
        - ``"error"``: The string ``"Validation Error"``.
        - ``"errors"``: A dictionary mapping field paths to error messages.
          Single-level fields map directly (e.g., ``{"name": "required"}``).
          Two-level fields nest (e.g., ``{"address": {"city": "required"}}``).
          Deeper paths use dot-separated keys (e.g., ``{"a.b.c": "invalid"}``).

    Note:
        The hierarchical error structure supports up to two levels of nesting
        without dot notation. Deeper paths are flattened with dot-separated
        keys. This design balances readability for common cases with the
        ability to represent arbitrarily deep validation paths.
    """
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
