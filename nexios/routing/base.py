from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from nexios.objects import URLPath
from nexios.types import ASGIApp, Receive, Scope, Send


class BaseRouter(ABC):
    """
    Base class for routers. This class should not be instantiated directly.
    Subclasses should implement the `__call__` method to handle specific routing logic.
    """

    @abstractmethod
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        raise NotImplementedError("Subclasses must implement this method")

    def add_middleware(self, middleware: Any) -> None:
        """Add middleware to the router.

        Args:
            middleware: Middleware to apply to all routes in this router.
        """
        raise NotImplementedError("Subclasses must implement this method")

    def build_middleware_stack(self, app: ASGIApp) -> ASGIApp:
        """Build the middleware stack for the given application.

        Args:
            app: The ASGI application to wrap with middleware.

        Returns:
            The ASGI application with middleware applied.
        """
        raise NotImplementedError("Subclasses must implement this method")

    def mount_router(self, app: Any): ...


class BaseRoute(ABC):
    """
    Base class for routes. This class should not be instantiated directly.
    Subclasses should implement the `matches` method to handle specific routing logic.
    """

    def __init__(
        self,
        path: str,
        methods: List[str] = [],
        name: Optional[str] = None,
        **kwargs: Dict[str, Any],
    ) -> None:
        """Initialize a base route with path, HTTP methods, and optional name.

        Args:
            path: URL path pattern for this route.
            methods: List of allowed HTTP methods (GET, POST, etc.).
            name: Optional unique identifier for URL generation.
            **kwargs: Additional route metadata.
        """
        self.path = path
        self.methods = methods
        self.name = name

    @abstractmethod
    def match(self, *args: Any, **kwargs: Any) -> Any:
        """
        Match a path against this route's pattern.

        Subclasses can implement this method with any signature that makes sense for the route type.
        The base implementation doesn't enforce any specific signature to allow for flexibility.

        Returns:
            Any: The return type is not enforced, but should be consistent with the route's needs.
        """
        raise NotImplementedError("Subclasses must implement this method")

    @abstractmethod
    async def handle(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Handle an incoming request matching this route.

        Args:
            scope: ASGI scope containing request information.
            receive: ASGI receive callable.
            send: ASGI send callable.
        """
        raise NotImplementedError("Subclasses must implement this method")

    @abstractmethod
    def url_path_for(self, name: str, **path_params: Dict[str, Any]) -> URLPath:
        """Generate a URL path for a route by name.

        Args:
            name: The name of the route to look up.
            **path_params: Path parameters to substitute in the URL.

        Returns:
            The generated URL path.
        """
        raise NotImplementedError("Subclasses must implement this method")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Handle the request by delegating to the handle method.

        Args:
            scope: ASGI scope containing request information.
            receive: ASGI receive callable.
            send: ASGI send callable.
        """
        raise NotImplementedError("Subclasses must implement this method")
