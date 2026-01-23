from __future__ import annotations

import typing

from typing_extensions import Annotated, Doc

from nexios import logging
from nexios.auth.backends.base import AuthenticationBackend
from nexios.auth.users.simple import BaseUser, UnauthenticatedUser,SimpleUser
from nexios.http import Request, Response
from nexios.middleware.base import BaseMiddleware

logger = logging.create_logger(__name__)


class AuthenticationMiddleware(BaseMiddleware):
    """
    Middleware responsible for handling user authentication.

    This middleware intercepts incoming HTTP requests, processes them through one or more
    authentication backends, and attaches the authenticated user to the request scope.
    Processing stops at the first backend that successfully authenticates the user.

    Attributes:
        backends (list[AuthenticationBackend]): List of authentication backends to try.
    """

    def __init__(
        self,
        user_model: Annotated[  
            type[BaseUser],
            Doc("The user model to use for authentication."),
        ] = SimpleUser, 
        backend: Annotated[
            typing.Union[AuthenticationBackend, typing.List[AuthenticationBackend]],
            Doc("Single backend or list of backends to use for authentication."),
        ] = None,
    ) -> None:
        """
        Initialize the authentication middleware with one or more backends.

        Args:
            backends: Single backend or list of backends to use for authentication.
                     Each backend will be tried in order until one successfully
                     authenticates the user or all backends are exhausted.
        """
        if not isinstance(backend, list):
            self.backends = [backend]
        else:
            self.backends = backend
        self.user_model = user_model

    async def process_request(
        self,
        request: Annotated[
            Request,
            Doc("The HTTP request object, containing authentication credentials."),
        ],
        response: Annotated[
            Response,
            Doc(
                "The HTTP response object, which may be modified during authentication."
            ),
        ],
        call_next: typing.Callable[..., typing.Awaitable[typing.Any]],
    ) -> None:
        """
        Process an incoming request through all authentication backends until one succeeds.

        This method iterates through each backend in order, attempting to authenticate
        the request. If a backend successfully authenticates the user, the user and
        authentication method are stored in the request scope and processing stops.
        If no backend authenticates the user, an unauthenticated user is set.

        Args:
            request: The incoming HTTP request.
            response: The HTTP response that will be sent.
            call_next: The next middleware or route handler in the chain.
        """
        # Try each backend until one successfully authenticates the user
        for backend in self.backends:
            try:
                auth_result = await backend.authenticate(request, response)

                if auth_result.success:
                    # Authentication successful, store user and auth type
                    request.scope["user"] = await self.user_model.load_user(
                        auth_result.identity
                    )
                    request.scope["auth"] = auth_result.scope
                    break

            except Exception as e:
                # Log the error but continue to the next backend
                backend.handle_exception(response, e)
                continue
        else:
            # No backend authenticated the user
            request.scope["user"] = UnauthenticatedUser()
            request.scope["auth"] = None

        await call_next()
