import re
import typing
from typing import Any

from sillo._internals._middleware import DefineMiddleware as Middleware
from sillo._internals._route_builder import RouteBuilder
from sillo.exceptions import NotFoundException
from sillo.objects import URLPath
from sillo.types import ASGIApp, Receive, Scope, Send

from ._utils import MatchStatus, get_route_path
from .base import BaseRoute


class Group(BaseRoute):
    """A route group that prefixes all routes with a common path.

    Groups allow organizing routes under a shared path prefix and mounting
    sub-applications at specific URL paths. This is useful for modular applications
    where different features are developed separately.
    """

    def __init__(
        self,
        path: str = "",
        app: typing.Optional[ASGIApp] = None,
        routes: typing.List[BaseRoute] = [],
        name: typing.Optional[str] = None,
        *,
        middleware: typing.List[Middleware] = [],
    ) -> None:
        """Initialize a route group.

        Args:
            path: URL path prefix for all routes in this group.
            app: An existing ASGI app to mount.
            routes: A list of routes to include in this group.
            name: Optional name for URL generation.
            middleware: List of middleware to apply to this group.
        """
        assert path == "" or path.startswith("/"), "Routed paths must start with '/'"
        assert app is not None or routes is not None, (
            "Either 'app=...', or 'routes=' must be specified"
        )

        self.path = path.rstrip("/")
        self.name = name
        self.raw_path = path

        if app is not None:
            self._base_app = app
        else:
            from .router import Router

            self._base_app = Router(routes=routes)

        self.app = self._base_app
        for cls, args, kwargs in reversed(middleware):
            self.app = cls(self.app, *args, **kwargs)

        self.route_info = RouteBuilder.create_pattern(
            self.path.rstrip("/") + "{path:path}"
        )
        self.pattern = self.route_info.pattern
        self.param_names = self.route_info.param_names
        self.route_type = self.route_info.route_type

    @property
    def routes(self) -> list[BaseRoute]:
        """Get all routes in this group."""
        return getattr(self._base_app, "routes", [])

    def match(self, scope: Scope) -> typing.Tuple[MatchStatus, dict[str, Any]]:
        """Match a path against this group's pattern.

        Args:
            scope: ASGI scope containing the request path.

        Returns:
            A tuple of (MatchStatus, dict) containing match status and parameters.
        """
        match = self.pattern.match(get_route_path(scope))
        if match:
            matched_params = match.groupdict()
            path_remainder = matched_params.pop("path", "")

            # Ensure the remainder path starts with /
            if path_remainder and not path_remainder.startswith("/"):
                path_remainder = "/" + path_remainder

            # Convert path parameters
            for key, value in matched_params.items():
                if value is not None:
                    matched_params[key] = self.route_info.convertor[key].convert(value)

            return MatchStatus.FULL, matched_params
        return MatchStatus.NONE, {}

    async def handle(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Handle an incoming request by delegating to the mounted app.

        Modifies the scope path to remove the group prefix before passing
        to the mounted application.

        Args:
            scope: ASGI scope containing request information.
            receive: ASGI receive callable.
            send: ASGI send callable.
        """
        original_path = scope["path"]
        matched_path = self.path.rstrip("/")

        if original_path.startswith(matched_path):
            remaining_path = original_path[len(matched_path) :] or "/"
            scope["path"] = remaining_path
            scope["root_path"] = scope.get("root_path", "") + matched_path

        try:
            await self.app(scope, receive, send)
        except NotFoundException:
            scope["path"] = original_path
            if "root_path" in scope:
                scope["root_path"] = scope["root_path"][: -len(matched_path)]
            raise

    def url_path_for(self, name: str, **path_params: typing.Any) -> URLPath:
        """Generate a URL path by substituting parameters.

        Args:
            name: The route name to generate URL for.
            **path_params: Parameters to substitute in the path.

        Returns:
            The generated URL path.
        """
        if name != self.name:
            raise ValueError(
                f"Route name '{name}' does not match the mounted route name '{self.name}'."
            )

        path = self.path.rstrip("/")
        for param_name, param_value in path_params.items():
            if param_name == "path":
                path = path + str(param_value)
            else:
                path = re.sub(rf"\{{{param_name}(:[^}}]+)?}}", str(param_value), path)

        return URLPath(path=path, protocol="http")

    def __call__(self, scope: Scope, receive: Receive, send: Send) -> typing.Any:
        """Handle the request by delegating to handle()."""
        return self.handle(scope, receive, send)

    def __repr__(self) -> str:
        """Return a string representation of this group."""
        class_name = self.__class__.__name__
        name = self.name or ""
        return f"{class_name}(path={self.path!r}, name={name!r}, app={self.app!r})"
