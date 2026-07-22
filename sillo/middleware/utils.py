import re
from functools import wraps
from typing import Any, Awaitable, Callable

from sillo.core.http import Request, Response
from sillo.types import HandlerType


def use_for_route(route: str) -> Callable[[HandlerType], HandlerType]:
    """
    Creates a decorator that conditionally applies middleware to matching routes.

    This factory function generates a decorator that wraps a middleware handler
    so it only executes when the incoming request URL path matches the specified
    route pattern. The route pattern supports both exact path matching and wildcard
    suffix patterns using ``/*`` notation, which are converted to regular expressions
    for flexible URL matching.

    The decorator intelligently distinguishes between standalone async functions
    and class method handlers by inspecting the function name. If the function is
    named ``__call__``, it wraps it as a method with ``self`` as the first parameter;
    otherwise, it wraps it as a standalone handler function.

    Args:
        route (str): The URL route pattern to match against incoming requests.
            Supports exact paths like ``/api/users`` and wildcard patterns like
            ``/api/*`` which match any path under the ``/api/`` prefix.

    Returns:
        Callable[[HandlerType], HandlerType]: A decorator function that wraps the
        provided handler with route-matching logic, ensuring the middleware only
        executes for requests whose URL paths match the specified pattern.
    """
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
            """
            Wraps a standalone middleware function with route-matching logic.

            Checks whether the incoming request URL path matches the configured
            route pattern. If it matches, the middleware function is executed with
            the request, response, and call_next arguments. If it does not match,
            the request is passed directly to the next handler in the chain by
            invoking ``call_next`` without executing the middleware logic.

            Args:
                request (Request): The incoming HTTP request object containing
                    URL, headers, and other request metadata.
                response (Response): The HTTP response object that may be modified
                    or replaced by the middleware handler.
                call_next (Callable[..., Awaitable[Response]]): An async callable
                    representing the next middleware or route handler in the chain.

            Returns:
                Any: The response from the middleware handler if the route matches,
                or the response from the next handler if the route does not match.
            """
            if re.match(route, request.url.path):
                return await func(request, response, call_next)
            else:
                return await call_next()

        @wraps(func)
        async def wrapper_klass(
            self: Any,
            request: Request,
            response: Response,
            call_next: Callable[..., Awaitable[Response]],
        ) -> Any:
            """
            Wraps a class-based middleware method with route-matching logic.

            Similar to ``wrapper_func`` but designed for middleware implemented as
            class methods where the first parameter is ``self``. Checks whether the
            incoming request URL path matches the configured route pattern and either
            executes the middleware method or passes through to the next handler.

            Args:
                self (Any): The middleware class instance on which the method is
                    being invoked, providing access to instance state and configuration.
                request (Request): The incoming HTTP request object containing
                    URL, headers, and other request metadata.
                response (Response): The HTTP response object that may be modified
                    or replaced by the middleware handler.
                call_next (Callable[..., Awaitable[Response]]): An async callable
                    representing the next middleware or route handler in the chain.

            Returns:
                Any: The response from the middleware method if the route matches,
                or the response from the next handler if the route does not match.
            """
            if re.match(route, request.url.path):
                return await func(self, request, response, call_next)
            else:
                return await call_next()

        if func.__name__ == "__call__":  # ty: ignore
            return wrapper_klass
        else:
            return wrapper_func

    return decorator
