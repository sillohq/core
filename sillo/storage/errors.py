"""
sillo.storage.errors — what can go wrong, named.

Deliberately few.  A storage layer that raises a different exception per backend
forces every caller to know which backend it is talking to, which is the one
thing the driver contract exists to prevent.
"""

from __future__ import annotations

__all__ = [
    "FileNotFound",
    "PolicyRefused",
    "SignatureInvalid",
    "StorageError",
    "UnsafeKey",
]


class StorageError(Exception):
    """Base for everything this package raises."""


class FileNotFound(StorageError):
    """There is no object under that key.

    Attributes:
        key: What was asked for.
    """

    def __init__(self, key: str) -> None:
        """Build the error.

        Args:
            key: The key that was not found.
        """
        super().__init__(f"no object at {key!r}")
        self.key = key


class UnsafeKey(StorageError):
    """A key that would escape the bucket, or that no backend can hold.

    Raised at the boundary rather than sanitised silently. A caller that meant
    ``../../etc/passwd`` should be told, not quietly redirected somewhere else.
    """


class PolicyRefused(StorageError):
    """The bucket's policy declined this operation.

    Attributes:
        action: What was attempted.
        key: On what.
    """

    def __init__(self, action: str, key: str) -> None:
        """Build the error.

        Args:
            action: The action refused.
            key: The key it was refused on.
        """
        super().__init__(f"{action} refused on {key!r}")
        self.action = action
        self.key = key


class SignatureInvalid(StorageError):
    """A signed URL was missing, expired, tampered with, or for something else.

    One error for all four on purpose.  Telling an unauthenticated caller
    *which* of those applies tells them how the signing works.
    """
