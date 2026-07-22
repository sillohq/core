from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Optional, Union

try:
    import bcrypt
except ImportError:
    raise ImportError(
        "bcrypt is required for password hashing. Install with: pip install bcrypt"
    )


def _ensure_bcrypt():
    """Verify and return the bcrypt module for password hashing operations.

    Returns the imported ``bcrypt`` module reference. The module is
    imported at the top of this file with a mandatory import guard, so
    this function serves as a consistent access point for bcrypt
    operations throughout the module.

    Returns:
        The ``bcrypt`` module reference, guaranteed to be available.

    Raises:
        ImportError: If the ``bcrypt`` package is not installed. This
            is raised at module import time, so this function will
            never be called without bcrypt available.
    """
    return bcrypt


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt with an auto-generated salt.

    Generates a cryptographically secure salt via ``bcrypt.gensalt`` and
    uses it to hash the provided password. The resulting hash includes
    the salt and cost factor, making it self-contained for later
    verification without needing to store the salt separately.

    Args:
        password: The plaintext password string to hash. Will be
            encoded to UTF-8 before hashing.

    Returns:
        The bcrypt password hash as a UTF-8 decoded string, containing
        the algorithm identifier, cost factor, salt, and hash digest.
    """
    bcrypt = _ensure_bcrypt()
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode(), salt).decode()


def verify_password(password: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash.

    Compares the provided plaintext password against the stored bcrypt
    hash using ``bcrypt.checkpw``, which extracts the salt from the
    hash and performs a constant-time comparison. Returns ``False``
    gracefully if the hash format is invalid rather than raising.

    Args:
        password: The plaintext password string to verify. Will be
            encoded to UTF-8 before comparison.
        hashed: The stored bcrypt hash string to verify against.
            Must be a valid bcrypt hash including salt and cost factor.

    Returns:
        ``True`` if the password matches the hash, ``False`` if it
        does not match or if the hash format is invalid.
    """
    bcrypt = _ensure_bcrypt()
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def needs_rehash(hashed: str, rounds: int = 12) -> bool:
    """Check whether a bcrypt hash should be rehashed with a higher cost factor.

    Parses the cost factor (number of rounds) from the bcrypt hash string
    and compares it against the desired minimum. If the hash was produced
    with fewer rounds than specified, it indicates the hash should be
    regenerated to maintain adequate security against increasing compute
    power.

    Args:
        hashed: The bcrypt hash string to inspect. Expected format is
            ``"$2b$<rounds>$<salt><hash>"``.
        rounds: The minimum acceptable number of bcrypt rounds. Defaults
            to 12. Hashes with fewer rounds will trigger a rehash.

    Returns:
        ``True`` if the hash's cost factor is below the specified rounds
        or if the hash format is unparseable, ``False`` otherwise.
    """
    bcrypt = _ensure_bcrypt()
    try:
        current_rounds = int(hashed.split("$")[2])
        return current_rounds < rounds
    except (IndexError, ValueError):
        return True


def md5(data: Union[str, bytes]) -> str:
    """Compute the MD5 hex digest of the given data.

    Calculates the MD5 hash of the input data and returns it as a
    lowercase hexadecimal string. String inputs are automatically
    encoded to UTF-8 before hashing. Note that MD5 is not suitable
    for security-sensitive applications due to known collision attacks.

    Args:
        data: The input data to hash. Can be a string (encoded to
            UTF-8) or raw bytes.

    Returns:
        A 32-character lowercase hexadecimal MD5 digest string.
    """
    if isinstance(data, str):
        data = data.encode()
    return hashlib.md5(data).hexdigest()


def sha1(data: Union[str, bytes]) -> str:
    """Compute the SHA-1 hex digest of the given data.

    Calculates the SHA-1 hash of the input data and returns it as a
    lowercase hexadecimal string. String inputs are automatically
    encoded to UTF-8 before hashing. Note that SHA-1 is not recommended
    for security-sensitive applications due to known collision attacks.

    Args:
        data: The input data to hash. Can be a string (encoded to
            UTF-8) or raw bytes.

    Returns:
        A 40-character lowercase hexadecimal SHA-1 digest string.
    """
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha1(data).hexdigest()


def sha256(data: Union[str, bytes]) -> str:
    """Compute the SHA-256 hex digest of the given data.

    Calculates the SHA-256 hash of the input data and returns it as a
    lowercase hexadecimal string. String inputs are automatically
    encoded to UTF-8 before hashing. SHA-256 is part of the SHA-2
    family and is currently considered secure for most applications.

    Args:
        data: The input data to hash. Can be a string (encoded to
            UTF-8) or raw bytes.

    Returns:
        A 64-character lowercase hexadecimal SHA-256 digest string.
    """
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()


def sha512(data: Union[str, bytes]) -> str:
    """Compute the SHA-512 hex digest of the given data.

    Calculates the SHA-512 hash of the input data and returns it as a
    lowercase hexadecimal string. String inputs are automatically
    encoded to UTF-8 before hashing. SHA-512 is part of the SHA-2
    family and provides a larger digest than SHA-256 for higher
    security margins.

    Args:
        data: The input data to hash. Can be a string (encoded to
            UTF-8) or raw bytes.

    Returns:
        A 128-character lowercase hexadecimal SHA-512 digest string.
    """
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha512(data).hexdigest()


def digest(data: Union[str, bytes], algorithm: str = "sha256") -> str:
    """Compute a hex digest of the given data using a specified hash algorithm.

    Creates a new hash object for the named algorithm via ``hashlib.new``
    and computes the hex digest of the input data. String inputs are
    automatically encoded to UTF-8 before hashing. Any algorithm
    supported by the system's OpenSSL library can be used.

    Args:
        data: The input data to hash. Can be a string (encoded to
            UTF-8) or raw bytes.
        algorithm: The name of the hash algorithm to use (e.g.
            ``"sha256"``, ``"sha384"``, ``"blake2b"``). Defaults to
            ``"sha256"``.

    Returns:
        The hex digest string in lowercase hexadecimal format.

    Raises:
        ValueError: If the specified algorithm is not supported by the
            underlying ``hashlib`` implementation.
    """
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
    """Compute an HMAC hex digest of the given data using a secret key.

    Creates an HMAC (Hash-based Message Authentication Code) using the
    provided key and data with the specified hash algorithm. Both key
    and data are automatically encoded to UTF-8 if they are strings.
    The result is returned as a lowercase hexadecimal string suitable
    for signature verification and message authentication.

    Args:
        key: The secret key for HMAC computation. Can be a string
            (encoded to UTF-8) or raw bytes.
        data: The message data to authenticate. Can be a string
            (encoded to UTF-8) or raw bytes.
        algorithm: The name of the hash algorithm to use for HMAC
            (e.g. ``"sha256"``, ``"sha512"``). Defaults to ``"sha256"``.

    Returns:
        The HMAC hex digest as a lowercase hexadecimal string.
    """
    if isinstance(key, str):
        key = key.encode()
    if isinstance(data, str):
        data = data.encode()
    return hmac.new(key, data, algorithm).hexdigest()


def constant_time_compare(a: Union[str, bytes], b: Union[str, bytes]) -> bool:
    """Compare two values in constant time to prevent timing attacks.

    Uses ``hmac.compare_digest`` to perform a byte-level comparison
    that takes the same amount of time regardless of where the values
    first differ. This prevents attackers from inferring information
    about secret values through response time analysis. String inputs
    are automatically encoded to UTF-8 before comparison.

    Args:
        a: The first value to compare. Can be a string (encoded to
            UTF-8) or raw bytes.
        b: The second value to compare. Can be a string (encoded to
            UTF-8) or raw bytes.

    Returns:
        ``True`` if the two values are byte-identical, ``False``
        otherwise. The comparison always runs in time proportional
        to the length of the inputs.
    """
    if isinstance(a, str):
        a = a.encode()
    if isinstance(b, str):
        b = b.encode()
    return hmac.compare_digest(a, b)


def hash_file(path: str, algorithm: str = "sha256", chunk_size: int = 65536) -> str:
    """Compute a hex digest of a file's contents using a specified hash algorithm.

    Reads the file at the given path in chunks and incrementally updates
    the hash object to support large files without loading the entire
    content into memory. The chunk size can be tuned for performance
    based on file size and available memory.

    Args:
        path: The filesystem path to the file to hash. The file must
            exist and be readable.
        algorithm: The name of the hash algorithm to use (e.g.
            ``"sha256"``, ``"sha512"``). Defaults to ``"sha256"``.
        chunk_size: The number of bytes to read per iteration. Larger
            values reduce I/O overhead but use more memory. Defaults
            to 65536 (64 KB).

    Returns:
        The hex digest of the file contents as a lowercase hexadecimal
        string.

    Raises:
        FileNotFoundError: If the file at ``path`` does not exist.
        ValueError: If the specified algorithm is not supported.
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
    """Generate a cryptographically secure random salt as a hex string.

    Uses ``secrets.token_hex`` to produce a random hexadecimal string
    suitable for use as a salt in password hashing or key derivation.
    The resulting string has twice the number of characters as the
    specified byte length since each byte is represented by two hex
    characters.

    Args:
        length: The number of random bytes to generate. The returned
            hex string will be twice this length. Defaults to 16,
            producing a 32-character hex string.

    Returns:
        A lowercase hexadecimal string of ``2 * length`` characters
        generated from cryptographically secure random bytes.
    """
    return secrets.token_hex(length)
