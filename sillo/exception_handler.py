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
from sillo.core.helpers.async_helpers import collapse_excgroups
from sillo.core.http import HttpContext, json
from sillo.core.http.response import BaseResponse
from sillo.exceptions import HTTPException, NotFoundException
from sillo.handlers.not_found import handle_404_error
from sillo.types import (
    ASGIApp,
    ExceptionHandlerFor,
    ExceptionHandlerType,
    ExcT,
    Message,
    Receive,
    Scope,
    Send,
)
from sillo.validation import RequestValidationError, ResponseValidationError

logger = logging.getLogger("sillo")


def _lookup_exception_handler(
    exc_handlers: dict[int | type[Exception], ExceptionHandlerType],
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
    ctx: HttpContext,
    call_next: typing.Callable[..., typing.Awaitable[typing.Any]],
    exception_handlers: dict[int | type[Exception], ExceptionHandlerType],
    status_handlers: dict[int, ExceptionHandlerType],
):
    """Wrap request processing with exception handling for HTTP and custom exceptions.

    This async function executes the next middleware/handler in the chain and
    catches any exceptions that arise. It first checks status-code-based handlers
    for ``HTTPException`` instances, then falls back to class-based exception
    handler lookup via MRO traversal. Unhandled exceptions are logged and re-raised.

    Args:
        ctx: The context for the request being handled.
        call_next: An async callable representing the next middleware or
            handler in the processing chain. Calling it continues request
            processing.
        exception_handlers: A dictionary mapping exception classes to their
            handler callables. Handlers are looked up via MRO traversal.
        status_handlers: A dictionary mapping HTTP status codes (int) to
            handler callables. Used specifically for ``HTTPException``
            instances to match on their ``status_code`` attribute.

    Returns:
        The response returned by either the successful ``call_next``
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
    # These were assigned to themselves inside a try/except KeyError, which
    # could not raise and so could not default anything. Default them directly.
    exception_handlers = exception_handlers or {}
    status_handlers = status_handlers or {}

    try:
        return await call_next()
    except Exception as exc:
        handler: ExceptionHandlerType | None = None

        if isinstance(exc, HTTPException):
            handler: ExceptionHandlerType | None = status_handlers.get(exc.status_code)
            if handler:
                return await handler(ctx, exc)

        if handler is None:
            handler = _lookup_exception_handler(exception_handlers, exc)
            if not handler:
                error = traceback.format_exc()
                logger.error(error)
                raise
            return await handler(ctx, exc)


class ExceptionMiddleware:
    """Pure-ASGI middleware that maps exceptions onto registered handlers.

    This middleware sits in the ASGI middleware stack and intercepts exceptions
    raised by downstream handlers. It maintains two registries: one mapping
    exception classes to handler functions, and another mapping HTTP status
    codes to handler functions. Built-in handlers are pre-registered for
    ``HTTPException``, ``AuthenticationFailed``, ``NotFoundException``, and
    Pydantic ``ValidationError``.

    Like :class:`~sillo.core.error.handler.ServerErrorMiddleware` it is written
    in the plain ASGI form — ``__init__(app)`` and ``__call__(scope, receive,
    send)`` — rather than sillo's ``(request, response, call_next)`` dispatch
    form. It has no interest in a request that succeeds, so building a
    an ``HttpContext`` and a background task for one is pure waste;
    both objects are constructed inside the ``except`` clause and nowhere else.

    An exception with no matching handler is re-raised unchanged, which is how
    it reaches ``ServerErrorMiddleware`` and becomes a 500.

    Attributes:
        app: The next ASGI application in the chain. Assigned by the
            application when it assembles its chain, since the registries below
            outlive any single chain and must not be rebuilt with it.
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

    def __init__(self, app: ASGIApp | None = None) -> None:
        """Initialize the ExceptionMiddleware with default exception handlers.

        Sets up the middleware with an empty status handler registry and
        pre-populates the exception handler registry with built-in handlers
        for common framework exception types.

        Args:
            app: The next ASGI application to run. Optional because the
                application constructs this middleware before it has a chain to
                put it in, and assigns ``app`` when the chain is assembled.

        Returns:
            None. This is a constructor method.

        Note:
            The default handlers registered are:
            - ``HTTPException`` -> ``self.http_exception`` (JSON error response)
            - ``AuthenticationFailed`` -> ``AuthErrorHandler`` (auth error response)
            - ``NotFoundException`` -> ``handle_404_error`` (404 page/response)
            - ``ValidationError`` -> ``pydantic_validation_error_handler`` (422 response)
        """
        self.app = app
        self.debug = False
        self._status_handlers: dict[int, ExceptionHandlerType] = {}
        # Annotated rather than inferred. Left bare, this narrows to a dict of
        # exactly those six classes and their six distinct handler signatures,
        # so registering any *other* exception -- the entire purpose of
        # `add_exception_handler` -- becomes a type error.
        #
        # The cast erases each handler's own exception type for the same
        # reason `add_exception_handler` does: every one of these is narrowed
        # to the class it is keyed by, and it is the pairing inside this dict
        # that makes that sound. No annotation can state "the value's third
        # parameter is the key".
        self._exception_handlers: dict[type[Exception], ExceptionHandlerType] = (
            typing.cast(
                "dict[type[Exception], ExceptionHandlerType]",
                {
                    HTTPException: self.http_exception,
                    AuthenticationFailed: AuthErrorHandler,
                    NotFoundException: handle_404_error,
                    ValidationError: pydantic_validation_error_handler,
                    RequestValidationError: request_validation_error_handler,
                    ResponseValidationError: response_validation_error_handler,
                },
            )
        )

    def add_exception_handler(
        self,
        exc_class_or_status_code: int | type[ExcT],
        handler: ExceptionHandlerFor[ExcT],
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
                ``async (ctx, exc) -> BaseResponse`` that handles
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
        # The registries are keyed by exception class and hold the erased
        # signature. Narrowing is dropped deliberately at this boundary: a
        # handler is only ever invoked for the class it was registered
        # against, so the pairing that makes the narrow type sound is the
        # dictionary itself, which no annotation can express.
        erased = typing.cast(ExceptionHandlerType, handler)

        if isinstance(exc_class_or_status_code, int):
            self._status_handlers[exc_class_or_status_code] = erased
        else:
            assert issubclass(exc_class_or_status_code, Exception)
            self._exception_handlers[exc_class_or_status_code] = erased

    @property
    def has_handlers(self) -> bool:
        """Whether either registry holds anything for this middleware to match.

        With both empty there is no exception it could answer, so the request
        goes straight to the inner application with no ``try`` around it. Read
        per request rather than decided once, because handlers are registered
        after the chain exists — ``setup_record`` and the admin panel both do
        it while the application is still being configured.
        """
        return bool(self._exception_handlers or self._status_handlers)

    def _handler_for(self, exc: Exception) -> ExceptionHandlerType | None:
        """Find the handler registered for ``exc``, if any.

        Status-code handlers are consulted first and only for ``HTTPException``,
        since they key on ``status_code``, which nothing else carries. Anything
        else is matched by walking the exception's MRO, so a handler registered
        against a base class also catches its subclasses.

        Args:
            exc: The exception raised by the inner application.

        Returns:
            The matching handler, or ``None`` when nothing is registered for
            this exception or any of its base classes.
        """
        if isinstance(exc, HTTPException):
            status_handler = self._status_handlers.get(exc.status_code)
            if status_handler is not None:
                return status_handler
        return _lookup_exception_handler(self._exception_handlers, exc)  # ty: ignore[invalid-argument-type]

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Run the inner application, routing exceptions to registered handlers.

        Args:
            scope: The ASGI connection scope. Non-HTTP scopes are forwarded
                untouched, as are all scopes when nothing is registered.
            receive: The ASGI receive callable, passed straight through.
            send: The ASGI send callable, wrapped only to notice whether the
                response has already started.

        Returns:
            None.

        Raises:
            Exception: The original exception, re-raised unchanged when no
                handler matches it, or when one does but the inner application
                had already begun sending its response and there is nothing
                left to replace. ``ServerErrorMiddleware`` sits above this one
                and is what turns a re-raise into a 500.
        """
        if self.app is None:
            raise RuntimeError(
                "ExceptionMiddleware was constructed without an inner "
                "application and cannot serve requests. The application "
                "assigns it while assembling its middleware chain."
            )
        app = self.app

        if scope["type"] != "http" or not self.has_handlers:
            await app(scope, receive, send)
            return

        response_started = False

        async def send_watching_start(message: Message) -> None:
            """Forward an ASGI message, noting when the response begins.

            Args:
                message: The ASGI message the inner application is sending.
            """
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            with collapse_excgroups():
                await app(scope, receive, send_watching_start)
        except Exception as exc:
            handler = self._handler_for(exc)
            if handler is None or response_started:
                logger.error(traceback.format_exc())
                raise

            # Constructed only now. Nothing above this line touches a
            # context, which is the entire reason this middleware is pure ASGI
            # rather than a dispatch function.
            ctx = HttpContext(scope, receive)
            result = await handler(ctx, exc)  # ty: ignore[invalid-await]
            await result(scope, receive, send)

    async def http_exception(
        self, ctx: HttpContext, exc: HTTPException
    ) -> BaseResponse:
        """Handle an HTTPException by producing an appropriate error response.

        Converts an ``HTTPException`` into an HTTP response. For status codes
        204 (No Content) and 304 (Not Modified), an empty response is returned.
        For all other status codes, a JSON response containing the exception's
        detail message is returned.

        Args:
            ctx: The context for the request that triggered the exception.
            exc: The ``HTTPException`` instance to handle. Contains the status
                code, detail message, and optional headers.

        Returns:
            A response with the appropriate status code, headers,
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
            return BaseResponse(
                body=b"", status_code=exc.status_code, headers=exc.headers
            )
        return json(exc.detail, status_code=exc.status_code, headers=exc.headers)


async def request_validation_error_handler(ctx: HttpContext, exc: RequestValidationError) -> BaseResponse:
    """Handle a request validation failure with a 422 response.

    This is the unified error contract for parameters declared with sillo's
    validation markers. Every failure carries a ``loc`` whose first element
    names the request location it came from, so a client can tell a bad query
    string from a malformed body without guessing::

        {"detail": [{"loc": ["query", "page"], "msg": "...", "type": "..."}]}

    All failures across all locations are reported together rather than one per
    round trip.

    Args:
        request: The incoming request whose data failed validation.
        exc: The ``RequestValidationError`` carrying the location-prefixed
            error dictionaries.

    Returns:
        A response with status 422 and a ``detail`` list of errors.
    """
    return json({"detail": exc.errors}, status_code=422)


async def response_validation_error_handler(ctx: HttpContext, exc: ResponseValidationError) -> BaseResponse:
    """Handle a response validation failure with a 500 response.

    A handler returned something its declared ``response_model`` does not
    permit. The caller did nothing wrong, so this is reported as a server
    error; returning 422 here would wrongly blame the client and would mislead
    clients that retry on 4xx.

    The offending value is deliberately not echoed to the client, since it may
    contain data the response model was there to filter out in the first place.

    Args:
        ctx: The context for the request being served.
        exc: The ``ResponseValidationError`` describing the contract violation.

    Returns:
        A response with status 500 and a generic error body.
    """
    logger.error(
        "Response validation failed for %s %s: %s",
        ctx.method,
        ctx.url.path,
        exc.errors,
    )
    return json(
        {"error": "Internal Server Error", "detail": "Response validation failed"},
        status_code=500,
    )


async def pydantic_validation_error_handler(ctx: HttpContext, exc: ValidationError) -> BaseResponse:
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
        A response with status 422 and a JSON body containing:
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
            nested = error_dict.get(loc[0])
            if not isinstance(nested, dict):
                nested = {}
                error_dict[loc[0]] = nested
            nested[loc[1]] = msg
        else:
            error_dict[".".join(map(str, loc))] = msg
    return json(
        {"error": "Validation Error", "errors": error_dict},
        status_code=422,
    )
