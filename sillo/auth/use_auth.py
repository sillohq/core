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

from sillo.auth.backend import AuthenticationBackend
from sillo.auth.exceptions import AuthenticationFailed, PermissionDenied
from sillo.users.base import UserProtocol
from sillo.users.simple import SimpleUser

if TYPE_CHECKING:
    from sillo.http import Request


class useAuth:
    """Route-level authentication and authorisation gate for the sillo framework.

    Provides a flexible, composable authentication gate that can be passed as
    the ``auth`` argument to route registration methods. Supports scope-based
    authentication method restrictions, permission-based authorisation, custom
    backend overrides, and optional (non-blocking) authentication modes.

    Unlike the legacy ``@auth()`` decorator, ``useAuth`` instances are passed
    directly to the router, keeping the handler function clean and allowing
    the framework to manage the gate lifecycle.

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

    Attributes:
        scopes: List of accepted auth scope strings for this gate.
        permissions: List of required permission strings for this gate.
        backends: Optional list of backend overrides for this route.
        user_model: User model class for loading identities.
        required: Whether authentication is mandatory for this route.

    Example:
        Use as a route-level auth gate::

            @router.get("/profile", auth=useAuth(scopes=["jwt"]))
            async def profile(request, response):
                return response.json({"user": request.user})
    """

    def __init__(
        self,
        scopes: Optional[list[str]] = None,
        permissions: Optional[list[str]] = None,
        backends: Optional[list[AuthenticationBackend]] = None,
        user_model: Optional[type[BaseUser]] = None,
        required: bool = True,
    ) -> None:
        """Initialise the authentication gate with scope, permission, and backend config.

        Stores all configuration parameters as instance attributes for use
        during request authentication. Default values are applied for
        optional parameters that are not provided.

        Args:
            scopes: List of auth scope strings accepted for this route.
                If ``None`` or empty, scope checking is skipped. Each scope
                string corresponds to a backend's scope label (e.g. ``"jwt"``).
            permissions: List of permission strings required for this route.
                If ``None`` or empty, permission checking is skipped. Each
                permission is checked via ``user.has_permission(perm)``.
            backends: Optional list of authentication backends to use instead
                of the globally configured middleware backends. When provided,
                these backends are tried in order to authenticate the request.
            user_model: User model class for loading identities when custom
                backends are provided. Defaults to ``None`` which resolves to
                ``SimpleUser`` at runtime.
            required: Whether authentication is mandatory. When ``False``,
                unauthenticated requests pass through with an
                ``UnauthenticatedUser`` on the scope. Default ``True``.

        Returns:
            None. This is a constructor that initialises the gate state.

        Raises:
            No exceptions are raised during initialisation.
        """
        self.scopes: list[str] = scopes or []
        self.permissions: list[str] = permissions or []
        self.backends: Optional[list[AuthenticationBackend]] = backends
        self.user_model: type[BaseUser] = user_model  # type: ignore[assignment]
        self.required: bool = required

    async def authenticate(self, request: "Request") -> bool:
        """Run the authentication and authorisation gate before the route handler.

        This is the main entry point called by the framework before the route
        handler executes. It optionally runs custom backends, checks that the
        user is authenticated, verifies auth scopes, and validates permissions.
        The order of checks is: backends -> authentication -> scopes -> permissions.

        Args:
            request: The incoming HTTP request object. The request scope is
                read for ``"user"`` and ``"auth"`` keys and may be modified
                if custom backends are configured and succeed.

        Returns:
            bool: Always returns ``True`` if the gate passes. This return
                value allows subclass overrides to add custom logic after
                calling ``super().authenticate(request)``.

        Raises:
            AuthenticationFailed: If no authenticated user is found and
                ``required`` is ``True``, or if scope checking fails.
            PermissionDenied: If the authenticated user does not possess
                one or more of the required permissions.
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

    def _resolve_user_model(self) -> type[UserProtocol]:
        """Resolve the user model class to use for loading authenticated identities.

        Returns the explicitly configured ``user_model`` if one was provided
        at construction time, otherwise falls back to the default ``SimpleUser``
        class. This indirection allows the gate to work with any user model
        that implements the ``UserProtocol`` interface.

        Args:
            No arguments are accepted; this method operates on instance state.

        Returns:
            type[UserProtocol]: The resolved user model class. Either the
                explicitly configured ``user_model`` or the default
                ``SimpleUser`` class.

        Raises:
            No exceptions are raised by this method.
        """
        if self.user_model is not None:
            return self.user_model
        return SimpleUser

    async def _authenticate_with_backends(self, request: "Request") -> None:
        """Authenticate the request using the gate's custom backend list.

        Iterates through the configured backends in order, attempting to
        authenticate the request with each one. On the first successful
        authentication, the resolved user and scope are written to the
        request scope and the method returns. If all backends fail and
        the gate is required, an ``AuthenticationFailed`` exception is raised.

        Backend exceptions are silently caught so that a failing backend
        does not prevent subsequent backends from being tried.

        Args:
            request: The incoming HTTP request object. On success, the
                ``"user"`` and ``"auth"`` keys in ``request.scope`` are
                set to the resolved user object and scope string.

        Returns:
            None. This method operates by side-effect on the request scope.

        Raises:
            AuthenticationFailed: If all backends fail to authenticate and
                ``self.required`` is ``True``.
        """
        user_model = self._resolve_user_model()

        for backend in self.backends:  # type: ignore[union-attr]
            try:
                result = await backend.authenticate(request)
                if result.success:
                    request.scope["user"] = await user_model.load_user(result.identity)
                    request.scope["auth"] = result.scope
                    return
            except Exception:
                continue

        if self.required:
            raise AuthenticationFailed

    def _check_scopes(self, request: "Request") -> None:
        """Verify that the request's auth scope matches the gate's required scopes.

        Reads the ``"auth"`` key from the request scope and checks that at
        least one of the gate's configured scopes is present. The auth scope
        may be either a single string or a list of strings. If no matching
        scope is found, an ``AuthenticationFailed`` exception is raised.

        Args:
            request: The incoming HTTP request object. The ``"auth"`` key
                in ``request.scope`` is read to determine the authentication
                method(s) used for this request.

        Returns:
            None. This method validates in-place and either passes silently
                or raises an exception.

        Raises:
            AuthenticationFailed: If no auth scope is present on the request,
                or if none of the gate's required scopes match the request's
                auth scope.
        """
        auth_scope = request.scope.get("auth")
        if not auth_scope:
            raise AuthenticationFailed

        user_scopes = auth_scope if isinstance(auth_scope, list) else [auth_scope]
        if not any(s in user_scopes for s in self.scopes):
            raise AuthenticationFailed
