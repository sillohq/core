"""API key authentication sub-package for the Sillo framework.

Provides API key generation, hashing, verification, and an authentication
backend that validates keys transmitted via HTTP headers. Also includes
a user mixin for managing per-user API keys.

Attributes:
    APIKeyAuthBackend: Authentication backend for header-based API keys.
    ApiKey: Model representing a stored API key record.
    ApiKeyManager: Manager class for creating and verifying API keys.
    ApiKeyUserMixin: Mixin that adds API key management methods to users.
    generate_api_key: Generates a new API key with its hashed form.
    verify_api_key: Verifies a raw key against a stored hash.
    hash_api_key: Hashes a raw API key for secure storage.
    create_api_key: Deprecated wrapper around generate_api_key.
    verify_key: Alias for verify_api_key for backward compatibility.
"""

import warnings as _warnings

from sillo.auth.apikey.backend import APIKeyAuthBackend
from sillo.auth.apikey.mixins import ApiKeyUserMixin
from sillo.auth.apikey.models import (
    ApiKey,
    ApiKeyManager,
    generate_api_key,
    hash_api_key,
    verify_api_key,
)


def create_api_key(prefix: str = "key"):
    """Generate a new API key and return the full key with its hash.

    This function is deprecated. Callers should migrate to
    ``generate_api_key()`` which returns the full key, the raw
    secret, and the hash in a single tuple.

    Args:
        prefix: A short string prepended to the generated key to
            make it easily identifiable. Defaults to ``"key"``.

    Returns:
        tuple[str, str]: A two-element tuple containing the full
        API key string and its SHA-256 hash.

    Raises:
        DeprecationWarning: Always emitted to inform callers that
            this function is deprecated and will be removed in a
            future release.
    """
    _warnings.warn(
        "create_api_key() is deprecated, use generate_api_key() instead",
        DeprecationWarning,
        stacklevel=2,
    )
    full_key, _, key_hash = generate_api_key(prefix=prefix)
    return full_key, key_hash


verify_key = verify_api_key

__all__ = [
    "APIKeyAuthBackend",
    "ApiKey",
    "ApiKeyManager",
    "ApiKeyUserMixin",
    "generate_api_key",
    "verify_api_key",
    "hash_api_key",
]
