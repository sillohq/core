"""Session authentication backend implementation.

Provides the core session-based authentication mechanism including the
``login`` and ``logout`` helper functions and the ``SessionAuthBackend``
class that integrates with the framework's authentication system. Session
authentication stores user identity in a server-side session and validates
it on each incoming request.
"""

from __future__ import annotations

from typing import Any

from sillo.auth.backend import AuthenticationBackend
from sillo.auth.model import AuthResult
from sillo.http import Request

DEFAULT_SESSION_KEY = "user"
DEFAULT_IDENTIFIER = "id"


def login(
    request: Request,
    user,
    session_key: str = DEFAULT_SESSION_KEY,
    identifier: str = DEFAULT_IDENTIFIER,
):
    """Authenticate a user by storing their identity in the request session.

    Writes the user's identity and display name into the server-side session
    associated with the current request. If a previous session entry exists
    under the same key, it is removed before writing the new entry to ensure
    a clean state. This function requires the session middleware to be
    installed in the application middleware stack.

    Args:
        request: The current HTTP request object. Must have a 'session'
            key in its scope, which is provided by the session middleware.
        user: The user object to log in. Must have ``identity`` and
            ``display_name`` properties that return the user's unique
            identifier and human-readable name respectively.
        session_key: The key under which user data is stored in the session
            dictionary. Defaults to 'user'. Allows multiple authentication
            contexts to coexist in the same session if needed.
        identifier: The key used to store the user's identity value within
            the session user data dictionary. Defaults to 'id'. This value
            is later used by ``SessionAuthBackend`` to extract the identity.

    Returns:
        None: This function does not return a value. The user data is
            written directly into the request's session dictionary.

    Raises:
        AssertionError: If the request does not have a session in its scope,
            indicating that the session middleware has not been installed.
    """
    assert "session" in request.scope, "No Session Middleware Installed"
    if request.session.get(session_key):
        del request.session[session_key]
    request.session[session_key] = {
        identifier: user.identity,
        "display_name": user.display_name,
    }


def logout(request: Request, session_key: str = DEFAULT_SESSION_KEY):
    """Terminate a user's session by removing their data from the session.

    Removes the user data entry from the server-side session associated with
    the current request, effectively logging the user out. After this call,
    subsequent requests will not contain any authenticated user information
    under the specified session key. This function requires the session
    middleware to be installed in the application middleware stack.

    Args:
        request: The current HTTP request object. Must have a 'session'
            key in its scope, which is provided by the session middleware.
        session_key: The key identifying the user data to remove from the
            session dictionary. Defaults to 'user'. Must match the key
            used during the corresponding ``login`` call.

    Returns:
        None: This function does not return a value. The user data is
            removed directly from the request's session dictionary.

    Raises:
        AssertionError: If the request does not have a session in its scope,
            indicating that the session middleware has not been installed.
    """
    assert "session" in request.scope, "No Session Middleware Installed"
    del request.session[session_key]


class SessionAuthBackend(AuthenticationBackend):
    """Authentication backend that validates users via server-side sessions.

    Implements the ``AuthenticationBackend`` interface by reading user identity
    from the request's session data. When a user logs in via the ``login``
    helper, their identity is stored in the session. This backend extracts
    that identity on each request to produce an ``AuthResult`` indicating
    whether the request is authenticated.

    Attributes:
        session_key: The session dictionary key where user data is stored.
        identifier: The key within the user data dict holding the identity.
    """

    def __init__(
        self,
        session_key: str = DEFAULT_SESSION_KEY,
        identifier: str = DEFAULT_IDENTIFIER,
    ):
        """Initialize the session authentication backend with key configuration.

        Configures which session keys this backend will use to locate and
        extract user identity information from the request session. These
        values must match those used in the corresponding ``login`` call
        to ensure consistent session data access.

        Args:
            session_key: The key under which user data is stored in the
                session dictionary. Defaults to 'user'. Must match the
                session_key used in the ``login`` function.
            identifier: The key within the stored user data dictionary that
                holds the user's identity value. Defaults to 'id'. Must
                match the identifier used in the ``login`` function.

        Returns:
            None: This constructor does not return a value.
        """
        self.session_key = session_key
        self.identifier = identifier

    async def authenticate(self, request: Request) -> Any:
        """Authenticate the current request by checking session data.

        Reads the user data from the request's session using the configured
        session key. If user data is found, returns a successful ``AuthResult``
        with the user's identity and 'session' as the authentication scope.
        If no user data is present, returns an unsuccessful ``AuthResult``
        with empty identity and scope fields.

        Args:
            request: The current HTTP request object. Must have a 'session'
                key in its scope, which is provided by the session middleware.

        Returns:
            Any: An ``AuthResult`` instance. On success, ``success`` is True,
                ``identity`` contains the user's identifier string, and
                ``scope`` is 'session'. On failure, ``success`` is False
                with empty strings for identity and scope.

        Raises:
            AssertionError: If the request does not have a session in its
                scope, indicating that the session middleware has not been
                installed in the application middleware stack.
        """
        assert "session" in request.scope, "No Session Middleware Installed"
        user = request.session.get(self.session_key)

        if not user:
            return AuthResult(success=False, identity="", scope="")

        return AuthResult(
            success=True, identity=user.get(self.identifier, ""), scope="session"
        )
