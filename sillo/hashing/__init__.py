"""Password hashing with support for multiple algorithms (bcrypt, argon2, scrypt, pbkdf2).

bcrypt is handled natively. Non-bcrypt schemes require the optional
``passlib`` package: install ``sillo[hashing-all]`` or ``sillo[hashing-passlib]``.

Quick Start:

    from sillo.hashing import hash_password, verify_password

    # Hash a password (uses bcrypt by default)
    hashed = hash_password("my_password")

    # Verify a password
    if verify_password("my_password", hashed):
        print("Password is correct!")

    # Use a different algorithm
    hashed_argon2 = hash_password("my_password", scheme="argon2")

Installation:

    # Bcrypt (default, lightweight, no passlib needed)
    uv add bcrypt

    # Argon2 (most secure, requires passlib)
    uv add "sillo[hashing-argon2]"

    # All algorithms
    uv add "sillo[hashing-all]"
"""

from .core import (
    get_available_schemes_list,
    hash_password,
    is_hashed,
    needs_rehash,
    needs_update,
    set_default_scheme,
    verify_password,
)
from .exceptions import HashingError, InvalidSchemeError, VerificationError
from .utils import (
    UNUSABLE_PASSWORD_PREFIX,
    UNUSABLE_PASSWORD_SUFFIX_LENGTH,
    constant_time_compare,
    is_password_usable,
    make_unusable_password,
    md5,
    password_strength,
    sha256,
    validate_password,
)

__all__ = [
    "UNUSABLE_PASSWORD_PREFIX",
    "UNUSABLE_PASSWORD_SUFFIX_LENGTH",
    "HashingError",
    "InvalidSchemeError",
    "VerificationError",
    "constant_time_compare",
    "get_available_schemes_list",
    "hash_password",
    "is_hashed",
    "is_password_usable",
    "make_unusable_password",
    "md5",
    "needs_rehash",
    "needs_update",
    "password_strength",
    "set_default_scheme",
    "sha256",
    "validate_password",
    "verify_password",
]
