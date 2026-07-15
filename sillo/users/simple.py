from sillo.users.base import AbstractBaseUser


class SimpleUser(AbstractBaseUser):
    def __init__(self, username: str, permissions: list[str] | None = None):
        self.username = username
        self.permissions = permissions or []

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def display_name(self) -> str:
        return self.username

    @property
    def identity(self) -> str:
        return self.username

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions

    @classmethod
    async def load_user(cls, identity: str):
        return cls(identity, [identity])


class UnauthenticatedUser(AbstractBaseUser):
    @property
    def is_authenticated(self) -> bool:
        return False

    @property
    def display_name(self) -> str:
        return ""

    @property
    def identity(self) -> str:
        return ""

    def has_permission(self, permission: str) -> bool:
        return False

    @classmethod
    async def load_user(cls, identity: str):
        return cls()
