from sillo.users.protocol import UserProtocol


class SimpleUser(UserProtocol):
    """Simpleuser"""

    def __init__(self, username: str, permissions: list[str] | None = None):
        """Init"""
        self.username = username
        self.permissions = permissions or []

    @property
    def is_authenticated(self) -> bool:
        """Is Authenticated"""
        return True

    @property
    def display_name(self) -> str:
        """Display Name"""
        return self.username

    @property
    def identity(self) -> str:
        """Identity"""
        return self.username

    def has_permission(self, permission: str) -> bool:
        """Has Permission"""
        return permission in self.permissions

    @classmethod
    async def load_user(cls, identity: str):
        """Load User"""
        return cls(identity, [identity])


class UnauthenticatedUser(UserProtocol):
    """Unauthenticateduser"""

    @property
    def is_authenticated(self) -> bool:
        """Is Authenticated"""
        return False

    @property
    def display_name(self) -> str:
        """Display Name"""
        return ""

    @property
    def identity(self) -> str:
        """Identity"""
        return ""

    def has_permission(self, permission: str) -> bool:
        """Has Permission"""
        return False

    @classmethod
    async def load_user(cls, identity: str):
        """Load User"""
        return cls()
