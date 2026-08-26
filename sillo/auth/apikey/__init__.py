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

verify_key = verify_api_key

__all__ = [
    "APIKeyAuthBackend",
    "ApiKey",
    "ApiKeyManager",
    "ApiKeyUserMixin",
    "generate_api_key",
    "hash_api_key",
    "verify_api_key",
]
