"""Password hashing and utilities (backward compatibility wrapper).

This module re-exports functions from sillo.hashing for backward compatibility.
New code should import directly from sillo.hashing.
"""

from __future__ import annotations

import hashlib
from typing import Union

from sillo.hashing import hash_password as _hash_password
from sillo.hashing import verify_password as _verify_password


def hash_password(password: str, scheme: str = "bcrypt") -> str:
    """Hash a password.

    Args:
        password: Plaintext password to hash.
        scheme: Hashing scheme (bcrypt, argon2, scrypt, pbkdf2_sha256).

    Returns:
        Hashed password string.
    """
    return _hash_password(password, scheme=scheme)


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a hash.

    Args:
        password: Plaintext password.
        hashed: Previously hashed password.

    Returns:
        True if password matches, False otherwise.
    """
    return _verify_password(password, hashed)


def md5(data: Union[str, bytes]) -> str:
    """Compute MD5 hash.

    Note: MD5 is not suitable for passwords. Use hash_password() instead.

    Args:
        data: Data to hash (string or bytes).

    Returns:
        MD5 hex digest.
    """
    if isinstance(data, str):
        data = data.encode()
    return hashlib.md5(data).hexdigest()


def sha256(data: Union[str, bytes]) -> str:
    """Compute SHA-256 hash.

    Note: SHA-256 is not suitable for passwords. Use hash_password() instead.

    Args:
        data: Data to hash (string or bytes).

    Returns:
        SHA-256 hex digest.
    """
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()


def sha512(data: Union[str, bytes]) -> str:
    """Compute SHA-512 hash.

    Args:
        data: Data to hash (string or bytes).

    Returns:
        SHA-512 hex digest.
    """
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha512(data).hexdigest()


def digest(data: Union[str, bytes], algorithm: str = "sha256") -> str:
    """Compute hash using specified algorithm.

    Args:
        data: Data to hash (string or bytes).
        algorithm: Hash algorithm name.

    Returns:
        Hex digest.
    """
    if isinstance(data, str):
        data = data.encode()
    h = hashlib.new(algorithm)
    h.update(data)
    return h.hexdigest()


def hash_file(path: str, algorithm: str = "sha256", chunk_size: int = 65536) -> str:
    """Compute hash of file contents.

    Args:
        path: Path to file.
        algorithm: Hash algorithm name.
        chunk_size: Bytes per iteration.

    Returns:
        Hex digest of file contents.
    """
    h = hashlib.new(algorithm)
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def random_salt(length: int = 16) -> str:
    """Generate random salt.

    Args:
        length: Number of random bytes.

    Returns:
        Hex-encoded random string.
    """
    import secrets

    return secrets.token_hex(length)
