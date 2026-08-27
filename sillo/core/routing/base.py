from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from sillo.objects import URLPath
from sillo.types import ASGIApp, Receive, Scope, Send


class BaseRouter(ABC):
    """Base class for all router implementations in the sillo framework.

    This abstract base class defines the core interface that every router
    must implement. It establishes the contract for handling ASGI requests,
    applying middleware, and mounting sub-routers. Concrete subclasses must
    provide implementations for all abstract methods defined here.

    The class is designed to be subclassed rather than instantiated directly.
    It serves as the foundation for the main Router class and any custom
    routing implementations that integrate with the framework.

    Subclasses should implement the ``__call__`` method to handle specific
    routing logic and dispatch requests to the appropriate handlers.
    """

    @abstractmethod
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Handle an incoming ASGI request by dispatching to the routing logic.

        This abstract method defines the primary ASGI callable interface that
        all router subclasses must implement. It receives the standard ASGI
        triple of scope, receive, and send callables and is responsible for
        matching the request to an appropriate route and invoking its handler.

        Args:
            scope: The ASGI connection scope dictionary containing request
                metadata such as path, method, headers, and query parameters.
            receive: An awaitable callable that yields ASGI message dicts
                from the client connection as they arrive.
            send: An awaitable callable that accepts ASGI message dicts to
                transmit response data back to the client.

        Raises:
            NotImplementedError: If a subclass does not override this method.
        """
        raise NotImplementedError(
            "Subclasses must implement this method"
        )  # pragma: no cover - abstract base method

    def use(self, middleware: Any) -> None:
        """Add middleware to the router for processing incoming requests.

        Registers a middleware component that will be applied to all routes
        managed by this router. Middleware is executed in the order it is
        added, wrapping around the route handler in an onion-style pattern.

        This method serves as the primary extension point for adding cross-
        cutting concerns such as authentication, logging, CORS handling,
        and request/response transformation to the routing pipeline.

        Args:
            middleware: Middleware to apply to all routes in this router.
                Can be a callable, a class, or a middleware definition
                tuple depending on the router implementation.

        Raises:
            NotImplementedError: If a subclass does not override this method.
        """
        raise NotImplementedError(
            "Subclasses must implement this method"
        )  # pragma: no cover - abstract base method

    def build_middleware_stack(self, app: ASGIApp) -> ASGIApp:
        """Build the middleware stack for the given ASGI application.

        Constructs the full middleware chain by wrapping the provided ASGI
        application with all registered middleware components. The middleware
        is applied in reverse order so that the first middleware added is the
        outermost wrapper in the call chain.

        This method is typically called during request dispatch to ensure
        that all middleware is properly applied before the request reaches
        the route handler.

        Args:
            app: The ASGI application to wrap with middleware. This is
                usually the innermost application or route handler.

        Returns:
            The ASGI application with all middleware applied, forming a
            complete middleware stack ready to process requests.

        Raises:
            NotImplementedError: If a subclass does not override this method.
        """
        raise NotImplementedError(
            "Subclasses must implement this method"
        )  # pragma: no cover - abstract base method

    def mount_router(self, app: Any):
        """Mount another ASGI application or router onto this router.

        Attaches a sub-application at a specific path prefix, allowing the
        main router to delegate requests to nested routers or standalone
        ASGI applications. This enables modular application architecture
        where different features can be developed and mounted independently.

        The mounted application will receive requests whose paths match
        the configured prefix, with the prefix stripped from the path
        before being passed to the sub-application.

        Args:
            app: The ASGI application or router instance to mount. The
                application should have a prefix attribute or be wrapped
                in a Group with a specific path.
        """


class BaseRoute(ABC):
    """Base class for all route implementations in the sillo framework.

    This abstract base class defines the core interface that every route
    must implement. It provides the fundamental attributes shared by all
    route types including path pattern, allowed HTTP methods, and an
    optional name for URL generation.

    Concrete subclasses must implement the ``match``, ``handle``, and
    ``url_path_for`` methods to provide specific routing behaviour for
    different protocol types such as HTTP and WebSocket.

    The class is designed to be subclassed rather than instantiated
    directly. It serves as the foundation for Route, WebsocketRoute,
    Group, and any custom route implementations.
    """

    def __init__(
        self,
        path: str,
        methods: list[str] = [],
        name: str | None = None,
        **kwargs: dict[str, Any],
    ) -> None:
        """Initialize a base route with path, HTTP methods, and optional name.

        Sets up the fundamental attributes that all route types share. The
        path defines the URL pattern to match against incoming requests,
        while methods restrict which HTTP verbs the route will respond to.
        An optional name enables reverse URL lookups via ``url_path_for``.

        Additional keyword arguments are accepted for forward compatibility
        and may be used by subclasses or future framework extensions.

        Args:
            path: URL path pattern for this route. Supports dynamic segments
                using curly brace syntax such as ``/users/{id}``.
            methods: List of allowed HTTP methods (GET, POST, etc.). Defaults
                to an empty list meaning no method restrictions.
            name: Optional unique identifier for URL generation. When set,
                this name can be used with ``url_path_for`` to build URLs.
            **kwargs: Additional route metadata stored for extensibility.
        """
        self.path = path
        self.methods = methods
        self.name = name

    @abstractmethod
    def match(self, *args: Any, **kwargs: Any) -> Any:
        """Match a path against this route's URL pattern.

        Determines whether an incoming request path matches the route's
        configured URL pattern and extracts any dynamic path parameters.
        The matching logic varies by route type, which is why the method
        accepts flexible arguments rather than a fixed signature.

        Subclasses can implement this method with any signature that makes
        sense for the route type. The base implementation does not enforce
        any specific signature to allow for flexibility across HTTP routes,
        WebSocket routes, and route groups.

        Args:
            *args: Positional arguments passed by the router during the
                matching phase. Typically includes the ASGI scope.
            **kwargs: Keyword arguments for additional matching context
                that may be needed by specific route implementations.

        Returns:
            A match result whose type depends on the route implementation.
            Typically a tuple of match status and captured parameters.

        Raises:
            NotImplementedError: If a subclass does not override this method.
        """
        raise NotImplementedError(
            "Subclasses must implement this method"
        )  # pragma: no cover - abstract base method

    @abstractmethod
    async def handle(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Handle an incoming request that has been matched to this route.

        Processes the ASGI connection by performing route-specific logic
        such as invoking the handler function, running middleware, and
        sending the response back to the client. This method is called
        by the router after a successful path match has been confirmed.

        Subclasses must implement this method with the appropriate logic
        for their protocol type, whether HTTP request handling, WebSocket
        connection management, or group delegation.

        Args:
            scope: ASGI scope containing request information including
                path, method, headers, and captured path parameters.
            receive: ASGI receive callable for reading incoming messages
                from the client connection.
            send: ASGI send callable for transmitting response messages
                back to the client.

        Raises:
            NotImplementedError: If a subclass does not override this method.
        """
        raise NotImplementedError(
            "Subclasses must implement this method"
        )  # pragma: no cover - abstract base method

    @abstractmethod
    def url_path_for(self, name: str, **path_params: dict[str, Any]) -> URLPath:
        """Generate a URL path for a named route by substituting parameters.

        Performs reverse URL resolution by taking a route name and a set of
        path parameters and producing a concrete URL path. This is the
        mechanism that allows applications to generate links dynamically
        without hardcoding URL patterns throughout the codebase.

        The method validates that the provided name matches this route and
        that all required path parameters are supplied. Subclasses may add
        additional validation logic specific to their route type.

        Args:
            name: The name of the route to look up. Must match this route's
                name attribute for the lookup to succeed.
            **path_params: Path parameters to substitute in the URL pattern.
                Keys correspond to parameter names defined in the route path.

        Returns:
            The generated URL path as a URLPath object containing the
            resolved path string and protocol information.

        Raises:
            NotImplementedError: If a subclass does not override this method.
        """
        raise NotImplementedError(
            "Subclasses must implement this method"
        )  # pragma: no cover - abstract base method

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Handle the request by delegating to the handle method.

        Makes the route instance directly callable as an ASGI application.
        This method delegates to the ``handle`` method, providing a uniform
        interface that allows routes to be used anywhere an ASGI app is
        expected, such as in middleware chains or test clients.

        Subclasses should override this method or the ``handle`` method to
        implement their specific request processing logic.

        Args:
            scope: ASGI scope containing request information including
                path, method, headers, and query parameters.
            receive: ASGI receive callable for reading incoming messages
                from the client connection.
            send: ASGI send callable for transmitting response messages
                back to the client.

        Raises:
            NotImplementedError: If a subclass does not override this method.
        """
        raise NotImplementedError(
            "Subclasses must implement this method"
        )  # pragma: no cover - abstract base method
