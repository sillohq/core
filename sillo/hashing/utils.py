"""Password utilities: validation, strength checking, hashing, etc."""

from __future__ import annotations

import hashlib
import re
import secrets
from typing import Optional, Union


UNUSABLE_PASSWORD_PREFIX = "!"
UNUSABLE_PASSWORD_SUFFIX_LENGTH = 40


def make_unusable_password() -> str:
    """Create an unusable/disabled password marker.

    Returns:
        String that will fail password verification.
    """
    return UNUSABLE_PASSWORD_PREFIX + secrets.token_hex(UNUSABLE_PASSWORD_SUFFIX_LENGTH)


def is_password_usable(encoded: str) -> bool:
    """Check if a password hash is usable (not marked as unusable/disabled).

    Args:
        encoded: Hashed password to check.

    Returns:
        True if password is usable, False if marked as unusable.
    """
    return bool(encoded) and not encoded.startswith(UNUSABLE_PASSWORD_PREFIX)


def validate_password(
    password: str,
    user: Optional[object] = None,
    min_length: int = 8,
) -> list[str]:
    """Validate password strength requirements.

    Args:
        password: Password to validate.
        user: User object (unused, kept for API compatibility).
        min_length: Minimum password length (default 8).

    Returns:
        List of error messages. Empty list if password is valid.

    Example:
        errors = validate_password("Pass123!")
        if errors:
            print(f"Invalid password: {errors}")
    """
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
    """Analyze password strength.

    Args:
        password: Password to analyze.

    Returns:
        Dictionary with:
        - score: 0-6 points
        - strength: "weak", "medium", or "strong"
        - feedback: List of suggestions

    Example:
        result = password_strength("MyPass123!@#")
        print(f"Strength: {result['strength']} (score: {result['score']})")
    """
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
    """Compare two values in constant time (timing-safe).

    Prevents timing attacks by using HMAC compare_digest.

    Args:
        val1: First value to compare.
        val2: Second value to compare.

    Returns:
        True if values match, False otherwise.
    """
    return secrets.compare_digest(val1.encode(), val2.encode())


def md5(value: Union[str, bytes]) -> str:
    """Compute MD5 hash of a value.

    Note: MD5 should not be used for password hashing. Use hash_password() instead.
    This is a utility for checksums and non-cryptographic uses.

    Args:
        value: String or bytes to hash.

    Returns:
        Hexadecimal MD5 hash.
    """
    if isinstance(value, str):
        value = value.encode()
    return hashlib.md5(value).hexdigest()


def sha256(value: Union[str, bytes]) -> str:
    """Compute SHA256 hash of a value.

    Note: SHA256 should not be used for password hashing. Use hash_password() instead.
    This is a utility for checksums and non-cryptographic uses.

    Args:
        value: String or bytes to hash.

    Returns:
        Hexadecimal SHA256 hash.
    """
    if isinstance(value, str):
        value = value.encode()
    return hashlib.sha256(value).hexdigest()
