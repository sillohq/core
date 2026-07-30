"""sillo.users.base — user model + authentication contract.

This module is the single home for sillo's user system. It merges the
authentication *contract* and the user *model* into one place.

* :class:`UserProtocol` — the pure authentication contract. Every user
  object (DB-backed or not) satisfies this interface. Operations that only a
  concrete user can perform raise ``NotImplementedError`` here. ``BaseUser``
  is an alias of it and is used throughout the auth layer as the
  ``type[BaseUser]`` annotation.
* :class:`AnonymousUser` — the unauthenticated sentinel.
* :class:`UserBaseModel` — the abstract, extensible *model* base. It
  combines :class:`sillo.record.Model` (Tortoise-backed, low-level) with the
  auth contract and carries the default user fields + password handling. This
  is the extension point: subclass it to build your own user model. It
  intentionally does **not** include ``TimestampsMixin`` / ``SoftDeletesMixin``
  so users stay lean and predictable.
* :class:`User` — the concrete default user model, built on
  :class:`UserBaseModel`. This is the primary user class sillo auth
  expects you to use: extend it freely or swap in your own
  :class:`UserBaseModel` subclass.

Quick start::

    from sillo.users import User

    user = await User.verify_credentials("admin@example.com", "secret")
    if user is None:
        ...  # invalid credentials
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Optional

from tortoise import fields

from sillo.hashing import (
    UNUSABLE_PASSWORD_PREFIX,
    hash_password,
    is_password_usable,
    verify_password,
)
from sillo.record import Model
from sillo.users.managers import UserManager


def make_password(
    raw_password: Optional[str] = None, scheme: Optional[str] = None, **kwargs
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
    except Exception:
        return False


class UserProtocol:
    """Pure authentication contract.

    Every user object in sillo — whether backed by the database or a simple
    in-memory stand-in — satisfies this interface. Operations that require a
    concrete implementation raise ``NotImplementedError`` here.
    """

    REQUIRED_FIELDS: list[str] = []

    @property
    def is_authenticated(self) -> bool:
        """Is Authenticated

        Returns:
            [description]

        Raises:
            [description]
        """
        return True

    @property
    def is_anonymous(self) -> bool:
        """Is Anonymous

        Returns:
            [description]

        Raises:
            [description]
        """
        return not self.is_authenticated

    is_active: bool = True

    @property
    def display_name(self) -> str:
        """Display Name

        Returns:
            [description]

        Raises:
            [description]
        """
        raise NotImplementedError

    @property
    def identity(self) -> str:
        """Identity

        Returns:
            [description]

        Raises:
            [description]
        """
        raise NotImplementedError

    def get_id(self) -> str:
        """Get Id

        Returns:
            [description]

        Raises:
            [description]
        """
        return self.identity

    def get_display_name(self) -> str:
        """Get Display Name

        Returns:
            [description]

        Raises:
            [description]
        """
        return self.display_name

    def has_perm(self, perm: str) -> bool:
        """Has Perm

        Args:
            perm: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        return False

    def has_perms(self, perm_list: list[str]) -> bool:
        """Has Perms

        Args:
            perm_list: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        return all(self.has_perm(p) for p in perm_list)

    def has_permission(self, permission: str) -> bool:
        """Has Permission

        Args:
            permission: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        raise NotImplementedError

    def has_module_perms(self, app_label: str) -> bool:
        """Has Module Perms

        Args:
            app_label: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        return self.is_active and self.is_staff  # ty: ignore[unresolved-attribute]  # pyright: ignore[reportAttributeAccessIssue]

    def __str__(self) -> str:
        """Str

        Returns:
            [description]

        Raises:
            [description]
        """
        return self.get_display_name()

    def __repr__(self) -> str:
        """Repr

        Returns:
            [description]

        Raises:
            [description]
        """
        return f"<{self.__class__.__name__}: {self}>"

    def __eq__(self, other: object) -> bool:
        """Eq

        Args:
            other: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        if not isinstance(other, UserProtocol):
            return NotImplemented
        return self.get_id() == other.get_id()

    def __hash__(self) -> int:
        """Hash

        Returns:
            [description]

        Raises:
            [description]
        """
        return hash(self.get_id())

    @classmethod
    async def load_user(cls, identity: str) -> Optional[UserProtocol]:
        """Load User

        Args:
            identity: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        raise NotImplementedError

    @classmethod
    def get_email_field_name(cls) -> str:
        """Get Email Field Name

        Returns:
            [description]

        Raises:
            [description]
        """
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
        """Get Id

        Returns:
            [description]

        Raises:
            [description]
        """
        return ""

    def get_display_name(self) -> str:
        """Get Display Name

        Returns:
            [description]

        Raises:
            [description]
        """
        return ""

    def has_perm(self, perm: str) -> bool:
        """Has Perm

        Args:
            perm: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        return False

    def has_perms(self, perm_list: list[str]) -> bool:
        """Has Perms

        Args:
            perm_list: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        return False

    def has_module_perms(self, app_label: str) -> bool:
        """Has Module Perms

        Args:
            app_label: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        return False

    def __str__(self) -> str:
        """Str

        Returns:
            [description]

        Raises:
            [description]
        """
        return "AnonymousUser"

    def __eq__(self, other: object) -> bool:
        """Eq

        Args:
            other: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        if not isinstance(other, AnonymousUser):
            return NotImplemented
        return True

    def __hash__(self) -> int:
        """Hash

        Returns:
            [description]

        Raises:
            [description]
        """
        return 0


class UserBaseModel(Model, UserProtocol):
    """Abstract, extensible user model base.

    Combines :class:`sillo.record.Model` (Tortoise) with the authentication
    contract and the default user fields. This is the extension point: subclass
    it (or :class:`User`) to add fields and behavior. It intentionally does
    **not** include ``TimestampsMixin`` / ``SoftDeletesMixin``.

    Fields:
        id, email, username, password, is_active, is_staff, is_superuser,
        last_login, email_verified_at.
    """

    id = fields.IntField(pk=True)
    email = fields.CharField(max_length=255, unique=True, index=True)
    username = fields.CharField(max_length=150, unique=True, index=True)
    password = fields.CharField(max_length=128)

    is_active = fields.BooleanField(default=True)
    is_staff = fields.BooleanField(default=False)
    is_superuser = fields.BooleanField(default=False)

    last_login = fields.DatetimeField(null=True, default=None)
    email_verified_at = fields.DatetimeField(null=True, default=None)

    class Meta:
        """Meta

        Returns:
            [description]

        Raises:
            [description]
        """

        abstract = True

    @property
    def is_authenticated(self) -> bool:
        """Is Authenticated

        Returns:
            [description]

        Raises:
            [description]
        """
        return bool(self.is_active)

    @property
    def display_name(self) -> str:
        """Display Name

        Returns:
            [description]

        Raises:
            [description]
        """
        return self.username

    @property
    def identity(self) -> str:
        """Identity

        Returns:
            [description]

        Raises:
            [description]
        """
        return str(self.id)

    def has_perm(self, perm: str) -> bool:
        """Has Perm

        Args:
            perm: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        if self.is_superuser:
            return True
        return perm in getattr(self, "_permissions", [])

    def has_permission(self, permission: str) -> bool:
        """Has Permission

        Args:
            permission: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        return self.has_perm(permission)

    def has_perms(self, perm_list: list[str]) -> bool:
        """Has Perms

        Args:
            perm_list: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        return all(self.has_perm(p) for p in perm_list)

    def has_module_perms(self, app_label: str) -> bool:
        """Has Module Perms

        Args:
            app_label: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        return bool(self.is_active and self.is_staff)

    def set_password(self, raw_password: str) -> None:
        """Set Password

        Args:
            raw_password: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        self.password = make_password(raw_password)

    def check_password(self, raw_password: str) -> bool:
        """Check Password

        Args:
            raw_password: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        return check_password(raw_password, self.password)

    def set_unusable_password(self) -> None:
        """Set Unusable Password

        Returns:
            [description]

        Raises:
            [description]
        """
        self.password = UNUSABLE_PASSWORD_PREFIX

    def has_usable_password(self) -> bool:
        """Has Usable Password

        Returns:
            [description]

        Raises:
            [description]
        """
        return is_password_usable(self.password)

    async def set_last_login(self) -> None:
        """Set Last Login

        Returns:
            [description]

        Raises:
            [description]
        """
        self.last_login = datetime.now(timezone.utc)
        await self.save(update_fields=["last_login"])

    async def mark_email_verified(self) -> None:
        """Mark Email Verified

        Returns:
            [description]

        Raises:
            [description]
        """
        self.email_verified_at = datetime.now(timezone.utc)
        await self.save(update_fields=["email_verified_at"])

    @classmethod
    async def load_user(cls, identity: str) -> Optional["UserBaseModel"]:
        """Load User

        Args:
            identity: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        try:
            uid = int(identity)
        except (TypeError, ValueError):
            return None
        user = await cls.filter(id=uid, is_active=True).first()
        if user is not None and hasattr(user, "load_permissions"):
            await user.load_permissions()
        return user

    @classmethod
    def get_email_field_name(cls) -> str:
        """Get Email Field Name

        Returns:
            [description]

        Raises:
            [description]
        """
        return "email"

    @classmethod
    async def verify_credentials(
        cls, identifier: str, password: str
    ) -> Optional["UserBaseModel"]:
        """Authenticate a user by email/username + password.

        Looks the user up by ``identifier`` (email or username) through the
        :class:`~sillo.users.managers.UserManager`, verifies the password, and
        — on success — stamps ``last_login`` before returning the user.
        Returns ``None`` when the user does not exist, is inactive, or the
        password is wrong.

        Args:
            identifier: Email or username submitted by the client.
            password: Raw password to verify.

        Returns:
            The authenticated user instance, or ``None`` on failure.
        """
        manager = UserManager()
        manager.model = cls
        user = await manager.get_by_natural_key(identifier)
        if user is None or not getattr(user, "is_active", False):
            return None
        if not user.check_password(password):
            return None
        await user.set_last_login()
        if hasattr(user, "load_permissions"):
            await user.load_permissions()
        return user


class User(UserBaseModel):
    """Concrete default user model.

    This is the primary user class sillo auth expects. It is deliberately
    minimal and fully extensible — subclass it to add profile fields,
    relationships, or override behavior.
    """

    objects = UserManager()

    class Meta:
        """Meta

        Returns:
            [description]

        Raises:
            [description]
        """

        table = "users"
