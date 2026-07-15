import inspect
import typing
from functools import wraps

from sillo.decorator_helper import RouteDecorator
from sillo.http import Request, Response

from .exceptions import AuthenticationFailed, PermissionDenied


class auth(RouteDecorator):
    """Legacy decorator — delegates to useAuth internally."""

    def __init__(
        self,
        scopes: typing.Union[str, typing.List[str], None] = None,
        handle_401: typing.Callable[[Request, Response], typing.Any] = None,
    ):
        super().__init__()
        self.handle_401 = handle_401
        if isinstance(scopes, str):
            self.scopes = [scopes]
        elif scopes is None:
            self.scopes = []
        else:
            self.scopes = scopes

    def _handle_401(self, request: Request, response: Response):
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

        wrapper._is_wrapped = True
        return wrapper


class has_permission(RouteDecorator):
    """Legacy decorator — delegates to useAuth internally."""

    def __init__(self, permissions: typing.Union[str, typing.List[str], None] = None):
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

        wrapper._is_wrapped = True
        return wrapper
