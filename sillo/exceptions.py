"""HTTP and WebSocketContext exception classes for the sillo framework.

This module defines the exception hierarchy used throughout sillo for signaling
HTTP error responses and WebSocketContext close events. These exceptions can be raised
from any handler or middleware, and are caught by the exception middleware to
produce appropriate HTTP responses or WebSocketContext close frames.
"""

from __future__ import annotations

import http
import typing


class HTTPException(Exception):
    """Exception representing an HTTP error response with a status code.

    This is the base exception class for all HTTP-level errors in the sillo
    framework. When raised from a request handler or middleware, the exception
    middleware catches it and converts it into an HTTP response with the
    specified status code, detail message, and optional headers.

    The exception integrates with Python's standard ``http.HTTPStatus`` enum
    to provide default reason phrases when no explicit detail is given.

    Attributes:
        status_code: The HTTP status code for the error response (e.g., 400,
            404, 500). Must be a valid HTTP status code.
        detail: A human-readable description of the error. If not provided,
            defaults to the standard HTTP reason phrase for the status code.
        headers: A dictionary of additional HTTP headers to include in the
            error response. Commonly used for ``WWW-Authenticate`` on 401
            responses or ``Retry-After`` on 429 responses.

    Note:
        Subclasses like ``NotFoundException`` provide convenient constructors
        for commonly used status codes. Custom subclasses can be registered
        with specific exception handlers via ``app.add_exception_handler``.
    """

    def __init__(
        self,
        status_code: int,
        detail: typing.Any | None = None,
        headers: dict[str, typing.Any] = {},
    ) -> None:
        """Initialize an HTTPException with status code, detail, and headers.

        Constructs an HTTP exception that will be converted to an HTTP response
        by the exception middleware. The detail message defaults to the standard
        HTTP reason phrase if not explicitly provided.

        Args:
            status_code: The HTTP status code for the error response. Must be
                a valid HTTP status code recognized by ``http.HTTPStatus``.
            detail: An optional error description. Can be any JSON-serializable
                value (string, dict, list). If None, the standard HTTP reason
                phrase for the status code is used.
            headers: An optional dictionary of HTTP headers to include in the
                error response. Defaults to an empty dict.

        Returns:
            None. This is a constructor method.

        Raises:
            http.HTTPStatus: If the status_code is not a valid HTTP status
                code and no detail is provided (the phrase lookup will fail).

        Note:
            The ``headers`` parameter uses a mutable default argument (empty dict).
            This is intentional since the dict is only read, never mutated, by
            the exception handling code.
        """
        super().__init__(detail or http.HTTPStatus(status_code).phrase)
        self.status_code = status_code
        self.detail = self.args[0]
        self.headers = headers

    def __str__(self) -> str:
        """Return a human-readable string representation of the HTTP exception.

        Formats the exception as ``"HTTP {status_code}: {detail}"`` for
        display in logs, tracebacks, and debugging output.

        Args:
            No arguments beyond ``self``.

        Returns:
            A formatted string containing the HTTP status code and detail
            message, e.g., ``"HTTP 404: Not Found"``.

        Note:
            This representation is intended for human consumption in logs and
            debugging. For machine-readable representations, use ``__repr__``.
        """
        return f"HTTP {self.status_code}: {self.detail}"

    def __repr__(self) -> str:
        """Return a developer-oriented representation of the HTTP exception.

        Formats the exception as a constructor-like string for debugging and
        development purposes, showing the class name, status code, and detail.

        Args:
            No arguments beyond ``self``.

        Returns:
            A string in the format ``"HTTPException(404, 'Not Found')"`` that
            resembles a Python constructor call.

        Note:
            This representation is useful for debugging and can help identify
            the exact exception type and parameters in stack traces.
        """
        return f"{self.__class__.__name__}({self.status_code}, {self.detail!r})"


class NotFoundException(HTTPException):
    """Exception for HTTP 404 Not Found responses.

    A convenience subclass of ``HTTPException`` that automatically sets the
    status code to 404. This is the most commonly raised HTTP exception, used
    when a requested resource does not exist.

    Attributes:
        status_code: Always 404 for this exception class.
        detail: Defaults to ``"Not Found"`` if not explicitly provided.
        headers: Optional additional HTTP headers for the 404 response.

    Note:
        This exception is also handled specially by the ``ExceptionMiddleware``
        which registers a dedicated ``handle_404_error`` handler for it. The
        handler may render a custom 404 page if one is configured.
    """

    def __init__(
        self,
        detail: str | None = None,
        headers: dict[str, typing.Any] = {},
    ) -> None:
        """Initialize a NotFoundException with optional detail and headers.

        Constructs a 404 exception. The status code is fixed at 404 and cannot
        be changed. The detail message defaults to ``"Not Found"``.

        Args:
            detail: An optional description of what was not found. If None,
                defaults to the string ``"Not Found"``.
            headers: An optional dictionary of HTTP headers to include in the
                404 response. Defaults to an empty dict.

        Returns:
            None. This is a constructor method.

        Note:
            This is a convenience wrapper. ``raise NotFoundException()`` is
            equivalent to ``raise HTTPException(status_code=404)``.
        """
        super().__init__(status_code=404, detail=detail or "Not Found", headers=headers)


class WebSocketException(Exception):
    """Exception representing a WebSocketContext close event with a code and reason.

    This exception is used to signal that a WebSocketContext connection should be
    closed with a specific close code and optional reason string. When raised
    from a WebSocketContext handler, the framework catches it and sends a WebSocketContext
    close frame with the specified code and reason.

    Attributes:
        code: The WebSocketContext close code (e.g., 1000 for normal closure, 1008
            for policy violation). Must be a valid WebSocketContext close code.
        reason: An optional human-readable string explaining why the connection
            is being closed. Limited in length by the WebSocketContext protocol.

    Note:
        WebSocketContext close codes are defined in RFC 6455 and the IANA WebSocketContext
        registry. Common codes include 1000 (normal), 1001 (going away), 1008
        (policy violation), and 1011 (internal error).
    """

    def __init__(self, code: int, reason: str | None = None) -> None:
        """Initialize a WebSocketException with a close code and reason.

        Constructs a WebSocketContext exception that will result in a close frame
        being sent to the client with the specified code and reason.

        Args:
            code: The WebSocketContext close code. Must be a valid close code as
                defined in RFC 6455 (e.g., 1000-1015 range).
            reason: An optional human-readable string explaining the close
                reason. If None, defaults to an empty string.

        Returns:
            None. This is a constructor method.

        Note:
            The close code is sent as part of the WebSocketContext close frame and
            determines how the client interprets the disconnection. The reason
            string is limited to 123 bytes by the WebSocketContext protocol.
        """
        super().__init__(reason or "")
        self.code = code
        self.reason = self.args[0]

    def __str__(self) -> str:
        """Return a human-readable string representation of the WebSocketContext exception.

        Formats the exception as ``"WebSocketContext {code}: {reason}"`` for display
        in logs, tracebacks, and debugging output.

        Args:
            No arguments beyond ``self``.

        Returns:
            A formatted string containing the WebSocketContext close code and reason,
            e.g., ``"WebSocketContext 1008: Policy violation"``.

        Note:
            This representation is intended for human consumption in logs and
            debugging output.
        """
        return f"WebSocketContext {self.code}: {self.reason}"

    def __repr__(self) -> str:
        """Return a developer-oriented representation of the WebSocketContext exception.

        Formats the exception as a constructor-like string for debugging and
        development purposes.

        Args:
            No arguments beyond ``self``.

        Returns:
            A string in the format ``"WebSocketException(1008, 'Policy violation')"``
            that resembles a Python constructor call.

        Note:
            This representation is useful for debugging and identifying the
            exact exception parameters in stack traces.
        """
        return f"{self.__class__.__name__}({self.code}, {self.reason!r})"
