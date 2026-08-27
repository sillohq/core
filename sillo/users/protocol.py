"""
sillo.users.protocol — the parts of the user model that need no database.

Split out of :mod:`sillo.users.base` so that importing sillo does not require
the ORM. ``base`` defines Tortoise models, so importing it pulls in
``tortoise``; the authentication contract, the anonymous user and the password
helpers do not need it, and plenty of code wants only those.

``sillo.users.base`` re-exports everything here, so the older import paths keep
working.
"""

from __future__ import annotations

import secrets
from typing import ClassVar

from sillo.hashing import (
    UNUSABLE_PASSWORD_PREFIX,
    hash_password,
    verify_password,
)

__all__ = [
    "AnonymousUser",
    "BaseUser",
    "UserProtocol",
    "check_password",
    "make_password",
]


def make_password(
    raw_password: str | None = None, scheme: str | None = None, **kwargs
) -> str:
    """Hash a password using sillo.hashing.

    Args:
        raw_password: Plaintext password. If None, creates unusable password marker.
        scheme: Hashing algorithm to use. Options: 'bcrypt' (default if installed),
                'argon2' (if argon2-cffi installed), 'scrypt' (if scrypt installed),
                'pbkdf2_sha256' (built-in, used as fallback if no optional libs).
                If None, uses app's default scheme (bcrypt if available, else pbkdf2_sha256).
        **kwargs: Additional parameters for the hashing function (e.g., salt for bcrypt).

    Returns:
        Hashed password string prefixed with algorithm identifier.

    Examples:
        Hash with default algorithm:
            hashed = make_password("mypassword")

        Hash with specific algorithm:
            hashed = make_password("mypassword", scheme="argon2")
            hashed = make_password("mypassword", scheme="bcrypt")
            hashed = make_password("mypassword", scheme="pbkdf2_sha256")

        Create unusable password marker:
            hashed = make_password(None)  # Used for disabled accounts
    """
    if raw_password is None:
        return UNUSABLE_PASSWORD_PREFIX + secrets.token_hex(40)
    return hash_password(raw_password, scheme=scheme, **kwargs)


def check_password(raw_password: str, encoded: str) -> bool:
    """Verify a password against a hash.

    Automatically detects which algorithm was used to create the hash
    (bcrypt, argon2, scrypt, pbkdf2, etc.) and verifies accordingly.
    Works seamlessly with hashes from any supported algorithm.

    Args:
        raw_password: Plaintext password to verify.
        encoded: Hashed password string (with algorithm prefix).

    Returns:
        True if password is valid and hash is usable, False otherwise.
        Returns False for malformed hashes or disabled passwords.

    Examples:
        Basic verification:
            if check_password("mypassword", user.password_hash):
                # Password is correct
                pass

        Works with any algorithm:
            # These all work automatically:
            bcrypt_hash = make_password("pw", scheme="bcrypt")
            argon2_hash = make_password("pw", scheme="argon2")
            pbkdf2_hash = make_password("pw", scheme="pbkdf2_sha256")

            check_password("pw", bcrypt_hash)  # True
            check_password("pw", argon2_hash)  # True
            check_password("pw", pbkdf2_hash)  # True
    """
    if raw_password is None or not raw_password:
        return False
    if not encoded or encoded.startswith(UNUSABLE_PASSWORD_PREFIX):
        return False
    try:
        return verify_password(raw_password, encoded)
    except Exception:  # pragma: no cover
        # verify_password() already catches every error internally and
        # returns False, so this never actually fires; kept as a guard in
        # case that internal contract ever changes.
        return False


class UserProtocol:
    """Pure authentication contract.

    Every user object in sillo — whether backed by the database or a simple
    in-memory stand-in — satisfies this interface. Operations that require a
    concrete implementation raise ``NotImplementedError`` here.
    """

    REQUIRED_FIELDS: ClassVar[list[str]] = []

    @property
    def is_authenticated(self) -> bool:
        """Is Authenticated"""
        return True

    @property
    def is_anonymous(self) -> bool:
        """Is Anonymous"""
        return not self.is_authenticated

    is_active: bool = True

    @property
    def display_name(self) -> str:
        """Display Name"""
        raise NotImplementedError

    @property
    def identity(self) -> str:
        """Identity"""
        raise NotImplementedError

    def get_id(self) -> str:
        """Get Id"""
        return self.identity

    def get_display_name(self) -> str:
        """Get Display Name"""
        return self.display_name

    def has_perm(self, perm: str) -> bool:
        """Has Perm"""
        return False

    def has_perms(self, perm_list: list[str]) -> bool:
        """Has Perms"""
        return all(self.has_perm(p) for p in perm_list)

    def has_permission(self, permission: str) -> bool:
        """Has Permission"""
        raise NotImplementedError

    def has_module_perms(self, app_label: str) -> bool:
        """Has Module Perms"""
        return self.is_active and self.is_staff  # ty: ignore[unresolved-attribute]  # pyright: ignore[reportAttributeAccessIssue]

    def __str__(self) -> str:
        """Str"""
        return self.get_display_name()

    def __repr__(self) -> str:
        """Repr"""
        return f"<{self.__class__.__name__}: {self}>"

    def __eq__(self, other: object) -> bool:
        """Eq"""
        if not isinstance(other, UserProtocol):
            return NotImplemented
        return self.get_id() == other.get_id()

    def __hash__(self) -> int:
        """Hash"""
        return hash(self.get_id())

    @classmethod
    async def load_user(cls, identity: str) -> UserProtocol | None:
        """Load User"""
        raise NotImplementedError

    @classmethod
    def get_email_field_name(cls) -> str:
        """Get Email Field Name"""
        return "email"


#: Alias used throughout the auth layer as ``type[BaseUser]``. It is the pure
#: contract, so ``BaseUser()`` raises ``NotImplementedError`` for abstract ops.
BaseUser = UserProtocol


class AnonymousUser:
    """The unauthenticated user sentinel."""

    is_authenticated: bool = False
    is_anonymous: bool = True
    is_active: bool = False
    is_staff: bool = False
    is_superuser: bool = False
    display_name: str = ""
    identity: str = ""

    def get_id(self) -> str:
        """Get Id"""
        return ""

    def get_display_name(self) -> str:
        """Get Display Name"""
        return ""

    def has_perm(self, perm: str) -> bool:
        """Has Perm"""
        return False

    def has_perms(self, perm_list: list[str]) -> bool:
        """Has Perms"""
        return False

    def has_module_perms(self, app_label: str) -> bool:
        """Has Module Perms"""
        return False

    def __str__(self) -> str:
        """Str"""
        return "AnonymousUser"

    def __eq__(self, other: object) -> bool:
        """Eq"""
        if not isinstance(other, AnonymousUser):
            return NotImplemented
        return True

    def __hash__(self) -> int:
        """Hash"""
        return 0
