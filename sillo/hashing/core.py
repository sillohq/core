"""Core password hashing operations.

bcrypt is handled natively. Non-bcrypt schemes (argon2, scrypt, pbkdf2)
require the optional ``passlib`` package.
"""

from __future__ import annotations

from typing import Any

from .config import (
    get_available_schemes,
    get_default_scheme,
    install_hint,
    is_scheme_available,
)
from .exceptions import HashingError, InvalidSchemeError

_context: Any | None = None
_default_scheme: str = get_default_scheme()

# Known scheme prefixes, used when passlib is not installed.
_KNOWN_HASH_PREFIXES = (
    "$2a$",
    "$2b$",
    "$2x$",
    "$2y$",  # bcrypt
    "$argon2",  # argon2
    "$scrypt$",  # scrypt
    "$pbkdf2-sha256$",  # pbkdf2_sha256
    "$pbkdf2-sha512$",  # pbkdf2_sha512
)


def _get_context() -> Any:
    """Get or create the passlib CryptContext.

    Raises ``HashingError`` when passlib is not installed and a non-bcrypt
    scheme is requested.
    """
    global _context

    if _context is None:
        try:
            from passlib.context import CryptContext  # noqa: PLC0415
        except ImportError as exc:
            raise HashingError(
                "passlib is required for non-bcrypt hashing schemes. "
                "Install it with: pip install passlib"
            ) from exc

        available_schemes = get_available_schemes()

        if not available_schemes:
            raise HashingError(
                "No hashing schemes available. Install at least one: "
                "bcrypt, argon2-cffi, or scrypt"
            )

        _context = CryptContext(
            schemes=available_schemes,
            deprecated="auto",
        )

    return _context


def hash_password(
    password: str,
    scheme: str | None = None,
    salt: str | None = None,
    **kwargs,
) -> str:
    """Hash a password using the specified scheme.

    Supports multiple hashing algorithms with automatic algorithm detection
    during verification. The hashed output includes a prefix identifying the
    algorithm used, so any algorithm can be verified with verify_password().

    Args:
        password: Plaintext password to hash.
        scheme: Hashing algorithm to use. Options:
                - 'bcrypt' (default if installed): Fast, widely-supported
                - 'argon2' (requires argon2-cffi): Memory-hard, most secure
                - 'scrypt' (requires scrypt): GPU-resistant
                - 'pbkdf2_sha256' (built-in, always available): NIST-approved, reliable
                - 'pbkdf2_sha512' (built-in, always available): Stronger variant
                If None, uses app's default (bcrypt if available, else pbkdf2_sha256).
        salt: Optional salt for bcrypt hashing (for advanced use only).
        **kwargs: Additional keyword arguments passed to the hashing function.

    Returns:
        Hashed password string with algorithm prefix (e.g., $2b$..., $argon2$...).

    Raises:
        InvalidSchemeError: If scheme is not available or unknown.
        HashingError: If hashing fails.

    Examples:
        Hash with default algorithm:
            hashed = hash_password("my_password")

        Hash with specific algorithms:
            hashed_bcrypt = hash_password("my_password", scheme="bcrypt")
            hashed_argon2 = hash_password("my_password", scheme="argon2")
            hashed_pbkdf2 = hash_password("my_password", scheme="pbkdf2_sha256")

        Algorithm mixing (all verify correctly):
            hash1 = hash_password("password", scheme="bcrypt")
            hash2 = hash_password("password", scheme="argon2")
            verify_password("password", hash1)  # True
            verify_password("password", hash2)  # True
    """
    if scheme is None:
        scheme = _default_scheme

    if not is_scheme_available(scheme):
        raise InvalidSchemeError(
            f"Scheme '{scheme}' is not available. Install with: {install_hint(scheme)}"
        )

    try:
        # Use bcrypt directly for bcrypt scheme
        if scheme == "bcrypt":
            import bcrypt as bcrypt_lib

            # A separate name for the bytes form: `salt` is declared
            # `str | None`, and rebinding it to bytes made the annotation
            # describe something the function never holds.
            if salt is not None:
                salt_bytes = salt.encode() if isinstance(salt, str) else salt
            else:
                salt_bytes = bcrypt_lib.gensalt(rounds=12)
            hashed = bcrypt_lib.hashpw(password.encode(), salt_bytes)
            return hashed.decode()

        # For other schemes, use passlib
        context = _get_context()
        return context.hash(password, scheme=scheme, **kwargs)
    except ValueError:
        # Let ValueError through (e.g., password too long for bcrypt)
        raise
    except Exception as e:
        raise HashingError(f"Failed to hash password: {e}") from e


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a hash.

    Automatically detects which algorithm was used to create the hash
    (bcrypt, argon2, scrypt, pbkdf2, etc.) and verifies accordingly.
    Works seamlessly with hashes from any supported algorithm without
    needing to specify the scheme.

    Args:
        password: Plaintext password to verify.
        hashed: Previously hashed password (must include algorithm prefix).

    Returns:
        True if password matches hash, False otherwise or on error.

    Examples:
        Basic verification:
            if verify_password("my_password", user.password_hash):
                print("Password is correct!")

        Works with any algorithm (auto-detected):
            bcrypt_hash = hash_password("pw", scheme="bcrypt")
            argon2_hash = hash_password("pw", scheme="argon2")
            pbkdf2_hash = hash_password("pw", scheme="pbkdf2_sha256")

            # All return True, no scheme parameter needed
            verify_password("pw", bcrypt_hash)   # True
            verify_password("pw", argon2_hash)   # True
            verify_password("pw", pbkdf2_hash)   # True

            # All return False for wrong password
            verify_password("wrong", bcrypt_hash)   # False
            verify_password("wrong", argon2_hash)   # False
    """
    if not hashed:
        return False

    # Try bcrypt directly first if it's a bcrypt hash
    if hashed.startswith(("$2a$", "$2b$", "$2x$", "$2y$")):
        try:
            import bcrypt as bcrypt_lib

            return bcrypt_lib.checkpw(password.encode(), hashed.encode())
        except Exception:
            pass

    context = _get_context()

    try:
        return context.verify(password, hashed)
    except Exception:
        return False


def needs_update(hashed: str) -> bool:
    """Check if a hash should be regenerated with stronger settings.

    This is useful for migrating to stronger schemes or parameters.

    Args:
        hashed: Previously hashed password.

    Returns:
        True if hash should be regenerated, False otherwise.

    Example:
        if needs_update(user.password_hash):
            user.password_hash = hash_password(password)
            user.save()
    """
    if not hashed:
        return True

    if hashed.startswith("$2"):
        try:
            current_rounds = int(hashed.split("$")[2])
            return current_rounds < 12
        except (IndexError, ValueError):
            return True

    try:
        return _get_context().needs_update(hashed)
    except Exception:
        return False


def is_hashed(value: str) -> bool:
    """Report whether a string is already a hash this application can verify.

    When passlib is installed, asks it to identify the scheme rather than
    matching a prefix. A prefix test has to name every algorithm it accepts,
    and the one that existed only knew bcrypt, so an argon2, scrypt or pbkdf2
    hash was treated as a plaintext password and hashed a second time, and
    every login against it then failed.

    When passlib is not installed, falls back to a prefix check against the
    known scheme identifiers.

    Args:
        value: The string to inspect. Usually a value on its way into a
            password column, which may be either plaintext or a hash.

    Returns:
        True when the value is recognised as a hash produced by one of the
        configured schemes, False for plaintext or for a hash from a scheme
        this application has no handler for.

    Example:
        if not is_hashed(value):
            value = hash_password(value)
    """
    if not isinstance(value, str) or not value:
        return False

    try:
        return _get_context().identify(value) is not None
    except HashingError:
        pass

    for prefix in _KNOWN_HASH_PREFIXES:
        if value.startswith(prefix):
            return True

    return False


def set_default_scheme(scheme: str) -> None:
    """Set the default hashing scheme for the application.

    Args:
        scheme: Scheme name (bcrypt, argon2, scrypt, pbkdf2_sha256, pbkdf2_sha512).

    Raises:
        InvalidSchemeError: If scheme is not available.

    Example:
        set_default_scheme("argon2")
        hashed = hash_password("password")  # Uses argon2
    """
    global _default_scheme

    if not is_scheme_available(scheme):
        raise InvalidSchemeError(
            f"Scheme '{scheme}' is not available. Install with: {install_hint(scheme)}"
        )

    _default_scheme = scheme


def get_available_schemes_list() -> list[str]:
    """Get list of currently available hashing schemes.

    Returns:
        List of available scheme names.

    Example:
        schemes = get_available_schemes_list()
        print(f"Available schemes: {schemes}")
    """
    return get_available_schemes()


def needs_rehash(hashed: str, rounds: int = 12) -> bool:
    """Check if a hash should be regenerated with stronger settings.

    For bcrypt hashes, checks if rounds are below the specified minimum.
    For other schemes, uses passlib's needs_update().

    Args:
        hashed: Previously hashed password.
        rounds: Minimum bcrypt rounds (only for bcrypt hashes).

    Returns:
        True if hash should be regenerated, False otherwise.

    Example:
        if needs_rehash(user.password_hash):
            user.password_hash = hash_password(plaintext)
    """
    if not hashed:
        return True

    if needs_update(hashed):
        return True

    if hashed.startswith("$2"):
        try:
            current_rounds = int(hashed.split("$")[2])
            return current_rounds < rounds
        except (IndexError, ValueError):
            return True

    return False
