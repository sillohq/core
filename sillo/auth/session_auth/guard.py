from __future__ import annotations

from sillo.auth.session_auth.backend import (
    DEFAULT_IDENTIFIER,
    DEFAULT_SESSION_KEY,
)
from sillo.auth.session_auth.backend import (
    login as _session_login,
)
from sillo.auth.session_auth.backend import (
    logout as _session_logout,
)
from sillo.core.http import HttpContext


class SessionGuard:
    """Guard that manages user authentication state via server-side sessions.

    Provides a high-level interface for authenticating users, managing
    login and logout lifecycles, and inspecting the currently authenticated
    user from an incoming HTTP request.  All session data is read from and
    written to the request's session store through a configurable backend.

    Attributes:
        backend: The session backend instance that supplies the session key
            and identifier field names used to persist auth state.
        user_model: The ORM model class used to look up and validate user
            records during authentication attempts.
    """

    def __init__(self, backend=None, user_model=None):
        """Initialize the SessionGuard with a backend and user model.

        Configures the guard with the session backend responsible for
        reading and writing session data, and the user model used for
        credential verification and user retrieval.

        Args:
            backend: The session backend instance that provides session_key
                and identifier attributes.  Falls back to module-level
                defaults when attributes are absent.
            user_model: The ORM model class representing authenticatable
                users.  Expected to expose an ``objects`` manager with
                ``get_by_email`` and ``get_by_id`` methods.

        Returns:
            None
        """
        self.backend = backend
        self.user_model = user_model

    @property
    def _session_key(self) -> str:
        """Return the session-store key used to persist authentication data.

        Reads the ``session_key`` attribute from the configured backend.
        If the backend does not define one, the module-level default
        ``DEFAULT_SESSION_KEY`` is returned instead.

        Returns:
            str: The string key under which the authenticated user's
            identifier is stored in the request session dictionary.
        """
        return getattr(self.backend, "session_key", DEFAULT_SESSION_KEY)

    @property
    def _identifier(self) -> str:
        """Return the field name used to identify the user inside session data.

        Reads the ``identifier`` attribute from the configured backend.
        If the backend does not define one, the module-level default
        ``DEFAULT_IDENTIFIER`` is returned instead.

        Returns:
            str: The key name inside the session sub-dictionary that holds
            the unique user identifier (typically the primary key).
        """
        return getattr(self.backend, "identifier", DEFAULT_IDENTIFIER)

    async def attempt(self, request: HttpContext, **credentials) -> bool:
        """Attempt to authenticate a user with the given credentials.

        Extracts ``email`` and ``password`` from the supplied keyword
        arguments, looks up the corresponding user record, and verifies
        the password hash.  On success the user is logged in and a
        session is created on the request.

        Args:
            request: The current HTTP request object whose session store
                will be populated upon successful authentication.
            **credentials: Arbitrary keyword arguments that must include
                ``email`` (str) and ``password`` (str) for verification.

        Returns:
            bool: ``True`` if authentication succeeded and the user was
            logged in; ``False`` if credentials were missing, the user
            was not found, or the password did not match.

        Raises:
            None: All error conditions are caught internally and result
            in a ``False`` return value rather than an exception.
        """
        email = credentials.get("email")
        password = credentials.get("password")
        if not email or not password or self.user_model is None:
            return False
        user = (
            await self.user_model.objects.get_by_email(email)
            if hasattr(self.user_model, "objects")
            else None
        )
        if user is None or not user.check_password(password):
            return False
        await self.login(request, user)
        return True

    async def login(self, request: HttpContext, user) -> None:
        """Log the given user into the current request session.

        Delegates to the backend's ``login`` helper to write the user's
        identifier into the request session.  If the user model exposes
        a ``set_last_login`` method it is awaited so the last-login
        timestamp is updated.

        Args:
            request: The current HTTP request whose session dictionary
                will be mutated to store the authenticated user data.
            user: The authenticated user model instance to persist in
                the session.  Must expose an ``identity`` attribute or
                be serializable by the backend login helper.

        Returns:
            None

        Raises:
            None: Any exceptions from the backend login helper or the
            ``set_last_login`` call propagate to the caller unchanged.
        """
        _session_login(
            request, user, session_key=self._session_key, identifier=self._identifier
        )
        if hasattr(user, "set_last_login"):
            await user.set_last_login()

    async def logout(self, request: HttpContext) -> None:
        """Log the current user out by clearing the session data.

        Delegates to the backend's ``logout`` helper to remove the
        authentication entry from the request session store, effectively
        ending the user's authenticated state for this session.

        Args:
            request: The current HTTP request whose session dictionary
                will have the authentication key removed.

        Returns:
            None

        Raises:
            None: Any exceptions from the backend logout helper
            propagate to the caller unchanged.
        """
        _session_logout(request, session_key=self._session_key)

    async def user(self, request: HttpContext):
        """Retrieve the currently authenticated user from the request session.

        Reads the session store to obtain the stored user identifier,
        then queries the user model's object manager to fetch the full
        user record from the database.

        Args:
            request: The current HTTP request whose session dictionary
                is inspected for the authenticated user's identifier.

        Returns:
            The authenticated user model instance if a valid session
            exists and the user can be found, or ``None`` if no session
            is present, the identifier is missing, or the user record
            no longer exists in the database.

        Raises:
            None: All error conditions are handled internally and
            result in a ``None`` return value.
        """
        session_user = (
            request.session.get(self._session_key)
            if hasattr(request, "session")
            else None
        )
        if session_user and self.user_model:
            uid = session_user.get(self._identifier)
            if uid:
                return (
                    await self.user_model.objects.get_by_id(int(uid))
                    if hasattr(self.user_model, "objects")
                    else None
                )
        return None

    async def check(self, request: HttpContext) -> bool:
        """Check whether the current request has an active session.

        Performs a lightweight check for the presence of session data
        without loading the full user record from the database.

        Args:
            request: The current HTTP request whose session dictionary
                is inspected for the authentication session key.

        Returns:
            bool: ``True`` if the request has a session attribute and
            the session key is present with a truthy value; ``False``
            otherwise.

        Raises:
            None: Missing session attributes are handled gracefully
            and result in a ``False`` return value.
        """
        if not hasattr(request, "session"):
            return False
        return bool(request.session.get(self._session_key))

    async def id(self, request: HttpContext) -> str | None:
        """Return the raw user identifier stored in the current session.

        Reads the session store and extracts the identifier field value
        without performing a database lookup for the full user record.

        Args:
            request: The current HTTP request whose session dictionary
                is inspected for the stored user identifier.

        Returns:
            Optional[str]: The string representation of the user
            identifier if a session with a valid identifier exists,
            or ``None`` if no session data is available.

        Raises:
            None: Missing session attributes are handled gracefully
            and result in a ``None`` return value.
        """
        session_user = (
            request.session.get(self._session_key)
            if hasattr(request, "session")
            else None
        )
        return str(session_user.get(self._identifier)) if session_user else None

    async def validate(self, request: HttpContext, credentials: dict) -> bool:
        """Validate credentials without logging the user in.

        Checks the supplied email and password against the user model
        but does not create a session.  Instead, the validated user
        instance is stashed on ``request.scope["_validated_user"]``
        for downstream middleware or handlers to consume.

        Args:
            request: The current HTTP request whose scope dictionary
                will receive the ``_validated_user`` key on success.
            credentials: A dictionary that must contain ``email`` (str)
                and ``password`` (str) keys for verification against
                the stored user record.

        Returns:
            bool: ``True`` if the credentials are valid and the user
            was stored on the request scope; ``False`` if credentials
            are missing, the user was not found, or the password did
            not match.

        Raises:
            None: All error conditions are handled internally and
            result in a ``False`` return value.
        """
        email = credentials.get("email")
        password = credentials.get("password")
        if not email or not password or self.user_model is None:
            return False
        user = (
            await self.user_model.objects.get_by_email(email)
            if hasattr(self.user_model, "objects")
            else None
        )
        if user is None or not user.check_password(password):
            return False
        request.scope["_validated_user"] = user
        return True
