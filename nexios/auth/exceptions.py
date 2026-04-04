from typing import Any, Dict, Optional

from nexios.exceptions import HTTPException
from nexios.http import Request, Response

HeadersType = Dict[str, Any]  # Alias for better readability


class AuthException(HTTPException):
    """
    Base class for all authentication-related exceptions.
    """

    def __init__(
        self, status_code: int, detail: str, headers: Optional[HeadersType] = None
    ) -> None:
        """
        Initialize an authentication exception.

        Args:
            status_code (int): The HTTP status code.
            detail (str): A description of the error.
            headers (Optional[Dict[str, Any]]): Optional headers for the response.
        """
        super().__init__(status_code, detail, headers or {})


class AuthenticationFailed(AuthException):
    """
    Raised when authentication fails.
    """

    def __init__(
        self,
        detail: str = "Authentication failed",
        headers: Optional[HeadersType] = None,
    ) -> None:
        super().__init__(401, detail, headers)


class PermissionDenied(AuthException):
    """
    Raised when a user does not have the required permission.
    """

    def __init__(
        self,
        detail: str = "Permission denied",
        headers: Optional[HeadersType] = None,
    ) -> None:
        super().__init__(403, detail, headers)


async def AuthErrorHandler(
    request: Request, response: Response, exc: HTTPException
) -> Any:
    """
    Handle authentication exceptions and return a JSON response.

    Args:
        req (Request): The incoming HTTP request.
        res (Response): The outgoing HTTP response.
        exc (HTTPException): The raised HTTP exception.

    Returns:
        Response: JSON-formatted error response.
    """
    return response.json(exc.detail, status_code=exc.status_code, headers=exc.headers)
