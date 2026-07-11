from typing_extensions import Annotated, Doc

from .base import BaseUser


class SimpleUser(BaseUser):
    """
    A basic implementation of an authenticated user.

    This class represents a simple authenticated user with a username.
    """

    def __init__(
        self,
        username: Annotated[str, Doc("The username of the authenticated user.")],
        permissions: Annotated[list[str], Doc("Array of user User Permissions")] = [],
    ) -> None:
        """
        Initializes a simple authenticated user.

        Args:
            username (str): The username of the user.
        """
        self.username = username
        self.permissions = permissions

    @property
    def is_authenticated(
        self,
    ) -> Annotated[
        bool, Doc("Always returns `True` since this user is authenticated.")
    ]:
        """
        Indicates that the user is authenticated.

        Returns:
            bool: Always `True` since this represents an authenticated user.
        """
        return True

    @property
    def display_name(
        self,
    ) -> Annotated[str, Doc("Returns the username as the display name.")]:
        """
        Retrieves the display name of the user.

        Returns:
            str: The username of the authenticated user.
        """
        return self.username

    def has_permission(self, permission: str) -> bool:
        """
        Checks if the user has the specified permission.

        Args:
            permission (str): A permission to check.

        Returns:
            bool: True if the user has the specified permission, False otherwise.
        """
        if permission in self.permissions:
            return True
        return False

    @classmethod
    async def load_user(cls, identity: str):
        return cls(identity, [identity])

    @property
    def identity(self) -> str:
        return self.username


class UnauthenticatedUser(BaseUser):
    """
    Represents an unauthenticated user.

    This class is used to represent users who have not logged in.
    """

    @property
    def is_authenticated(
        self,
    ) -> Annotated[
        bool, Doc("Always returns `False` since this user is unauthenticated.")
    ]:
        """
        Indicates that the user is not authenticated.

        Returns:
            bool: Always `False` since this represents an unauthenticated user.
        """
        return False

    @property
    def display_name(
        self,
    ) -> Annotated[
        str,
        Doc(
            "Returns an empty string since unauthenticated users have no display name."
        ),
    ]:
        """
        Retrieves the display name of the user.

        Since unauthenticated users do not have a valid username, this
        method returns an empty string.

        Returns:
            str: An empty string.
        """
        return ""

    @property
    def identity(self) -> str:
        return ""

    def has_permission(self, permission: str) -> bool:
        return False
