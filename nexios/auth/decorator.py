import inspect
import typing
from functools import wraps

from nexios.decorator_helper import RouteDecorator
from nexios.http import Request, Response

from .exceptions import AuthenticationFailed, PermissionDenied


class auth(RouteDecorator):
    def __init__(self, scopes: typing.Union[str, typing.List[str], None] = None):
        super().__init__()
        if isinstance(scopes, str):
            self.scopes = [scopes]
        elif scopes is None:
            self.scopes = []  # Allow authentication with any scope
        else:
            self.scopes = scopes

    def __call__(
        self,
        handler: typing.Union[
            typing.Callable[..., typing.Any],
            typing.Callable[..., typing.Awaitable[typing.Any]],
        ],
    ) -> typing.Any:
        if getattr(handler, "_is_wrapped", False):
            return handler

        @wraps(handler)  # type: ignore
        async def wrapper(
            *args: typing.List[typing.Any], **kwargs: typing.Dict[str, typing.Any]
        ) -> typing.Any:
            request, response, *_ = kwargs.values()

            if not isinstance(request, Request) or not isinstance(response, Response):
                raise TypeError("Expected request and response as the fist arguments")

            if not request.scope.get("user"):
                raise AuthenticationFailed

            scopes = request.scope.get("auth")  # type: ignore
            if not scopes:  # pragma: no cover
                raise AuthenticationFailed
            for scope in self.scopes:
                if scope not in self.scopes:
                    raise AuthenticationFailed

            if inspect.iscoroutinefunction(handler):
                return await handler(*args, **kwargs)
            return handler(*args, **kwargs)

        wrapper._is_wrapped = True  # type: ignore
        return wrapper


class has_permission(RouteDecorator):
    def __init__(self, permissions: typing.Union[str, typing.List[str], None] = None):
        super().__init__()
        if isinstance(permissions, str):
            self.permissions = [permissions]
        elif permissions is None:
            self.permissions = []  # Allow authentication with any scope
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

        @wraps(handler)  # type: ignore
        async def wrapper(
            *args: typing.List[typing.Any], **kwargs: typing.Dict[str, typing.Any]
        ) -> typing.Any:
            request, response, *_ = kwargs.values()

            if not isinstance(request, Request) or not isinstance(response, Response):
                raise TypeError("Expected request and response as the fist arguments")

            if not request.scope.get("user"):
                raise AuthenticationFailed

            user = request.user
            for permission in self.permissions:
                if user is None or not user.has_permission(permission):
                    raise PermissionDenied

            if inspect.iscoroutinefunction(handler):
                return await handler(*args, **kwargs)
            return handler(*args, **kwargs)

        wrapper._is_wrapped = True  # type: ignore
        return wrapper
