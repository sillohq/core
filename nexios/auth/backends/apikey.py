import hashlib
import secrets
from typing import Any

from typing_extensions import Annotated, Doc

from nexios.auth.backends.base import AuthenticationBackend
from nexios.auth.model import AuthResult
from nexios.http import Request, Response

prefix = "key"


def create_api_key() -> tuple[str, str]:
    raw_token = secrets.token_urlsafe(32)

    api_key = f"{prefix}_{raw_token}"

    hashed = hashlib.sha256(api_key.encode()).hexdigest()
    return api_key, hashed


def verify_key(api_key: str, stored_hash: str) -> bool:
    """
    Verify an incoming API key against a stored hash.
    """
    hashed_input = hashlib.sha256(api_key.encode()).hexdigest()
    return secrets.compare_digest(hashed_input, stored_hash)


class APIKeyAuthBackend(AuthenticationBackend):
    """
    Authentication backend for API key-based authentication.

    This class verifies incoming requests using API keys found in request headers.
    It relies on a user-defined authentication function to validate API keys.

    Attributes:
        authenticate_func (Callable[..., Awaitable[Any]]): The function used to validate API keys.
        header_name (str): The HTTP header used to pass the API key (default: "X-API-Key").
    """

    def __init__(
        self,
        header_name: Annotated[
            str,
            Doc(
                'The header name from which the API key is retrieved (default: "X-API-Key").'
            ),
        ] = "X-API-Key",
        prefix: Annotated[
            str,
            Doc('The prefix for the API key (default: "key").'),
        ] = "key",
    ) -> None:
        """
        Initializes the APIKeyAuthBackend with an authentication function and optional header name.

        Args:
            authenticate_func (Callable[..., Awaitable[Any]]): Function to validate API keys.
            header_name (str, optional): Header key where the API key is expected (default: "X-API-Key").
        """
        self.header_name = header_name
        self.prefix = prefix

    async def authenticate(  # type: ignore[override]
        self,
        request: Annotated[
            Request,
            Doc(
                "The incoming HTTP request, containing authentication credentials in headers."
            ),
        ],
        response: Annotated[
            Response,
            Doc(
                "The HTTP response object, which may be modified for authentication-related headers."
            ),
        ],
    ) -> Any:
        """
        Authenticates the request by checking for an API key in the specified header.

        This method extracts the API key from the request headers and verifies it
        using the provided authentication function.

        Args:
            request (Request): The incoming HTTP request.
            response (Response): The response object (may be modified).

        Returns:
            Any: A user object if authentication is successful, `UnauthenticatedUser` if invalid, or `None` if no API key is provided.

        Side Effects:
            - If no API key is found, sets the `WWW-Authenticate` response header.
        """
        # Retrieve the API key from the request headers
        raw_token = request.headers.get(self.header_name)

        if not raw_token:
            response.set_header("WWW-Authenticate", 'APIKey realm="Access to the API"')
            return AuthResult(success=False, identity="", scope="")

        # Authenticate the API key using the provided function
        return AuthResult(success=True, identity=raw_token, scope="apikey")
