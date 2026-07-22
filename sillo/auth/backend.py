from __future__ import annotations

from typing import TYPE_CHECKING

from sillo import logging
from sillo.auth.model import AuthResult

if TYPE_CHECKING:
    from sillo.core.http import Request, Response

logger = logging.create_logger(__name__)


class AuthenticationBackend:
    """Base class for all authentication backends in the sillo framework.

    A backend reads a credential from a request and, on success, returns an
    :class:`~sillo.auth.model.AuthResult` carrying the resolved ``identity``
    (a string) and a ``scope`` string (e.g. ``"jwt"``, ``"session"``,
    ``"apikey"``). ``AuthenticationMiddleware`` and ``useAuth`` turn that
    identity into ``request.user`` via ``user_model.load_user``.

    Subclasses must implement :meth:`authenticate`. The default
    :meth:`handle_exception` logs backend failures so the middleware/route gate
    can try the next backend.

    This class is not intended to be instantiated directly. Instead, subclass
    it and provide a concrete ``authenticate`` implementation that extracts
    credentials from the incoming request (headers, cookies, session data, etc.)
    and returns an ``AuthResult`` indicating success or failure.

    Attributes:
        None. Subclasses may define their own attributes for configuration
        such as header names, secret keys, or database references.

    Example:
        Subclass this backend to implement custom authentication logic::

            class MyBackend(AuthenticationBackend):
                async def authenticate(self, request):
                    token = request.headers.get("X-Custom-Token")
                    if token:
                        return AuthResult(success=True, identity=token, scope="custom")
                    return AuthResult(success=False, identity="", scope="")
    """

    async def authenticate(self, request: "Request") -> AuthResult:
        """Resolve the caller's identity from the incoming HTTP request.

        Subclasses must override this method to extract credentials from the
        request (e.g. headers, cookies, query parameters) and attempt to
        authenticate the caller. On success, return an ``AuthResult`` with
        ``success=True`` and the resolved identity string. On failure, return
        ``AuthResult(success=False, identity="", scope="")`` so the next
        backend in the chain gets a chance to authenticate.

        Args:
            request: The incoming HTTP request object. Contains headers,
                cookies, session data, and other request-scoped information
                that backends use to extract credentials.

        Returns:
            AuthResult: An authentication result containing ``success`` (bool),
                ``identity`` (str — the user identifier on success), and
                ``scope`` (str — the authentication method label, e.g.
                ``"jwt"``, ``"session"``, ``"apikey"``).

        Raises:
            NotImplementedError: If the subclass does not override this method.
            Exception: Subclasses may raise arbitrary exceptions during
                credential verification. These are caught by
                ``AuthenticationMiddleware`` and passed to ``handle_exception``.

        Example:
            A minimal implementation that reads a token from a header::

                async def authenticate(self, request):
                    token = request.headers.get("Authorization")
                    if token:
                        return AuthResult(success=True, identity=token, scope="custom")
                    return AuthResult(success=False, identity="", scope="")
        """
        raise NotImplementedError(
            f"{type(self).__name__} must implement authenticate()"
        )

    def handle_exception(self, response: "Response", exc: Exception) -> None:
        """Handle exceptions raised during the authenticate phase.

        Called by the middleware or route gate when :meth:`authenticate` raises
        an unexpected exception. The default implementation logs the error at
        WARNING level so the caller can continue to the next backend. Override
        this method to customise error handling — for example, to short-circuit
        with a 401 response, emit metrics, or notify an operations channel.

        Args:
            response: The outgoing HTTP response object. Implementations may
                write directly to the response to short-circuit the request
                pipeline (e.g. setting status codes or JSON error bodies).
            exc: The exception instance that was raised during authentication.
                Inspect ``type(exc)`` or ``str(exc)`` to decide how to react.

        Returns:
            None. This method operates by side-effect on the response object
                and/or the logger. It does not return a value.

        Raises:
            No exceptions are raised by the default implementation. Subclasses
                may re-raise or raise new exceptions if they need to propagate
                errors to higher layers.

        Note:
            The default implementation only logs; it does not modify the
            response. The calling middleware will continue to the next backend
            after this method returns.
        """
        logger.warning("Auth backend %s failed: %s", type(self).__name__, exc)
