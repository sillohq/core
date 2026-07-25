"""
sillo.services.admin.auth — Authentication for the admin panel.

Provides a pluggable auth backend system.  Ships with :class:`SessionAuth`
which uses sillo's session middleware.  Bring-your-own-auth by
subclassing :class:`AuthBackend`.
"""

from __future__ import annotations

from typing import Optional

from sillo.helpers.hashing import verify_password

from .models import AdminUser


class AuthBackend:
    """Abstract authentication backend.

    Override :meth:`authenticate` and :meth:`get_user` to plug in
    your own auth system (JWT, OAuth, LDAP, etc.).
    """

    async def authenticate(self, request) -> bool:
        """Return True if the request is authenticated."""
        return True

    async def get_user(self, request) -> Optional[dict]:
        """Return the current user dict or None."""
        return {"id": "anonymous", "username": "Anonymous"}

    async def login(self, request, username: str, password: str) -> bool:
        """Attempt login. Return True on success."""
        return True

    async def logout(self, request) -> None:
        """Clear the current session."""
        pass

    @property
    def middleware(self):
        """Return a sillo middleware that enforces authentication.

        Override for custom auth middleware.
        """
        return _AuthMiddleware(self)


class SessionAuth(AuthBackend):
    """Session-based authentication using sillo's session system.

    Requires ``sillo.middleware.sessions.SessionMiddleware`` to be
    registered on the app.

    Usage::

        admin = setup_admin(app, auth_backend=SessionAuth())
    """

    def __init__(self, user_model=AdminUser):
        """Initialize with a custom user model (defaults to ``AdminUser``)."""
        self.user_model = user_model

    async def authenticate(self, request) -> bool:
        """Authenticate

        Args:
            request: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        session = getattr(request, "session", None)
        if session:
            return session.get("admin_authenticated", False)
        return False

    async def get_user(self, request) -> Optional[dict]:
        """Get User

        Args:
            request: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        session = getattr(request, "session", None)
        if session:
            # Support both the legacy admin_user key and Sillo's default session key
            return session.get("admin_user") or session.get("user")
        return None

    async def login(self, request, username: str, password: str) -> bool:
        """Authenticate against the ``AdminUser`` table with hashed passwords."""
        if not username or not password:
            return False
        # Use the configured user model
        user = await self.user_model.get_or_none(email=username)
        if user is None:
            user = await self.user_model.get_or_none(username=username)
        if user is None or not getattr(user, "is_active", True):
            return False
        # Verify password
        if not verify_password(password, getattr(user, "password", "")):
            return False

        # Use Sillo's official session authentication helper to store user identity
        from sillo.auth.session_auth import login as sillo_login

        class _UserWrapper:
            def __init__(self, u):
                self._u = u

            @property
            def identity(self):
                return str(self._u.pk)

            @property
            def display_name(self):
                # Prefer username, fall back to email
                return getattr(self._u, "username", self._u.email)

        sillo_login(request, _UserWrapper(user))
        return True


    async def logout(self, request) -> None:
        """Logout

        Args:
            request: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        session = getattr(request, "session", None)
        if session:
            session.pop("admin_authenticated", None)
            session.pop("admin_user", None)
            session.pop("user", None)

    @property
    def middleware(self):
        """Middleware

        Returns:
            [description]

        Raises:
            [description]
        """
        return _AuthMiddleware(self)


class _AuthMiddleware:
    """Middleware that enforces admin authentication."""

    def __init__(self, backend: AuthBackend):
        """Init

        Args:
            backend: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        self.backend = backend

    async def __call__(self, request, response, call_next):
        """Call

        Args:
            request: [description]
            response: [description]
            call_next: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        path = (
            request.url.path
            if hasattr(request.url, "path")
            else request.scope.get("path", "")
        )
        if not path.startswith("/admin"):
            return await call_next()
        if path.startswith("/admin/login") or path.startswith("/admin/static"):
            return await call_next()
        if not await self.backend.authenticate(request):
            return response.redirect("/admin/login/", status_code=302)
        return await call_next()
