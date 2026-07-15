from __future__ import annotations

from typing import Optional

from sillo.users.password import (
    UNUSABLE_PASSWORD_PREFIX,
    check_password,
    is_password_usable,
    make_password,
)


class AbstractBaseUser:
    REQUIRED_FIELDS: list[str] = []

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def is_anonymous(self) -> bool:
        return not self.is_authenticated

    @property
    def is_active(self) -> bool:
        return True

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
        if not isinstance(other, AbstractBaseUser):
            return NotImplemented
        return self.get_id() == other.get_id()

    def __hash__(self) -> int:
        return hash(self.get_id())

    @classmethod
    async def load_user(cls, identity: str) -> Optional[AbstractBaseUser]:
        raise NotImplementedError

    @classmethod
    def get_email_field_name(cls) -> str:
        return "email"


class BaseUser(AbstractBaseUser):
    password: str
    last_login: Optional[object] = None

    def set_password(self, raw_password: str) -> None:
        self.password = make_password(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password(raw_password, self.password)

    def set_unusable_password(self) -> None:
        self.password = UNUSABLE_PASSWORD_PREFIX

    def has_usable_password(self) -> bool:
        return is_password_usable(self.password)

    async def save(self, *args, **kwargs):
        raise NotImplementedError

    @classmethod
    async def _default_manager(cls):
        raise NotImplementedError


class AnonymousUser:
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
