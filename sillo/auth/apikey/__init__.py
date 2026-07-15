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
