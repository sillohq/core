import re
import typing

from nexios._internals._middleware import DefineMiddleware as Middleware
from nexios._internals._route_builder import RouteBuilder
from nexios.exceptions import NotFoundException
from nexios.objects import URLPath
from nexios.types import ASGIApp, Receive, Scope, Send

from ._utils import MatchStatus, get_route_path
from .base import BaseRoute


class Group(BaseRoute):
    def __init__(
        self,
        path: str = "",
        app: typing.Optional[ASGIApp] = None,
        routes: typing.Optional[typing.List[BaseRoute]] = None,
        name: typing.Optional[str] = None,
        *,
        middleware: typing.List[Middleware] = [],
    ) -> None:
        assert path == "" or path.startswith("/"), "Routed paths must start with '/'"
        assert (
            app is not None or routes is not None
        ), "Either 'app=...', or 'routes=' must be specified"

        self.path = path.rstrip("/")
        self.name = name
        self.raw_path = path

        if app is not None:
            self._base_app = app
        else:
            from .router import Router

            self._base_app = Router(routes=routes)  # type:ignore

        self.app = self._base_app  # type:ignore
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
        return getattr(self._base_app, "routes", [])

    def match(self, scope: Scope) -> typing.Tuple[typing.Any, typing.Any, typing.Any]:
        """
        Match a path against this mounted route's pattern.
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

    def url_path_for(self, _name: str, **path_params: typing.Any) -> URLPath:
        """
        Generate a URL path for the mounted route.
        """
        if _name != self.name:
            raise ValueError(
                f"Route name '{_name}' does not match the mounted route name '{self.name}'."
            )

        path = self.path.rstrip("/")
        for param_name, param_value in path_params.items():
            if param_name == "path":
                path = path + str(param_value)
            else:
                path = re.sub(rf"\{{{param_name}(:[^}}]+)?}}", str(param_value), path)

        return URLPath(path=path, protocol="http")

    def __call__(self, scope: Scope, receive: Receive, send: Send) -> typing.Any:
        return self.handle(scope, receive, send)

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        name = self.name or ""
        return f"{class_name}(path={self.path!r}, name={name!r}, app={self.app!r})"
