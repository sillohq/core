from __future__ import annotations

import base64
import hashlib
import hmac as _hmac
import secrets
from typing import Optional, Tuple

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2

    _crypto_available = True
except ImportError:
    _crypto_available = False
    Fernet = None  # type: ignore
    PBKDF2 = None  # type: ignore
    hashes = None  # type: ignore


def _ensure_crypto():
    if not _crypto_available:
        raise ImportError(
            "cryptography is required for encryption. Install with: pip install cryptography"
        )


def generate_key() -> bytes:
    _ensure_crypto()
    return Fernet.generate_key()


def encrypt(value: str, key: bytes) -> str:
    _ensure_crypto()
    f = Fernet(key)
    return f.encrypt(value.encode()).decode()


def decrypt(token: str, key: bytes) -> str:
    _ensure_crypto()
    f = Fernet(key)
    return f.decrypt(token.encode()).decode()


def derive_key(
    password: str,
    salt: Optional[bytes] = None,
    length: int = 32,
    iterations: int = 600_000,
) -> Tuple[bytes, bytes]:
    _ensure_crypto()
    if salt is None:
        salt = secrets.token_bytes(16)
    kdf = PBKDF2(
        algorithm=hashes.SHA256(),
        length=length,
        salt=salt,
        iterations=iterations,
    )
    key = kdf.derive(password.encode())
    return key, salt


def sign_value(value: str, secret: str, algorithm: str = "sha256") -> str:
    if isinstance(secret, str):
        secret = secret.encode()
    if isinstance(value, str):
        value = value.encode()

    signature = _hmac.new(secret, value, algorithm).hexdigest()
    payload = base64.urlsafe_b64encode(value).decode().rstrip("=")
    return f"{payload}.{signature}"


def unsign_value(
    signed: str, secret: str, algorithm: str = "sha256", max_age: Optional[int] = None
) -> str:
    if isinstance(secret, str):
        secret = secret.encode()

    try:
        payload_b64, _, signature = signed.rpartition(".")
        value = base64.urlsafe_b64decode(payload_b64 + "==").decode()

        expected = _hmac.new(secret, value.encode(), algorithm).hexdigest()
        if not _hmac.compare_digest(expected, signature):
            raise BadSignature("Invalid signature")
    except Exception:
        raise BadSignature("Invalid signed value")

    return value


class BadSignature(Exception):
    pass
