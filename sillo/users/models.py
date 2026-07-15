from __future__ import annotations

from datetime import datetime, timezone
from typing import ClassVar, Optional

from tortoise import fields

from sillo.record import Model, SoftDeletesMixin, TimestampsMixin
from sillo.users.base import AbstractBaseUser
from sillo.users.managers import UserManager
from sillo.users.password import (
    UNUSABLE_PASSWORD_PREFIX,
    check_password,
    is_password_usable,
    make_password,
)


class User(Model, TimestampsMixin, SoftDeletesMixin, AbstractBaseUser):
    id = fields.IntField(pk=True)
    email = fields.CharField(max_length=255, unique=True, index=True)
    username = fields.CharField(max_length=150, unique=True, index=True)
    password = fields.CharField(max_length=128)

    is_active: ClassVar[fields.BooleanField] = fields.BooleanField(default=True)
    is_staff: ClassVar[fields.BooleanField] = fields.BooleanField(default=False)
    is_superuser: ClassVar[fields.BooleanField] = fields.BooleanField(default=False)

    last_login = fields.DatetimeField(null=True, default=None)
    email_verified_at = fields.DatetimeField(null=True, default=None)

    class Meta:
        table = "users"

    @property
    def is_authenticated(self) -> bool:
        return self.is_active

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
    async def load_user(cls, identity: str) -> Optional[User]:
        return await UserManager().get_by_id(int(identity))

    @classmethod
    def get_email_field_name(cls) -> str:
        return "email"
