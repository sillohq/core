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

from datetime import datetime, timezone
from typing import Optional

from tortoise import fields

from sillo.record import Model
from sillo.users.managers import UserManager
from sillo.users.password import (
    UNUSABLE_PASSWORD_PREFIX,
    check_password,
    is_password_usable,
    make_password,
)


class UserProtocol:
    """Pure authentication contract.

    Every user object in sillo — whether backed by the database or a simple
    in-memory stand-in — satisfies this interface. Operations that require a
    concrete implementation raise ``NotImplementedError`` here.
    """

    REQUIRED_FIELDS: list[str] = []

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def is_anonymous(self) -> bool:
        return not self.is_authenticated

    is_active: bool = True

    @property
    def display_name(self) -> str:
        raise NotImplementedError

    @property
    def identity(self) -> str:
        raise NotImplementedError

    def get_id(self) -> str:
        return self.identity

    def get_display_name(self) -> str:
        return self.display_name

    def has_perm(self, perm: str) -> bool:
        return False

    def has_perms(self, perm_list: list[str]) -> bool:
        return all(self.has_perm(p) for p in perm_list)

    def has_permission(self, permission: str) -> bool:
        raise NotImplementedError

    def has_module_perms(self, app_label: str) -> bool:
        return self.is_active and self.is_staff  # pyright: ignore[reportAttributeAccessIssue]

    def __str__(self) -> str:
        return self.get_display_name()

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self}>"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, UserProtocol):
            return NotImplemented
        return self.get_id() == other.get_id()

    def __hash__(self) -> int:
        return hash(self.get_id())

    @classmethod
    async def load_user(cls, identity: str) -> Optional[UserProtocol]:
        raise NotImplementedError

    @classmethod
    def get_email_field_name(cls) -> str:
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
        return ""

    def get_display_name(self) -> str:
        return ""

    def has_perm(self, perm: str) -> bool:
        return False

    def has_perms(self, perm_list: list[str]) -> bool:
        return False

    def has_module_perms(self, app_label: str) -> bool:
        return False

    def __str__(self) -> str:
        return "AnonymousUser"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AnonymousUser):
            return NotImplemented
        return True

    def __hash__(self) -> int:
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
        abstract = True

    @property
    def is_authenticated(self) -> bool:
        return bool(self.is_active)

    @property
    def display_name(self) -> str:
        return self.username

    @property
    def identity(self) -> str:
        return str(self.id)

    def has_perm(self, perm: str) -> bool:
        if self.is_superuser:
            return True
        return perm in getattr(self, "_permissions", [])

    def has_permission(self, permission: str) -> bool:
        return self.has_perm(permission)

    def has_perms(self, perm_list: list[str]) -> bool:
        return all(self.has_perm(p) for p in perm_list)

    def has_module_perms(self, app_label: str) -> bool:
        return bool(self.is_active and self.is_staff)

    def set_password(self, raw_password: str) -> None:
        self.password = make_password(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password(raw_password, self.password)

    def set_unusable_password(self) -> None:
        self.password = UNUSABLE_PASSWORD_PREFIX

    def has_usable_password(self) -> bool:
        return is_password_usable(self.password)

    async def set_last_login(self) -> None:
        self.last_login = datetime.now(timezone.utc)
        await self.save(update_fields=["last_login"])

    async def mark_email_verified(self) -> None:
        self.email_verified_at = datetime.now(timezone.utc)
        await self.save(update_fields=["email_verified_at"])

    @classmethod
    async def load_user(cls, identity: str) -> Optional["UserBaseModel"]:
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
        table = "users"
