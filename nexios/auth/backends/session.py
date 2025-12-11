from typing import Any

from nexios.auth.backends.base import AuthenticationBackend
from nexios.auth.model import AuthResult
from nexios.auth.users.base import BaseUser
from nexios.http import Request, Response

_session_key = "user"
_identifier = "id"


def login(request: Request, user: type[BaseUser]):
    assert "session" in request.scope, "No Session Middleware Installed"
    if request.session.get(_session_key):
        del request.session[_session_key]
    request.session[_session_key] = {
        _identifier: user.identity,
        "display_name": user.display_name,
    }


def logout(request: Request):
    assert "session" in request.scope, "No Session Middleware Installed"
    del request.session[_session_key]


class SessionAuthBackend(AuthenticationBackend):
    """
    Session-based authentication backend that integrates with the framework's
    built-in session manager (req.session).

    This backend checks for authenticated user data in the existing session.
    """

    def __init__(self, session_key: str = "user", identifier: str = "id"):
        """
        Initialize the session auth backend.

        Args:
            user_key (str): The key used to store user data in the session (default: "user")
        """
        global _session_key
        global _identifier
        _session_key = session_key
        self.key = session_key
        _identifier = identifier

    async def authenticate(self, request: Request, response: Response) -> Any:
        """
        Authenticate the user using the framework's session.

        Args:
            request: The HTTP request containing the session
            response: The HTTP response (unused in this backend)

        Raises:
            AuthenticationError: If the user is not authenticated
        Returns:
            AuthResult: An authenticated user object if authentication succeeds.
        """
        assert "session" in request.scope, "No Session Middleware Installed"
        user = request.session.get(_session_key)
        if not user:
            return AuthResult(success=False, identity="", scope="")

        return AuthResult(
            success=True, identity=user.get(_identifier, ""), scope="session"
        )
