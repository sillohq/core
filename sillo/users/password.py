from __future__ import annotations

import hashlib
import re
import secrets
from typing import Optional

UNUSABLE_PASSWORD_PREFIX = "!"
UNUSABLE_PASSWORD_SUFFIX_LENGTH = 40


def _ensure_bcrypt():
    try:
        import bcrypt

        return bcrypt
    except ImportError:
        raise ImportError(
            "bcrypt is required for password hashing. Install with: pip install bcrypt"
        )


def make_password(raw_password: str, salt: Optional[str] = None) -> str:
    if raw_password is None:
        return UNUSABLE_PASSWORD_PREFIX + secrets.token_hex(
            UNUSABLE_PASSWORD_SUFFIX_LENGTH
        )

    bcrypt = _ensure_bcrypt()
    return bcrypt.hashpw(
        raw_password.encode(),
        salt.encode() if salt else bcrypt.gensalt(),
    ).decode()


def check_password(raw_password: str, encoded: str) -> bool:
    if raw_password is None or not raw_password:
        return False
    if not encoded or encoded.startswith(UNUSABLE_PASSWORD_PREFIX):
        return False
    bcrypt = _ensure_bcrypt()
    try:
        return bcrypt.checkpw(raw_password.encode(), encoded.encode())
    except (ValueError, TypeError):
        return False


def is_password_usable(encoded: str) -> bool:
    return bool(encoded) and not encoded.startswith(UNUSABLE_PASSWORD_PREFIX)


def needs_rehash(encoded: str, rounds: int = 12) -> bool:
    bcrypt = _ensure_bcrypt()
    try:
        current = int(encoded.split("$")[2])
        return current < rounds
    except (IndexError, ValueError):
        return True


def validate_password(password: str, user=None, min_length: int = 8) -> list[str]:
    errors: list[str] = []
    if len(password) < min_length:
        errors.append(f"Password must be at least {min_length} characters.")
    if not re.search(r"[A-Z]", password):
        errors.append("Password must contain at least one uppercase letter.")
    if not re.search(r"[a-z]", password):
        errors.append("Password must contain at least one lowercase letter.")
    if not re.search(r"\d", password):
        errors.append("Password must contain at least one digit.")
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        errors.append("Password must contain at least one special character.")
    return errors


def password_strength(password: str) -> dict:
    score = 0
    feedback: list[str] = []

    if len(password) >= 12:
        score += 2
    elif len(password) >= 8:
        score += 1
    else:
        feedback.append("Too short")

    if re.search(r"[A-Z]", password):
        score += 1
    if re.search(r"[a-z]", password):
        score += 1
    if re.search(r"\d", password):
        score += 1
    if re.search(r"[^a-zA-Z0-9]", password):
        score += 1

    if len(set(password)) < len(password) * 0.5:
        feedback.append("Low character diversity")

    if score >= 5:
        strength = "strong"
    elif score >= 3:
        strength = "medium"
    else:
        strength = "weak"

    return {"score": score, "strength": strength, "feedback": feedback}


def constant_time_compare(val1: str, val2: str) -> bool:
    return secrets.compare_digest(val1.encode(), val2.encode())


def md5(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode()
    return hashlib.md5(data).hexdigest()


def sha256(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()
