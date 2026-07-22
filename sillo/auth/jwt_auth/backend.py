from __future__ import annotations

from typing import Any, Optional

from sillo.auth.backend import AuthenticationBackend
from sillo.auth.jwt_auth.models import TokenBlacklist
from sillo.auth.model import AuthResult
from sillo.helpers import jwt as jwt_helpers
from sillo.core.http import Request


def _decode_jwt(token: str, secret: str) -> dict:
    """Decode and verify a JWT token using the HS256 algorithm.

    Internal helper that wraps the project's JWT decode function and
    translates library-specific exceptions into :class:`ValueError` for
    consistent error handling within the authentication backend.

    Args:
        token: The compact JWT string to decode and verify.
        secret: The symmetric secret key used to verify the token signature.

    Returns:
        A dictionary of decoded claims extracted from the token payload.

    Raises:
        ValueError: With message ``"Token has expired"`` if the ``exp`` claim
            is in the past, or ``"Invalid token"`` if the signature is invalid
            or the token structure is malformed.
    """
    try:
        return jwt_helpers.decode(token, secret, algorithms=["HS256"])
    except jwt_helpers.ExpiredTokenError:
        raise ValueError("Token has expired")
    except jwt_helpers.InvalidTokenError_:
        raise ValueError("Invalid token")


class JWTAuthBackend(AuthenticationBackend):
    """Authentication backend that validates requests using Bearer JWT tokens.

    Extracts the ``Authorization: Bearer <token>`` header from each request,
    verifies the token signature and expiration, and optionally checks a
    token blacklist before returning an :class:`AuthResult`. This backend
    is designed to be registered with the application's authentication
    middleware pipeline.

    Attributes:
        identifier: The payload claim key used to extract the user identity.
        secret_key: The symmetric secret used to verify token signatures.
        check_blacklist: Whether revoked tokens should be rejected via the
            :class:`TokenBlacklist` model.
    """

    def __init__(
        self,
        identifier: str = "id",
        secret_key: Optional[str] = None,
        check_blacklist: bool = True,
    ):
        """Initialize the JWT authentication backend with configuration options.

        Args:
            identifier: The claim key in the JWT payload that holds the user
                identity value. Defaults to ``"id"``.
            secret_key: The symmetric secret key for verifying token signatures.
                If ``None``, :meth:`authenticate` will raise a
                :class:`RuntimeError`.
            check_blacklist: If ``True``, tokens found in the blacklist table
                are rejected even if their signature and expiration are valid.
                Defaults to ``True``.

        Returns:
            None.

        Raises:
            None.
        """
        self.identifier = identifier
        self.secret_key = secret_key
        self.check_blacklist = check_blacklist

    async def authenticate(self, request: Request) -> Any:
        """Authenticate an incoming HTTP request using a Bearer JWT token.

        Extracts the token from the ``Authorization`` header, optionally
        checks the token against the blacklist, decodes and verifies the
        JWT signature, and returns an :class:`AuthResult` indicating
        success or failure. Returns a failed result rather than raising
        for any expected authentication error (missing header, expired
        token, invalid signature).

        Args:
            request: The incoming HTTP request object containing headers
                and other request metadata.

        Returns:
            An :class:`AuthResult` with ``success=True`` and the extracted
            identity on valid tokens, or ``success=False`` with empty
            identity and scope on any failure.

        Raises:
            RuntimeError: If ``secret_key`` was not provided during
                initialization.
        """
        if not self.secret_key:
            raise RuntimeError("secret_key is required for JWTAuthBackend")

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return AuthResult(success=False, identity="", scope="")

        token = auth_header.split(" ")[1]

        if self.check_blacklist:
            if await self._is_blacklisted(token):
                return AuthResult(success=False, identity="", scope="")

        try:
            payload = _decode_jwt(token, self.secret_key)
        except ValueError:
            return AuthResult(success=False, identity="", scope="")

        return AuthResult(
            success=True,
            identity=payload.get(self.identifier, ""),
            scope="jwt",
        )

    async def _is_blacklisted(self, token: str) -> bool:
        """Check whether a token's JTI exists in the blacklist table.

        Queries the :class:`TokenBlacklist` model for a row matching the
        given token string. If the database is unavailable or the table
        does not exist, the method silently returns ``False`` so that
        authentication can proceed without blacklist enforcement.

        Args:
            token: The raw token string (or JTI) to look up in the
                blacklist table.

        Returns:
            ``True`` if the token is found in the blacklist, ``False``
            otherwise or if the database query fails for any reason.

        Raises:
            None. All exceptions from the database layer are caught and
                suppressed to ensure graceful degradation.
        """
        try:
            return await TokenBlacklist.filter(token_jti=token).exists()
        except Exception:
            return False
