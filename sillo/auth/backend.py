from __future__ import annotations

from typing import TYPE_CHECKING

from sillo import logging
from sillo.auth.model import AuthResult

if TYPE_CHECKING:
    from sillo.http import Request, Response

logger = logging.create_logger(__name__)


class AuthenticationBackend:
    """Base class for all authentication backends.

    A backend reads a credential from a request and, on success, returns an
    :class:`~sillo.auth.model.AuthResult` carrying the resolved ``identity``
    (a string) and a ``scope`` string (e.g. ``"jwt"``, ``"session"``,
    ``"apikey"``). ``AuthenticationMiddleware`` and ``useAuth`` turn that
    identity into ``request.user`` via ``user_model.load_user``.

    Subclasses must implement :meth:`authenticate`. The default
    :meth:`handle_exception` logs backend failures so the middleware/route gate
    can try the next backend.
    """

    async def authenticate(self, request: "Request") -> AuthResult:
        """Resolve the caller's identity from the request.

        Return ``AuthResult(success=True, identity=..., scope=...)`` to accept,
        or ``AuthResult(success=False, identity="", scope="")`` to decline so
        the next backend gets a turn.
        """
        raise NotImplementedError(
            f"{type(self).__name__} must implement authenticate()"
        )

    def handle_exception(self, response: "Response", exc: Exception) -> None:
        """Called by the middleware when :meth:`authenticate` raises.

        The default logs the error; the caller then continues to the next
        backend. Override to customize error handling (e.g. short-circuit with
        a 401 response).
        """
        logger.warning(
            "Auth backend %s failed: %s", type(self).__name__, exc
        )
