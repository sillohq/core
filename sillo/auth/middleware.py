from __future__ import annotations

import typing

from typing_extensions import Annotated, Doc

from sillo import logging
from sillo.auth.backend import AuthenticationBackend
from sillo.users import BaseUser, SimpleUser, UnauthenticatedUser
from sillo.http import Request, Response
from sillo.middleware.base import BaseMiddleware

logger = logging.create_logger(__name__)


class AuthenticationMiddleware(BaseMiddleware):
    """Middleware responsible for handling user authentication on every request.

    This middleware intercepts incoming HTTP requests, processes them through
    one or more authentication backends, and attaches the authenticated user
    to the request scope. Processing stops at the first backend that
    successfully authenticates the user. If no backend succeeds, the request
    scope is populated with an ``UnauthenticatedUser`` instance so that
    downstream code can still access ``request.user`` safely.

    The middleware does not reject unauthenticated requests on its own — that
    is the responsibility of route-level gates (``useAuth``) or decorators
    (``@auth``). This allows some routes to be public while others require
    authentication.

    Attributes:
        backends: List of authentication backends to try in order. Each
            backend is called sequentially until one returns a successful
            ``AuthResult``.
        user_model: The user model class used to load user objects from
            resolved identity strings. Defaults to ``SimpleUser``.

    Example:
        Register the middleware with JWT and session backends::

            app.add_middleware(AuthenticationMiddleware(
                user_model=MyUser,
                backend=[JWTAuthBackend(secret_key="..."), SessionAuthBackend()],
            ))
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
        """Initialise the authentication middleware with backends and user model.

        Stores the user model class and normalises the backend argument into
        a list. If a single backend is provided it is wrapped in a list for
        uniform iteration during request processing.

        Args:
            user_model: The user model class to use for loading authenticated
                users. Must implement the ``BaseUser`` protocol including a
                ``load_user`` class method. Defaults to ``SimpleUser``.
            backend: A single ``AuthenticationBackend`` instance or a list of
                backend instances. Each backend is tried in order during
                request processing. If ``None``, an empty backend list is
                used and all requests get an ``UnauthenticatedUser``.

        Returns:
            None. This is a constructor that initialises the middleware state.

        Raises:
            No exceptions are raised during initialisation. Invalid backend
                types will surface as errors during request processing.
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
        """Process an incoming request through all authentication backends.

        Iterates through each backend in order, attempting to authenticate
        the request. If a backend successfully authenticates the user, the
        user object and authentication scope are stored in the request scope
        under the ``"user"`` and ``"auth"`` keys respectively, and processing
        stops. If no backend authenticates the user, an ``UnauthenticatedUser``
        is set on the scope so downstream code can safely access
        ``request.user`` without null checks.

        Backend exceptions are caught and passed to ``handle_exception`` for
        logging; the middleware then continues to the next backend.

        Args:
            request: The incoming HTTP request containing credentials such as
                authorization headers, cookies, or session data that backends
                use to identify the caller.
            response: The HTTP response object. Passed to backend
                ``handle_exception`` methods when a backend raises during
                authentication, allowing custom error response handling.
            call_next: An async callable representing the next middleware or
                route handler in the pipeline. Called after authentication
                processing is complete, regardless of whether a user was
                successfully authenticated.

        Returns:
            The return value of ``call_next()``, which is the result of the
                downstream middleware/handler processing chain.

        Raises:
            No exceptions are raised by this method. Backend exceptions are
                caught and handled internally. Exceptions from ``call_next``
                propagate normally to the caller.
        """
        # Try each backend until one successfully authenticates the user
        for backend in self.backends:
            try:
                auth_result = await backend.authenticate(  # ty: ignore[unresolved-attribute]
                    request
                )

                if auth_result.success:
                    # Authentication successful, store user and auth type
                    request.scope["user"] = await self.user_model.load_user(
                        auth_result.identity
                    )
                    request.scope["auth"] = auth_result.scope
                    break

            except Exception as e:
                # Log the error but continue to the next backend
                backend.handle_exception(response, e)  # ty: ignore
                continue
        else:
            # No backend authenticated the user
            request.scope["user"] = UnauthenticatedUser()
            request.scope["auth"] = None

        return await call_next()
