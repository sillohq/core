"""
sillo.users.base — the database-backed user models.

Importing this module requires the ``record`` extra, because the classes below
are Tortoise models. The parts that need no database — :class:`UserProtocol`,
:class:`AnonymousUser` and the password helpers — live in
:mod:`sillo.users.protocol` and are re-exported here so that the original
import paths keep working.
"""

from __future__ import annotations

from datetime import datetime, timezone

from tortoise import fields

from sillo.hashing import (
    UNUSABLE_PASSWORD_PREFIX,
    is_password_usable,
)
from sillo.record import Model
from sillo.users.managers import UserManager
from sillo.users.protocol import (
    AnonymousUser,
    BaseUser,
    UserProtocol,
    check_password,
    make_password,
)

__all__ = [
    "AnonymousUser",
    "BaseUser",
    "User",
    "UserBaseModel",
    "UserProtocol",
    "check_password",
    "make_password",
]


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
        """Meta"""

        abstract = True

    @property
    def is_authenticated(self) -> bool:
        """Is Authenticated"""
        return bool(self.is_active)

    @property
    def display_name(self) -> str:
        """Display Name"""
        return self.username

    @property
    def identity(self) -> str:
        """Identity"""
        return str(self.id)

    def has_perm(self, perm: str) -> bool:
        """Has Perm"""
        if self.is_superuser:
            return True
        return perm in getattr(self, "_permissions", [])

    def has_permission(self, permission: str) -> bool:
        """Has Permission"""
        return self.has_perm(permission)

    def has_perms(self, perm_list: list[str]) -> bool:
        """Has Perms"""
        return all(self.has_perm(p) for p in perm_list)

    def has_module_perms(self, app_label: str) -> bool:
        """Has Module Perms"""
        return bool(self.is_active and self.is_staff)

    def set_password(self, raw_password: str) -> None:
        """Set Password"""
        self.password = make_password(raw_password)

    def check_password(self, raw_password: str) -> bool:
        """Check Password"""
        return check_password(raw_password, self.password)

    def set_unusable_password(self) -> None:
        """Set Unusable Password"""
        self.password = UNUSABLE_PASSWORD_PREFIX

    def has_usable_password(self) -> bool:
        """Has Usable Password"""
        return is_password_usable(self.password)

    async def set_last_login(self) -> None:
        """Set Last Login"""
        self.last_login = datetime.now(timezone.utc)
        await self.save(update_fields=["last_login"])

    async def mark_email_verified(self) -> None:
        """Mark Email Verified"""
        self.email_verified_at = datetime.now(timezone.utc)
        await self.save(update_fields=["email_verified_at"])

    @classmethod
    async def load_user(cls, identity: str) -> UserBaseModel | None:
        """Load User"""
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
        """Get Email Field Name"""
        return "email"

    @classmethod
    async def verify_credentials(
        cls, identifier: str, password: str
    ) -> UserBaseModel | None:
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
        """Meta"""

        table = "users"
