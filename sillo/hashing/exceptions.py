"""Exceptions for password hashing operations."""


class HashingError(Exception):
    """Base exception for hashing operations."""

    pass


class InvalidSchemeError(HashingError):
    """Raised when an invalid hashing scheme is specified."""

    pass


class VerificationError(HashingError):
    """Raised when password verification fails."""

    pass
