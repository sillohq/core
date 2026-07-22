from __future__ import annotations

import hashlib
import secrets
from typing import Any, Optional

from sillo.auth.backend import AuthenticationBackend
from sillo.auth.apikey.models import ApiKeyManager
from sillo.auth.model import AuthResult
from sillo.http import Request


class APIKeyAuthBackend(AuthenticationBackend):
    """Authentication backend that validates API keys from HTTP headers.

    Extracts an API key token from a configurable request header and
    authenticates the request either by passing the raw token through
    as the identity or by delegating verification to an ``ApiKeyManager``
    instance for database-backed validation.

    Attributes:
        header_name: The HTTP header name from which the API key is
            read on each incoming request.
        prefix: A prefix string used when generating new API keys
            associated with this backend.
        verify_with_manager: Whether to perform database-backed key
            verification via ``ApiKeyManager`` instead of accepting
            any non-empty header value.
    """

    def __init__(
        self,
        header_name: str = "X-API-Key",
        prefix: str = "key",
        verify_with_manager: bool = False,
    ):
        """Initialize the API key authentication backend.

        Configures the header name, key prefix, and verification
        strategy used during request authentication. When
        ``verify_with_manager`` is True, each request triggers a
        database lookup to validate the key; otherwise the raw
        header value is used directly as the identity.

        Args:
            header_name: Name of the HTTP header that carries the
                API key. Defaults to ``"X-API-Key"``.
            prefix: Default prefix for newly generated API keys.
                Defaults to ``"key"``.
            verify_with_manager: If True, keys are verified against
                the database via ``ApiKeyManager``. If False, any
                non-empty header value is accepted. Defaults to
                False.

        Returns:
            None: This constructor does not return a value.

        Raises:
            None: No exceptions are raised during initialization.
        """
        self.header_name = header_name
        self.prefix = prefix
        self.verify_with_manager = verify_with_manager

    async def authenticate(self, request: Request) -> Any:
        """Authenticate an incoming request using an API key header.

        Reads the API key from the configured HTTP header on the
        request. If ``verify_with_manager`` is enabled, the key is
        validated against the database through ``ApiKeyManager``
        and the associated user ID is returned as the identity.
        Otherwise the raw token value is returned as the identity
        without any database lookup.

        Args:
            request: The incoming HTTP request object containing
                headers and other request metadata. Must expose a
                ``headers`` mapping for header access.

        Returns:
            AuthResult: An authentication result indicating whether
            the request was successfully authenticated, the resolved
            identity (user ID or raw token), and the scope string
            ``"apikey"``.

        Raises:
            None: No exceptions are explicitly raised by this method.
        """
        raw_token = request.headers.get(self.header_name)

        if not raw_token:
            return AuthResult(success=False, identity="", scope="")

        if self.verify_with_manager:
            apikey = await ApiKeyManager().verify(raw_token)
            if apikey is None:
                return AuthResult(success=False, identity="", scope="")
            return AuthResult(
                success=True,
                identity=str(apikey.user_id),
                scope="apikey",
            )

        return AuthResult(success=True, identity=raw_token, scope="apikey")
