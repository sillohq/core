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

import warnings
from typing import TYPE_CHECKING, Optional, Sequence, Union

from sillo.auth.backend import AuthenticationBackend
from sillo.auth.exceptions import AuthenticationFailed, PermissionDenied
from sillo.users.base import BaseUser, UserProtocol
from sillo.users.simple import SimpleUser

if TYPE_CHECKING:
    from sillo.core.http import Request


#: What the shipped backends used to report as ``AuthResult.scope``, mapped to
#: the scheme names they now report instead. Only these three ever shipped
#: with a fixed label; a custom backend chose its own string, which stays
#: whatever it was and needs no translation.
LEGACY_SCOPE_ALIASES = {
    "jwt": "bearerAuth",
    "session": "sessionCookie",
    "apikey": "apiKeyHeader",
}


def accepted_identifiers(names: "Sequence[str]") -> set:
    """Every identifier a gate written against *names* should accept.

    Both the value as written and its modern spelling, because the two can
    legitimately arrive from different backends. A shipped ``JWTAuthBackend``
    now reports ``"bearerAuth"``, while a hand-rolled backend that returns
    ``AuthResult(scope="jwt")`` still reports ``"jwt"`` — a gate saying
    ``"jwt"`` means both, and translating instead of widening would turn one
    of them into a silent 401.

    Args:
        names: Scheme names or legacy scope labels, as written by the caller.

    Returns:
        The set of identifiers that satisfy the gate.
    """
    accepted = set(names)
    accepted.update(LEGACY_SCOPE_ALIASES.get(name, name) for name in names)
    return accepted


def request_identifiers(request: "Request") -> set:
    """The identifiers a request authenticated under.

    ``auth`` and ``auth_scheme`` hold the same value for every shipped
    backend; they differ only for a custom backend that reports a scope but
    never sets a name.
    """
    return {request.scope.get("auth_scheme"), request.scope.get("auth")}


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
    schemes:
        OpenAPI security scheme names accepted for this route, e.g.
        ``["bearerAuth", "sessionCookie"]``.  A backend reports its own
        name, so this is the single identifier for "which credential" —
        it gates the request *and* becomes the route's documented
        ``security``.  Pass a mapping to carry OAuth2 scopes:
        ``{"oauth2": ["read:widgets"]}``.
    all_of:
        Require every entry in *schemes* together rather than any one.
    permissions:
        Permission strings checked via ``user.has_permission(perm)``.
        Authorization, not authentication — OpenAPI has no field for it,
        so it never reaches the document.
    backends:
        If provided, these replace the globally configured middleware
        backends for this route.  Successful authentication overrides
        ``request.scope["user"]``, ``["auth"]`` and ``["auth_scheme"]``.
    user_model:
        User model for loading identities when *backends* are overridden.
        Defaults to :class:`sillo.auth.SimpleUser`.
    required:
        When ``False``, unauthenticated requests are allowed through with
        an :class:`UnauthenticatedUser` on the scope.  Default ``True``.
    scopes:
        **Deprecated** — the previous spelling, which matched a method
        label (``"jwt"``) rather than a scheme name.  Values are
        translated through :data:`LEGACY_SCOPE_ALIASES` and merged into
        *schemes*, with a warning naming the replacement.

    Attributes:
        schemes: ``{scheme_name: oauth_scopes}`` accepted by this gate.
        all_of: Whether every scheme is required together.
        permissions: List of required permission strings for this gate.
        backends: Optional list of backend overrides for this route.
        user_model: User model class for loading identities.
        required: Whether authentication is mandatory for this route.
        scopes: The deprecated values as passed, kept for introspection.

    Example:
        Use as a route-level auth gate::

            @router.get("/profile", auth=useAuth(schemes=["bearerAuth"]))
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
        schemes: Optional[Union[list[str], dict[str, list[str]]]] = None,
        all_of: bool = False,
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
            schemes: OpenAPI security scheme names this route accepts, e.g.
                ``["bearerAuth", "sessionCookie"]``. Unlike *scopes* these
                are the names under ``components.securitySchemes``, so the
                route's documented ``security`` is derived from them and the
                gate cannot disagree with the document. Pass a mapping to
                carry OAuth2 scopes: ``{"oauth2": ["read:widgets"]}``.
            all_of: Whether every entry in *schemes* is required together.
                ``False`` (the default) means any one will do, which OpenAPI
                writes as separate requirement objects; ``True`` means all of
                them, which OpenAPI writes as one object with several keys.

        Returns:
            None. This is a constructor that initialises the gate state.

        Raises:
            No exceptions are raised during initialisation.
        """
        self.permissions: list[str] = permissions or []
        self.backends: Optional[list[AuthenticationBackend]] = backends
        self.user_model: type[BaseUser] = user_model  # ty: ignore[invalid-assignment]
        self.required: bool = required
        # Normalised to {name: oauth_scopes} so the two accepted spellings —
        # a list of names, or a mapping carrying OAuth2 scopes — collapse to
        # one shape before anything reads them.
        self.schemes: dict[str, list[str]] = (
            {}
            if schemes is None
            else {name: [] for name in schemes}
            if isinstance(schemes, (list, tuple))
            else {name: list(value or []) for name, value in schemes.items()}
        )
        self.all_of: bool = all_of

        # `scopes` was the old spelling of the same idea, matching a method
        # label rather than a scheme name. Translating rather than ignoring it
        # is the whole point: dropping it would turn a working gate into a
        # silent 401 in production, which reads like a bad credential and not
        # like an upgrade.
        self.scopes: list[str] = list(scopes or [])
        if self.scopes:
            renamed = [LEGACY_SCOPE_ALIASES.get(scope, scope) for scope in self.scopes]
            warnings.warn(
                "useAuth(scopes=...) is deprecated; use schemes=. "
                f"Rewrite scopes={self.scopes!r} as schemes={renamed!r}.",
                DeprecationWarning,
                stacklevel=2,
            )
            for name in renamed:
                self.schemes.setdefault(name, [])

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

        # `scopes` was folded into `schemes` at construction, so there is one
        # check rather than two that could disagree.
        if self.schemes:
            self._check_schemes(request)

        if self.permissions:
            for perm in self.permissions:
                if not user.has_permission(perm):
                    raise PermissionDenied

        return True

    def security_requirements(
        self, available: Optional[Sequence[str]] = None
    ) -> Optional[list[dict[str, list[str]]]]:
        """The OpenAPI ``security`` this gate implies.

        A route declares its auth once, on the gate; this turns that into the
        document's shape so the two cannot disagree. The mapping:

        =========================================  =====================================
        Gate                                       ``security``
        =========================================  =====================================
        ``schemes=[a, b]``                         ``[{a: []}, {b: []}]``  (either)
        ``schemes=[a, b], all_of=True``            ``[{a: [], b: []}]``    (both)
        ``required=False``                         an extra ``{}`` alternative
        no ``schemes``, *available* given          every available scheme (either)
        no ``schemes``, nothing available          ``None``
        =========================================  =====================================

        Args:
            available: Scheme names the application registered. A bare
                ``useAuth()`` names nothing but still rejects anonymous
                callers, and the middleware accepts any registered backend —
                so "any of these" is what it enforces. Without this the route
                documents as public while returning 401, which is the same
                lie as an overstated requirement and the more dangerous
                direction: a consumer reads "no auth needed" and is refused.

        Returns:
            The requirement list, or ``None`` when nothing is derivable and
            the route should keep whatever it declared by hand.
        """
        schemes = self.schemes
        if not schemes and available:
            schemes = {name: [] for name in available}

        if not schemes:
            return None

        if self.all_of:
            requirements = [dict(schemes)]
        else:
            requirements = [{name: scopes} for name, scopes in schemes.items()]

        # OpenAPI spells "authentication is optional" as an empty requirement
        # object among the alternatives. Nobody writes that by hand, which is
        # why optional-auth routes are otherwise documented as mandatory.
        if not self.required:
            requirements.append({})

        return requirements

    def _check_schemes(self, request: "Request") -> None:
        """Verify the request authenticated through an accepted scheme.

        Both ``auth_scheme`` and ``auth`` are consulted. The shipped backends
        set them to the same value, so which one answers does not matter; a
        custom backend that only reports an ``AuthResult.scope`` and never
        sets ``name`` keeps working through the second.

        Args:
            request: The incoming request.

        Raises:
            AuthenticationFailed: If the scheme that authenticated is not one
                this gate accepts.
        """
        accepted = accepted_identifiers([*self.schemes, *self.scopes])
        if request_identifiers(request).isdisjoint(accepted):
            raise AuthenticationFailed

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

        for backend in self.backends:  # ty: ignore[not-iterable]
            try:
                result = await backend.authenticate(request)
                if result.success:
                    request.scope["user"] = await user_model.load_user(result.identity)
                    request.scope["auth"] = result.scope
                    request.scope["auth_scheme"] = backend.name
                    return
            except Exception:
                continue

        if self.required:
            raise AuthenticationFailed
