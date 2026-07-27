"""
sillo.admin.auth — Authentication for the admin panel.

Provides a pluggable auth backend system.  Ships with :class:`SessionAuth`
which uses sillo's session middleware.  Bring-your-own-auth by
subclassing :class:`AuthBackend`.
"""

from __future__ import annotations

from typing import Optional

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

    Authenticates through :meth:`sillo.users.UserBaseModel.verify_credentials`,
    so ``user_model`` may be any subclass of
    :class:`sillo.users.UserBaseModel` — the default :class:`AdminUser`, a
    project's own extension of it, or a bare ``UserBaseModel`` subclass.

    Usage::

        admin = setup_admin(app, auth_backend=SessionAuth())
        # or, to use your own user model:
        admin = setup_admin(app, user_model=MyAdminUser)
    """

    def __init__(self, user_model=AdminUser):
        """Initialize with a custom user model (defaults to ``AdminUser``)."""
        self.user_model = user_model

    async def authenticate(self, request) -> bool:
        """Check whether the current request carries a valid admin session.

        Looks for user data stored by ``sillo.auth.session_auth.login``
        (default key ``"user"``) or the legacy ``"admin_user"`` key.
        """
        session = getattr(request, "session", None)
        if session:
            return bool(session.get("admin_user") or session.get("user"))
        return False

    async def get_user(self, request) -> Optional[dict]:
        """Return the current admin user dict from the session, or None."""
        session = getattr(request, "session", None)
        if session:
            return session.get("admin_user") or session.get("user")
        return None

    async def login(self, request, username: str, password: str) -> bool:
        """Authenticate against ``user_model`` via the shared user contract."""
        if not username or not password:
            return False
        user = await self.user_model.verify_credentials(username, password)
        if user is None:
            return False

        # Store user identity in the session using Sillo's official helper.
        from sillo.auth.session_auth import login as sillo_login

        sillo_login(request, user)
        return True

    async def logout(self, request) -> None:
        """Clear all admin-related session keys."""
        session = getattr(request, "session", None)
        if session:
            # ``Session`` exposes ``delete``, not the dict ``pop``; it already
            # tolerates a key that is not present.
            session.delete("admin_authenticated")
            session.delete("admin_user")
            session.delete("user")

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
