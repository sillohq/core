from typing import Any

from sillo.core.http import HttpContext
from sillo.exceptions import HTTPException
from sillo.responses import json

HeadersType = dict[str, Any]  # Alias for better readability
"""Type alias for HTTP header dictionaries used in auth exception responses.

Provides a readable alias for ``Dict[str, Any]`` to improve code clarity
when specifying header parameters in authentication exception constructors.
The keys are header names (strings) and values are header values (any type
accepted by the HTTP response layer).
"""


class AuthException(HTTPException):
    """Base class for all authentication-related exceptions in sillo.

    Serves as the root of the authentication exception hierarchy. All
    auth-specific errors (authentication failures, permission denials, etc.)
    inherit from this class, allowing callers to catch any auth error with
    a single ``except AuthException`` clause.

    Inherits from :class:`sillo.exceptions.HTTPException` so that instances
    can be directly converted into HTTP error responses by the framework's
    exception handling pipeline.

    Attributes:
        status_code: The HTTP status code associated with this error.
        detail: A human-readable description of the error condition.
        headers: Optional dictionary of HTTP headers to include in the
            error response (e.g. ``WWW-Authenticate``).

    Example:
        Catch all auth-related errors with a single except clause::

            try:
                await authenticate_user(request)
            except AuthException as exc:
                return json({"error": exc.detail}, status_code=exc.status_code)
    """

    def __init__(
        self, status_code: int, detail: str, headers: HeadersType | None = None
    ) -> None:
        """Initialise an authentication exception with status and detail.

        Constructs the base auth exception by forwarding all arguments to
        the parent ``HTTPException`` constructor. The ``headers`` parameter
        defaults to an empty dictionary if not provided.

        Args:
            status_code: The HTTP status code to use when this exception is
                converted into an HTTP response. Common values include 401
                (Unauthorized) and 403 (Forbidden).
            detail: A human-readable description of the authentication error.
                This string is included in the JSON error response body.
            headers: Optional dictionary of HTTP headers to include in the
                error response. Useful for adding ``WWW-Authenticate`` or
                custom authentication challenge headers. Defaults to ``None``.

        Returns:
            None. This is a constructor that initialises the exception state.

        Raises:
            No exceptions are raised during initialisation.
        """
        super().__init__(status_code, detail, headers or {})


class AuthenticationFailed(AuthException):
    """Raised when authentication fails or no valid credentials are provided.

    This exception corresponds to HTTP 401 Unauthorized. It is raised by
    authentication decorators and gates when the request does not contain
    valid credentials or when all authentication backends fail to identify
    the caller.

    The framework's error handler converts this into a JSON response with
    status code 401 and the ``detail`` message as the response body.

    Attributes:
        status_code: Always 401 for this exception class.
        detail: Human-readable error description. Defaults to
            ``"Authentication failed"``.
        headers: Optional response headers for the error response.
    """

    def __init__(
        self,
        detail: str = "Authentication failed",
        headers: HeadersType | None = None,
    ) -> None:
        """Initialise an AuthenticationFailed exception with HTTP 401 status.

        Constructs the exception with a fixed 401 status code and a
        configurable detail message. The detail defaults to a generic
        authentication failure message if not overridden.

        Args:
            detail: A human-readable description of why authentication
                failed. Defaults to ``"Authentication failed"``. Override
                to provide more specific error information to the client.
            headers: Optional dictionary of HTTP headers to include in the
                401 error response. Common usage includes ``WWW-Authenticate``
                to indicate supported authentication schemes.

        Returns:
            None. This is a constructor that initialises the exception.

        Raises:
            No exceptions are raised during initialisation.
        """
        super().__init__(401, detail, headers)


class PermissionDenied(AuthException):
    """Raised when an authenticated user lacks the required permission.

    This exception corresponds to HTTP 403 Forbidden. It is raised by
    permission-checking decorators and gates when the authenticated user
    does not possess one or more of the required permissions for the
    requested resource or action.

    Unlike ``AuthenticationFailed`` (401), the user is authenticated but
    is not authorised to perform the requested operation.

    Attributes:
        status_code: Always 403 for this exception class.
        detail: Human-readable error description. Defaults to
            ``"Permission denied"``.
        headers: Optional response headers for the error response.
    """

    def __init__(
        self,
        detail: str = "Permission denied",
        headers: HeadersType | None = None,
    ) -> None:
        """Initialise a PermissionDenied exception with HTTP 403 status.

        Constructs the exception with a fixed 403 status code and a
        configurable detail message. The detail defaults to a generic
        permission denied message if not overridden.

        Args:
            detail: A human-readable description of why the permission
                was denied. Defaults to ``"Permission denied"``. Override
                to provide more specific information about the missing
                permission or the resource that was accessed.
            headers: Optional dictionary of HTTP headers to include in the
                403 error response. Typically not needed for permission
                errors but available for custom use cases.

        Returns:
            None. This is a constructor that initialises the exception.

        Raises:
            No exceptions are raised during initialisation.
        """
        super().__init__(403, detail, headers)


async def AuthErrorHandler(ctx: HttpContext, exc: HTTPException) -> Any:
    """Handle authentication exceptions and return a JSON error response.

    This async error handler is registered with the framework to convert
    ``AuthException`` instances (and their subclasses) into JSON-formatted
    HTTP error responses. It extracts the detail message, status code, and
    headers from the exception and produces a consistent error response body.

    The handler is typically registered during application setup to ensure
    that authentication and permission errors produce well-formed JSON
    responses rather than HTML error pages.

    Args:
        ctx: The context for the request that triggered the authentication
            error. Available for logging or context extraction but not
            modified by this handler.
        exc: The HTTP exception instance that was raised during authentication.
            Its ``detail``, ``status_code``, and ``headers`` attributes are
            used to construct the error response.

    Returns:
        A JSON-formatted HTTP response containing the error detail
            message as the body, with the status code and headers from the
            exception. The response content type is ``application/json``.

    Raises:
        No exceptions are raised by this handler.
    """
    return json(exc.detail, status_code=exc.status_code, headers=exc.headers)
