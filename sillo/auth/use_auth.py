"""
Route-level authentication gate for sillo.

Pass a ``useAuth`` instance as the ``auth`` argument to route registration
methods instead of the ``@auth()`` decorator::

    from sillo.auth import useAuth

    @router.get("/profile", auth=useAuth())
    async def profile(request, response): ...

    @router.get("/admin", auth=useAuth(scopes=["jwt"]))
    async def admin(request, response): ...

    @router.get("/users", auth=useAuth(permissions=["read:users"]))
    async def list_users(request, response): ...

    @router.get("/internal", auth=useAuth(backends=[APIKeyAuthBackend()]))
    async def internal_api(request, response): ...

    @router.get("/feed", auth=useAuth(required=False))
    async def feed(request, response):
        user = request.user  # may be UnauthenticatedUser

Subclass to add custom logic::

    class OrgAuth(useAuth):
        def __init__(self, org_id_param: str, **kwargs):
            super().__init__(**kwargs)
            self.org_id_param = org_id_param

        async def authenticate(self, request) -> bool:
            if not await super().authenticate(request):
                return False
            return request.user.belongs_to_org(
                request.path_params[self.org_id_param]
            )
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sillo.auth.backends.base import AuthenticationBackend
from sillo.auth.exceptions import AuthenticationFailed, PermissionDenied
from sillo.users.base import AbstractBaseUser
from sillo.users.simple import SimpleUser

if TYPE_CHECKING:
    from sillo.http import Request


class useAuth:
    """Route-level authentication and authorisation gate.

    Parameters
    ----------
    scopes:
        Auth method scopes accepted for this route.  Each backend sets a
        scope string on ``request.scope["auth"]`` (e.g. ``"jwt"``,
        ``"session"``, ``"apikey"``).  If non-empty at least one listed
        scope must be present.
    permissions:
        Permission strings checked via ``user.has_permission(perm)``.
    backends:
        If provided, these replace the globally configured middleware
        backends for this route.  Successful authentication overrides
        ``request.scope["user"]`` and ``request.scope["auth"]``.
    user_model:
        User model for loading identities when *backends* are overridden.
        Defaults to :class:`sillo.auth.SimpleUser`.
    required:
        When ``False``, unauthenticated requests are allowed through with
        an :class:`UnauthenticatedUser` on the scope.  Default ``True``.
    """

    def __init__(
        self,
        scopes: Optional[list[str]] = None,
        permissions: Optional[list[str]] = None,
        backends: Optional[list[AuthenticationBackend]] = None,
        user_model: Optional[type[BaseUser]] = None,
        required: bool = True,
    ) -> None:
        self.scopes: list[str] = scopes or []
        self.permissions: list[str] = permissions or []
        self.backends: Optional[list[AuthenticationBackend]] = backends
        self.user_model: type[BaseUser] = user_model  # type: ignore[assignment]
        self.required: bool = required

    async def authenticate(self, request: "Request") -> bool:
        """Run the gate before the route handler.

        Raises :class:`AuthenticationFailed` or :class:`PermissionDenied`
        on failure when ``required`` is ``True``.
        """
        if self.backends is not None:
            await self._authenticate_with_backends(request)

        user = request.scope.get("user")
        if not user or not user.is_authenticated:
            if self.required:
                raise AuthenticationFailed
            return True

        if self.scopes:
            self._check_scopes(request)

        if self.permissions:
            for perm in self.permissions:
                if not user.has_permission(perm):
                    raise PermissionDenied

        return True

    def _resolve_user_model(self) -> type[AbstractBaseUser]:
        if self.user_model is not None:
            return self.user_model
        return SimpleUser

    async def _authenticate_with_backends(self, request: "Request") -> None:
        user_model = self._resolve_user_model()

        for backend in self.backends:  # type: ignore[union-attr]
            try:
                result = await backend.authenticate(request)
                if result.success:
                    request.scope["user"] = await user_model.load_user(
                        result.identity
                    )
                    request.scope["auth"] = result.scope
                    return
            except Exception:
                continue

        if self.required:
            raise AuthenticationFailed

    def _check_scopes(self, request: "Request") -> None:
        auth_scope = request.scope.get("auth")
        if not auth_scope:
            raise AuthenticationFailed

        user_scopes = auth_scope if isinstance(auth_scope, list) else [auth_scope]
        if not any(s in user_scopes for s in self.scopes):
            raise AuthenticationFailed
