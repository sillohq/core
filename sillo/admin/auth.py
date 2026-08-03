"""
sillo.admin.auth — Authentication for the admin panel.

Provides a pluggable auth backend system.  Ships with :class:`SessionAuth`
which uses sillo's session middleware.  Bring-your-own-auth by
subclassing :class:`AuthBackend`.
"""

from __future__ import annotations

from typing import Optional

from .default_user import AdminUser


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

    @staticmethod
    def may_enter(user) -> bool:
        """Whether *user* is allowed into the admin.

        Being signed in is not enough. When the admin shares the
        application's user model — the ordinary arrangement, since the people
        who administer a site are usually people who use it — every registered
        account holds a session, and admitting anyone with a session would hand
        the whole database to whoever last filled in the sign-up form.

        ``is_staff`` is the flag that separates the two, exactly as
        :func:`sillo.users.commands.create_admin` sets it.
        """
        if not getattr(user, "is_active", True):
            return False
        return bool(getattr(user, "is_staff", False) or getattr(user, "is_superuser", False))

    async def current_user(self, request):
        """Load the signed-in user, if they may use the admin.

        Returns:
            The user row, or None when nobody is signed in, the account no
            longer exists, or it is not permitted here.
        """
        session = getattr(request, "session", None)
        entry = (session.get("admin_user") or session.get("user")) if session else None
        if not entry:
            return None

        identity = entry.get("id") if isinstance(entry, dict) else entry
        if identity is None:
            return None

        try:
            user = await self.user_model.load_user(identity)
        except Exception:
            # A session naming a user this model cannot load is not an error
            # to surface; it is simply not an authenticated admin request.
            return None
        if user is None or not self.may_enter(user):
            return None
        return user

    async def authenticate(self, request) -> bool:
        """Check whether the current request carries a valid admin session.

        The session is read for who is signed in, and the account itself for
        whether they are allowed in — the session carries only an identity and
        a display name, and a flag revoked after sign-in has to take effect on
        the next request rather than at the next sign-in.
        """
        return await self.current_user(request) is not None

    async def get_user(self, request) -> Optional[dict]:
        """Return the current admin user dict from the session, or None."""
        if await self.current_user(request) is None:
            return None
        session = getattr(request, "session", None)
        if session:
            return session.get("admin_user") or session.get("user")
        return None

    async def login(self, request, username: str, password: str) -> bool:
        """Authenticate against ``user_model`` via the shared user contract.

        Correct credentials are necessary but not sufficient: the account must
        also be allowed into the admin. See :meth:`may_enter`.
        """
        if not username or not password:
            return False
        user = await self.user_model.verify_credentials(username, password)
        if user is None or not self.may_enter(user):
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
