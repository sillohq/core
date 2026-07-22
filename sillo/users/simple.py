from sillo.users.base import UserProtocol


class SimpleUser(UserProtocol):
    """Simpleuser

        Returns:
            [description]

        Raises:
            [description]
    """
    def __init__(self, username: str, permissions: list[str] | None = None):
        """Init

            Args:
                username: [description]
                permissions: [description]

            Returns:
                [description]

            Raises:
                [description]
        """
        self.username = username
        self.permissions = permissions or []

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
        return self.username

    def has_permission(self, permission: str) -> bool:
        """Has Permission

            Args:
                permission: [description]

            Returns:
                [description]

            Raises:
                [description]
        """
        return permission in self.permissions

    @classmethod
    async def load_user(cls, identity: str):
        """Load User

            Args:
                identity: [description]

            Returns:
                [description]

            Raises:
                [description]
        """
        return cls(identity, [identity])


class UnauthenticatedUser(UserProtocol):
    """Unauthenticateduser

        Returns:
            [description]

        Raises:
            [description]
    """
    @property
    def is_authenticated(self) -> bool:
        """Is Authenticated

            Returns:
                [description]

            Raises:
                [description]
        """
        return False

    @property
    def display_name(self) -> str:
        """Display Name

            Returns:
                [description]

            Raises:
                [description]
        """
        return ""

    @property
    def identity(self) -> str:
        """Identity

            Returns:
                [description]

            Raises:
                [description]
        """
        return ""

    def has_permission(self, permission: str) -> bool:
        """Has Permission

            Args:
                permission: [description]

            Returns:
                [description]

            Raises:
                [description]
        """
        return False

    @classmethod
    async def load_user(cls, identity: str):
        """Load User

            Args:
                identity: [description]

            Returns:
                [description]

            Raises:
                [description]
        """
        return cls()
