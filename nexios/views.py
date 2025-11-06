import logging
from typing import Any, Callable, Coroutine, Dict, List, Optional, Type

from nexios.http import Request, Response
from nexios.routing import Route as Route
from nexios.types import MiddlewareType

logger = logging.getLogger(__name__)


class APIView:
    """
    Enhanced class-based view that can be directly registered with the app or router.
    """

    middleware: List[MiddlewareType] = []

    error_handlers: Dict[
        Type[Exception],
        Callable[[Request, Response, Exception], Coroutine[Any, Any, Response]],
    ] = {}

    @classmethod
    def as_route(
        cls, path: str, methods: Optional[List[str]] = None, **kwargs: Dict[str, Any]
    ) -> Route:
        """
        Convert the APIView class into a Route that can be registered with the app or router.
        """
        if methods is None:
            methods = [
                name.lower()
                for name in {"get", "post", "put", "delete", "patch"}
                if name in cls.__dict__
            ]

        async def handler(
            req: Request, res: Response, **kwargs: Dict[str, Any]
        ) -> Response:
            instance = cls()
            return await instance.dispatch(req, res, **kwargs)

        return Route(
            path,
            handler,
            methods=methods,
            middleware=cls.middleware,
            **kwargs,  #  type: ignore
        )

    async def dispatch(
        self, req: Request, res: Response, **kwargs: Dict[str, Any]
    ) -> Response:
        """
        Dispatch the request to the appropriate handler method.
        """

        self.request = req
        self.res = res
        try:
            method = req.method.lower()
            handler = getattr(self, method, self.method_not_allowed)
            return await handler(req, res, **kwargs)
        except Exception as e:
            for exc_type, handler in self.error_handlers.items():
                if isinstance(e, exc_type):
                    return await handler(req, res, e)
            raise e

    async def method_not_allowed(self, req: Request, res: Response) -> Response:
        """
        Handle requests with unsupported HTTP methods.
        """
        return res.status(405).json({"error": "Method Not Allowed"})

    async def get(self, req: Request, res: Response) -> Response:
        """
        Handle GET requests.
        """
        return res.status(404).json({"error": "Not Found"})

    async def post(self, req: Request, res: Response) -> Response:
        """
        Handle POST requests.
        """
        return res.status(404).json({"error": "Not Found"})

    async def put(self, req: Request, res: Response) -> Response:
        """
        Handle PUT requests.
        """
        return res.status(404).json({"error": "Not Found"})

    async def delete(self, req: Request, res: Response) -> Response:
        """
        Handle DELETE requests.
        """
        return res.status(404).json({"error": "Not Found"})

    async def patch(self, req: Request, res: Response) -> Response:
        """
        Handle PATCH requests.
        """
        return res.status(404).json({"error": "Not Found"})
