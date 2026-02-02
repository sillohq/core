import typing

from typing_extensions import Annotated, Any, Doc

from nexios.http import Request, Response


class BaseMiddleware:
    """
    Base middleware class for handling request-response processing in Nexios.

    This class provides a structure for middleware in the Nexios framework.
    It allows child classes to intercept and modify HTTP requests before they
    reach the main application logic and modify responses before they are returned
    to the client.

    Middleware classes inheriting from `BaseMiddleware` should implement:

    - `process_request()`: To inspect, modify, or reject an incoming request.
    - `process_response()`: To inspect or modify an outgoing response.

    The user can decide when to call `next()` to proceed to the next middleware or handler.
    """

    def __init__(
        self,
        **kwargs: Annotated[
            typing.Dict[typing.Any, typing.Any],
            Doc("Additional keyword arguments for middleware configuration."),
        ],
    ) -> None:
        """
        Initializes the middleware with optional keyword arguments.

        Middleware can accept configuration parameters via `kwargs`. These parameters
        can be used to modify behavior when subclassing this base class.

        Args:
            **kwargs (dict): Arbitrary keyword arguments for middleware settings.
        """
        pass

    async def __call__(
        self,
        request: Annotated[
            Request,
            Doc("The incoming HTTP request object representing the client request."),
        ],
        response: Annotated[
            Response,
            Doc("The HTTP response object that will be returned to the client."),
        ],
        call_next: Annotated[
            typing.Callable[..., typing.Awaitable[Any]],
            Doc("The next middleware function in the processing chain."),
        ],
    ) -> Any:
        """
        Handles the request-response cycle for the middleware.

        This method does the following:
        1. Calls `process_request()` to inspect or modify the request before passing it forward.
        2. Allows the user to decide when to call `next_middleware()`.
        3. Calls `process_response()` to modify the response after `next_middleware()` is called.

        Args:
            request (Request): The incoming HTTP request object.
            next_middleware (Callable[..., Awaitable[Response]]): A function representing the next middleware.

        Returns:
            Response: The final HTTP response object.
        """
        self._call_next = False

        async def wrapped_call_next() -> Any:
            self._call_next = True
            return await call_next()  # type: ignore

        await self.process_request(request, response, wrapped_call_next)
        if self._call_next:
            return await self.process_response(request, response)

    async def process_request(
        self,
        request: Annotated[
            Request, Doc("The HTTP request object that needs to be processed.")
        ],
        response: Annotated[
            Response,
            Doc("The HTTP response object that will be returned to the client."),
        ],
        call_next: Annotated[
            typing.Callable[..., typing.Awaitable[Response]],
            Doc("The next middleware or handler to call."),
        ],
    ) -> Annotated[
        Any,
        Doc("The HTTP response object returned by the next middleware or handler."),
    ]:
        """
        Hook for processing an HTTP request before passing it forward.

        Override this method in subclasses to inspect, modify, or reject requests before
        they reach the next middleware or the application logic. The user can decide when
        to call `next()` to proceed.

        Args:
            request (Request): The incoming HTTP request object.
            next (Callable[..., Awaitable[Response]]): The next middleware or handler to call.

        Returns:
            Response: The HTTP response object returned by the next middleware or handler.
        """
        return await call_next()

    async def process_response(
        self,
        request: Annotated[
            Request,
            Doc(
                "The original HTTP request object, available for context during response processing."
            ),
        ],
        response: Annotated[
            Response,
            Doc(
                "The HTTP response object that can be modified before sending to the client."
            ),
        ],
    ) -> Annotated[
        Any,
        Doc("The modified HTTP response object to be returned to the client."),
    ]:
        """
        Hook for processing an HTTP response before returning it to the client.

        Override this method in subclasses to modify response headers, content, or status codes
        before they are sent back to the client.

        Args:
            request (Request): The original HTTP request object.
            response (Response): The outgoing HTTP response object.

        Returns:
            Response: The modified HTTP response object.
        """
        # Default behavior: Return the response as is
        return response
