"""Exceptions for password hashing operations."""


class HashingError(Exception):
    """Base exception for hashing operations."""


class InvalidSchemeError(HashingError):
    """Raised when an invalid hashing scheme is specified."""


class VerificationError(HashingError):
    """Raised when password verification fails."""
