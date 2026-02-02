import re
from functools import wraps
from typing import Any, Awaitable, Callable

from nexios.http import Request, Response
from nexios.types import HandlerType


def use_for_route(route: str) -> None:
    if route.endswith("/*"):
        route = route[:-2]
        route = f"^{route}/.*$"
    else:
        route = f"^{route}$"

    def decorator(func: HandlerType) -> Any:
        @wraps(func)
        async def wrapper_func(
            request: Request,
            response: Response,
            call_next: Callable[..., Awaitable[Response]],
        ) -> Any:
            if re.match(route, request.url.path):
                return await func(request, response, call_next)  # type: ignore
            else:
                return await call_next()

        @wraps(func)
        async def wrapper_klass(
            self: Any,
            request: Request,
            response: Response,
            call_next: Callable[..., Awaitable[Response]],
        ) -> Any:
            if re.match(route, request.url.path):
                return await func(self, request, response, call_next)  # type: ignore
            else:
                return await call_next()

        if func.__name__ == "__call__":
            return wrapper_klass
        else:
            return wrapper_func

    return decorator  # type: ignore
