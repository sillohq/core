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
from sillo.core.http import Request

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

    The session identifier is rotated as part of logging in, so the key the
    visitor arrived with stops being valid and the response carries a new
    cookie. See :meth:`sillo.session.session_objects.Session.cycle_key`.

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
    session = request.session  # ty: ignore[unresolved-attribute]

    if session.get(session_key):
        del session[session_key]

    # The identifier a session carried before it was authenticated must not
    # survive the login. An attacker who fixes a session key in the victim's
    # browser beforehand — and who therefore knows it — would otherwise hold a
    # key that is authenticated the moment the victim signs in, without ever
    # having to steal a cookie.
    session.cycle_key()

    session[session_key] = {
        identifier: user.identity,
        "display_name": user.display_name,
    }


def logout(request: Request, session_key: str = DEFAULT_SESSION_KEY):
    """Terminate a user's session, emptying it.

    The whole session goes, not only the entry *session_key* names: a
    server-side store is told to purge its record and the browser is sent an
    expired cookie, so the identifier the visitor logged out of stops being
    usable by anyone still holding it. Anything else the session carried —
    a cart, flash messages — goes with it, which is the point rather than a
    side effect.

    This function requires the session middleware to be installed in the
    application middleware stack.

    Args:
        request: The current HTTP request object. Must have a 'session'
            key in its scope, which is provided by the session middleware.
        session_key: Accepted so that a call written against the older
            behaviour keeps working. It no longer selects what is removed,
            because everything is.

    Returns:
        None: This function does not return a value.

    Raises:
        AssertionError: If the request does not have a session in its scope,
            indicating that the session middleware has not been installed.
    """
    assert "session" in request.scope, "No Session Middleware Installed"
    request.session.clear()  # ty: ignore[unresolved-attribute]


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

    name = "sessionCookie"

    def describe(self):
        """Document this backend as the session cookie it rides on.

        The credential is not read from the cookie directly — the session
        middleware has already turned it into ``request.session`` — but the
        cookie is what a caller must send, and that is what the document has
        to describe.
        """
        from sillo.openapi.models import APIKey

        return APIKey(
            type="apiKey",
            name=self.cookie_name,
            description=self.description,
            # `in` is a keyword, so the field can only be reached through a
            # spread — which drops the Literal. `populate_by_name` is off on
            # these models, so `in_=` fails at runtime.
            **{"in": "cookie"},  # ty: ignore[invalid-argument-type]
        )

    def __init__(
        self,
        session_key: str = DEFAULT_SESSION_KEY,
        identifier: str = DEFAULT_IDENTIFIER,
        cookie_name: str = "session_id",
        name: str | None = None,
        description: str | None = None,
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
        # Must match SessionConfig.session_cookie_name, or the document names
        # a cookie the application never sets.
        self.cookie_name = cookie_name
        if name is not None:
            self.name = name
        self.description = description

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
            success=True, identity=user.get(self.identifier, ""), scope=self.name
        )
