from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Optional, Union


def _ensure_bcrypt():
    try:
        import bcrypt

        return bcrypt
    except ImportError:
        raise ImportError(
            "bcrypt is required for password hashing. Install with: pip install bcrypt"
        )


def hash_password(password: str) -> str:
    bcrypt = _ensure_bcrypt()
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode(), salt).decode()


def verify_password(password: str, hashed: str) -> bool:
    bcrypt = _ensure_bcrypt()
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def needs_rehash(hashed: str, rounds: int = 12) -> bool:
    bcrypt = _ensure_bcrypt()
    try:
        current_rounds = int(hashed.split("$")[2])
        return current_rounds < rounds
    except (IndexError, ValueError):
        return True


def md5(data: Union[str, bytes]) -> str:
    if isinstance(data, str):
        data = data.encode()
    return hashlib.md5(data).hexdigest()


def sha1(data: Union[str, bytes]) -> str:
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha1(data).hexdigest()


def sha256(data: Union[str, bytes]) -> str:
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()


def sha512(data: Union[str, bytes]) -> str:
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha512(data).hexdigest()


def digest(data: Union[str, bytes], algorithm: str = "sha256") -> str:
    if isinstance(data, str):
        data = data.encode()
    h = hashlib.new(algorithm)
    h.update(data)
    return h.hexdigest()


def hmac_digest(
    key: Union[str, bytes],
    data: Union[str, bytes],
    algorithm: str = "sha256",
) -> str:
    if isinstance(key, str):
        key = key.encode()
    if isinstance(data, str):
        data = data.encode()
    return hmac.new(key, data, algorithm).hexdigest()


def constant_time_compare(a: Union[str, bytes], b: Union[str, bytes]) -> bool:
    if isinstance(a, str):
        a = a.encode()
    if isinstance(b, str):
        b = b.encode()
    return hmac.compare_digest(a, b)


def hash_file(path: str, algorithm: str = "sha256", chunk_size: int = 65536) -> str:
    h = hashlib.new(algorithm)
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def random_salt(length: int = 16) -> str:
    return secrets.token_hex(length)
