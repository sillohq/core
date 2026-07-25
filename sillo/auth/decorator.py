import inspect
import typing
from functools import wraps

from sillo.decorator_helper import RouteDecorator
from sillo.core.http import Request, Response

from .exceptions import AuthenticationFailed, PermissionDenied


class auth(RouteDecorator):
    """Legacy route decorator that enforces authentication on a handler.

    This decorator checks that the incoming request has been authenticated by
    the ``AuthenticationMiddleware`` and optionally verifies that the auth
    scope and permissions match the configured requirements. It delegates
    internally to the same mechanisms as :class:`useAuth` but uses the older
    decorator-based API style.

    Prefer :class:`useAuth` for new code, which can be passed as the ``auth``
    argument to route registration methods instead of wrapping the handler.

    Attributes:
        handle_401: Optional custom callback invoked when authentication fails.
            Receives the request and response objects. If not provided, an
            ``AuthenticationFailed`` exception is raised instead.
        scopes: List of auth scope strings that must be present in the
            request's ``auth`` scope for the handler to execute.

    Example:
        Apply to a route handler to require JWT authentication::

            @router.get("/profile", auth=auth(scopes=["jwt"]))
            async def profile(request, response):
                return response.json({"user": request.user})
    """

    def __init__(
        self,
        scopes: typing.Union[str, typing.List[str], None] = None,
        handle_401: typing.Callable[[Request, Response], typing.Any] = None,
    ):
        """Initialise the auth decorator with scope and error-handling config.

        Parses the ``scopes`` argument into a canonical list form and stores
        the optional 401 handler for later use when authentication fails.

        Args:
            scopes: Authentication scope(s) required for the decorated route.
                Accepts a single scope string, a list of scope strings, or
                ``None`` to skip scope checking entirely. A string is wrapped
                into a single-element list automatically.
            handle_401: Optional callable invoked when authentication fails.
                Receives ``(request, response)`` and should return a response
                or raise an exception. If ``None``, ``AuthenticationFailed``
                is raised by default.

        Returns:
            None. This is a constructor that initialises instance state.

        Raises:
            No exceptions are raised during initialisation. Type mismatches
                in ``scopes`` are silently normalised to a list.
        """
        super().__init__()
        self.handle_401 = handle_401
        if isinstance(scopes, str):
            self.scopes = [scopes]
        elif scopes is None:
            self.scopes = []
        else:
            self.scopes = scopes

    def _handle_401(self, request: Request, response: Response):
        """Dispatch the 401 authentication failure to the configured handler.

        If a custom ``handle_401`` callback was provided at construction time,
        it is called with the current request and response objects. Otherwise,
        an ``AuthenticationFailed`` exception is raised, which the framework's
        error handler converts into a 401 HTTP response.

        Args:
            request: The incoming HTTP request that failed authentication.
                Passed through to the custom handler if one is configured.
            response: The outgoing HTTP response object. The custom handler
                may write to this response to produce a custom error body.

        Returns:
            The return value of the custom ``handle_401`` callback, if one
                was configured. If no custom handler exists, this method
                does not return — it raises ``AuthenticationFailed`` instead.

        Raises:
            AuthenticationFailed: Raised when no custom ``handle_401``
                callback was provided. The framework converts this into
                an HTTP 401 response with a standard error message.
        """
        if self.handle_401:
            return self.handle_401(request, response)
        raise AuthenticationFailed

    def __call__(
        self,
        handler: typing.Union[
            typing.Callable[..., typing.Any],
            typing.Callable[..., typing.Awaitable[typing.Any]],
        ],
    ) -> typing.Any:
        """Wrap a route handler with authentication and scope checking.

        Returns a new async wrapper that validates the request has an
        authenticated user and that the auth scopes match the configured
        requirements before delegating to the original handler. If the
        handler is already wrapped (``_is_wrapped`` is truthy), it is
        returned unchanged to prevent double-wrapping.

        Args:
            handler: The route handler function to wrap. May be either a
                regular function or an async coroutine function. The first
                two positional arguments must be ``request`` and ``response``.

        Returns:
            An async wrapper function that performs authentication checks
                before calling the original handler. The wrapper has an
                ``_is_wrapped`` attribute set to ``True`` to prevent
                repeated decoration.

        Raises:
            TypeError: If the first two arguments to the wrapper are not
                ``Request`` and ``Response`` instances respectively.
            AuthenticationFailed: If no authenticated user is found on the
                request scope and no custom 401 handler is configured.
        """
        if getattr(handler, "_is_wrapped", False):
            return handler

        @wraps(handler)
        async def wrapper(
            *args: typing.List[typing.Any], **kwargs: typing.Dict[str, typing.Any]
        ) -> typing.Any:
            request, response = args[0], args[1]

            if not isinstance(request, Request) or not isinstance(response, Response):
                raise TypeError("Expected request and response as the first arguments")

            if not request.scope.get("user"):
                return self._handle_401(request, response)

            scopes = request.scope.get("auth")
            if not scopes:
                return self._handle_401(request, response)

            user_scopes = scopes if isinstance(scopes, list) else [scopes]

            for scope in self.scopes:
                if scope not in user_scopes:
                    return self._handle_401(request, response)

            if inspect.iscoroutinefunction(handler):
                return await handler(*args, **kwargs)
            return handler(*args, **kwargs)

        wrapper._is_wrapped = True  # ty: ignore[unresolved-attribute]
        return wrapper


class has_permission(RouteDecorator):
    """Legacy route decorator that enforces permission-based authorisation.

    This decorator checks that the incoming request has an authenticated user
    and that the user possesses all of the required permissions. Permissions
    are checked via ``user.has_permission(permission)`` for each permission
    string in the configured list.

    Prefer :class:`useAuth` for new code, which supports permissions through
    its ``permissions`` parameter and offers a more flexible API.

    Attributes:
        permissions: List of permission strings that the authenticated user
            must possess. Each permission is checked sequentially and all
            must pass for the handler to execute.

    Example:
        Apply to a route handler to require specific permissions::

            @router.get("/admin/users", auth=has_permission(permissions=["read:users"]))
            async def list_users(request, response):
                return response.json({"users": [...]})
    """

    def __init__(self, permissions: typing.Union[str, typing.List[str], None] = None):
        """Initialise the permission decorator with required permissions.

        Parses the ``permissions`` argument into a canonical list form for
        uniform iteration during request handling.

        Args:
            permissions: Permission string(s) required for the decorated
                route. Accepts a single permission string, a list of
                permission strings, or ``None`` to skip permission checking.
                A string is automatically wrapped into a single-element list.

        Returns:
            None. This is a constructor that initialises instance state.

        Raises:
            No exceptions are raised during initialisation. Type mismatches
                in ``permissions`` are silently normalised to a list form.
        """
        super().__init__()
        if isinstance(permissions, str):
            self.permissions = [permissions]
        elif permissions is None:
            self.permissions = []
        else:
            self.permissions = permissions

    def __call__(
        self,
        handler: typing.Union[
            typing.Callable[..., typing.Any],
            typing.Callable[..., typing.Awaitable[typing.Any]],
        ],
    ) -> typing.Any:
        """Wrap a route handler with permission-based authorisation checking.

        Returns a new async wrapper that validates the request has an
        authenticated user and that the user possesses all required permissions
        before delegating to the original handler. If the handler is already
        wrapped (``_is_wrapped`` is truthy), it is returned unchanged to
        prevent double-wrapping.

        Args:
            handler: The route handler function to wrap. May be either a
                regular function or an async coroutine function. The first
                two positional arguments must be ``request`` and ``response``.

        Returns:
            An async wrapper function that performs permission checks before
                calling the original handler. The wrapper has an
                ``_is_wrapped`` attribute set to ``True`` to prevent
                repeated decoration.

        Raises:
            TypeError: If the first two arguments to the wrapper are not
                ``Request`` and ``Response`` instances respectively.
            AuthenticationFailed: If no authenticated user is found on the
                request scope.
            PermissionDenied: If the authenticated user does not possess
                one or more of the required permissions.
        """
        if getattr(handler, "_is_wrapped", False):
            return handler

        @wraps(handler)
        async def wrapper(
            *args: typing.List[typing.Any], **kwargs: typing.Dict[str, typing.Any]
        ) -> typing.Any:
            request, response, *_ = args

            if not isinstance(request, Request) or not isinstance(response, Response):
                raise TypeError("Expected request and response as the first arguments")

            if not request.scope.get("user"):
                raise AuthenticationFailed

            user = request.user
            for permission in self.permissions:
                if user is None or not user.has_permission(permission):
                    raise PermissionDenied

            if inspect.iscoroutinefunction(handler):
                return await handler(*args, **kwargs)
            return handler(*args, **kwargs)

        wrapper._is_wrapped = True  # ty: ignore[unresolved-attribute]
        return wrapper
