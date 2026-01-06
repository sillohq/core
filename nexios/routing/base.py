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
        raise NotImplementedError("Subclasses must implement this method")

    def build_middleware_stack(self, app: ASGIApp) -> ASGIApp:
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
        raise NotImplementedError("Subclasses must implement this method")

    @abstractmethod
    def url_path_for(self, _name: str, **path_params: Dict[str, Any]) -> URLPath:
        raise NotImplementedError("Subclasses must implement this method")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        raise NotImplementedError("Subclasses must implement this method")
