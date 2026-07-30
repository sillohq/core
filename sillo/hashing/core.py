"""Core password hashing operations using passlib."""

from typing import Optional

from passlib.context import CryptContext

from .config import get_available_schemes, get_default_scheme, is_scheme_available
from .exceptions import HashingError, InvalidSchemeError


_context: Optional[CryptContext] = None
_default_scheme: str = get_default_scheme()


def _get_context() -> CryptContext:
    """Get or create the passlib CryptContext."""
    global _context

    if _context is None:
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
    scheme: Optional[str] = None,
    salt: Optional[str] = None,
    **kwargs,
) -> str:
    """Hash a password using the specified scheme.

    Args:
        password: Plaintext password to hash.
        scheme: Hashing scheme (bcrypt, argon2, scrypt, pbkdf2_sha256, pbkdf2_sha512).
               If None, uses the default scheme (bcrypt).
        salt: Optional salt for bcrypt hashing (for advanced use only).
        **kwargs: Additional keyword arguments passed to the hashing function.

    Returns:
        Hashed password string.

    Raises:
        InvalidSchemeError: If scheme is not available.
        HashingError: If hashing fails.

    Example:
        hashed = hash_password("my_password")
        hashed_argon2 = hash_password("my_password", scheme="argon2")
    """
    if scheme is None:
        scheme = _default_scheme

    if not is_scheme_available(scheme):
        raise InvalidSchemeError(
            f"Scheme '{scheme}' is not available. Install with: pip install {scheme}"
        )

    try:
        # Use bcrypt directly for bcrypt scheme
        if scheme == "bcrypt":
            import bcrypt as bcrypt_lib

            if salt is not None:
                # Use provided salt
                if isinstance(salt, str):
                    salt = salt.encode()
            else:
                # Generate new salt with 12 rounds by default
                salt = bcrypt_lib.gensalt(rounds=12)
            hashed = bcrypt_lib.hashpw(password.encode(), salt)
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

    Automatically detects which scheme was used to create the hash.

    Args:
        password: Plaintext password to verify.
        hashed: Previously hashed password.

    Returns:
        True if password matches hash, False otherwise.

    Example:
        if verify_password("my_password", stored_hash):
            print("Password is correct!")
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
    context = _get_context()

    try:
        return context.needs_update(hashed)
    except Exception:
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
            f"Scheme '{scheme}' is not available. Install with: pip install {scheme}"
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
