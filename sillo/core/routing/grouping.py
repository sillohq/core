import re
import typing
from typing import Any

from sillo._internals._middleware import DefineMiddleware as Middleware
from sillo.exceptions import NotFoundException
from sillo.objects import URLPath
from sillo.route_builder import RouteBuilder
from sillo.types import ASGIApp, Receive, Scope, Send

from ._utils import MatchStatus, get_route_path
from .base import BaseRoute


class Group(BaseRoute):
    """A route group that prefixes all routes with a common path.

    Groups allow organizing routes under a shared path prefix and mounting
    sub-applications at specific URL paths. This is useful for modular applications
    where different features are developed separately.

    A Group acts as both a route and a container. It matches incoming request
    paths against its prefix pattern, strips the matched prefix, and delegates
    the remaining path to the underlying application or router. Middleware
    applied to a group wraps all routes within it.

    Groups can be nested to create hierarchical URL structures and support
    reverse URL generation through the ``url_path_for`` method.
    """

    def __init__(
        self,
        path: str = "",
        app: ASGIApp | None = None,
        routes: list[BaseRoute] = [],
        name: str | None = None,
        *,
        middleware: list[Middleware] = [],
    ) -> None:
        """Initialize a route group with path prefix, app, and middleware.

        Creates a new route group that will match request paths starting
        with the given prefix and delegate handling to either an existing
        ASGI application or a newly created Router built from the provided
        routes. Middleware is applied in reverse order so that the first
        middleware in the list is the outermost wrapper.

        The group compiles its path pattern using the RouteBuilder to
        support dynamic path segments and type-converted parameters in
        the prefix itself.

        Args:
            path: URL path prefix for all routes in this group. Must be
                empty or start with a forward slash.
            app: An existing ASGI app to mount at this path prefix. If
                not provided, a new Router is created from the routes.
            routes: A list of routes to include in this group. Used only
                when app is not provided.
            name: Optional name for URL generation via ``url_path_for``.
            middleware: List of middleware to apply to this group. Each
                entry is a middleware definition tuple.

        Raises:
            AssertionError: If path does not start with '/' or if neither
                app nor routes is specified.
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
        """Get all routes contained within this group's underlying application.

        Returns the list of routes from the base application if it exposes
        a ``routes`` attribute. This provides transparent access to the
        inner routes for introspection, documentation generation, and
        URL resolution without needing to know the application type.

        Returns:
            A list of BaseRoute instances managed by the underlying app.
            Returns an empty list if the app does not have a routes
            attribute.
        """
        return getattr(self._base_app, "routes", [])

    def match(self, scope: Scope) -> tuple[MatchStatus, dict[str, Any]]:
        """Match a request path against this group's URL pattern.

        Attempts to match the incoming request path against the compiled
        regex pattern for this group. When a match is found, path parameters
        are extracted and converted to their appropriate types using the
        route info convertors.

        The method also handles the residual path portion that comes after
        the group prefix, ensuring it starts with a forward slash for
        proper delegation to the underlying application.

        Args:
            scope: ASGI scope containing the request path and other
                connection metadata used for route matching.

        Returns:
            A tuple of (MatchStatus, dict) containing the match status
            and any captured path parameters. Returns MatchStatus.FULL
            with parameters on success, or MatchStatus.NONE with an
            empty dict on failure.
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
        to the mounted application. This ensures the underlying app sees
        only the path relative to the group mount point. If the mounted
        app raises a NotFoundException, the original path is restored
        before re-raising so that the parent router can continue matching.

        The root_path in the scope is also updated to reflect the group
        prefix, enabling proper URL generation within the sub-application.

        Args:
            scope: ASGI scope containing request information. The path
                and root_path keys may be modified during handling.
            receive: ASGI receive callable for reading incoming messages
                from the client connection.
            send: ASGI send callable for transmitting response messages
                back to the client.
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
        """Generate a URL path by substituting parameters into the group pattern.

        Performs reverse URL generation for routes within this group. The
        method validates that the requested name matches the group's own
        name, then substitutes the provided path parameters into the URL
        pattern using regex replacement.

        Special handling is provided for the ``path`` parameter, which is
        appended directly to the group prefix rather than replacing a
        named placeholder.

        Args:
            name: The route name to generate URL for. Must match this
                group's name attribute.
            **path_params: Parameters to substitute in the path. Keys
                correspond to parameter names in the URL pattern.

        Returns:
            The generated URL path as a URLPath object with the resolved
            path string and http protocol.

        Raises:
            ValueError: If the provided name does not match this group's
                name attribute.
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
        """Handle the request by delegating to the handle method.

        Makes the Group instance directly callable as an ASGI application.
        This enables groups to be used anywhere an ASGI app is expected,
        such as in middleware chains, test clients, or nested routing
        configurations. The method simply forwards all ASGI arguments to
        the ``handle`` method for processing.

        Args:
            scope: ASGI scope containing request information including
                path, method, headers, and query parameters.
            receive: ASGI receive callable for reading incoming messages
                from the client connection.
            send: ASGI send callable for transmitting response messages
                back to the client.

        Returns:
            The return value of the handle method, typically a coroutine
            that resolves to None when the response is complete.
        """
        return self.handle(scope, receive, send)

    def __repr__(self) -> str:
        """Return a detailed string representation of this group.

        Produces a human-readable string that includes the class name,
        path prefix, optional name, and the underlying application. This
        is useful for debugging and logging purposes, providing a quick
        overview of the group's configuration.

        Returns:
            A formatted string in the form
            ``Group(path='...', name='...', app=...)`` showing the
            key attributes of this route group.
        """
        class_name = self.__class__.__name__
        name = self.name or ""
        return f"{class_name}(path={self.path!r}, name={name!r}, app={self.app!r})"
