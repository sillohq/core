from typing_extensions import Annotated, Doc


class BaseUser:
    """
    Abstract base class for user objects.

    This class defines the minimum required properties for user objects,
    including authentication status, display name, and identity.

    Subclasses should override these properties to provide meaningful values.
    """

    @property
    def is_authenticated(
        self,
    ) -> Annotated[bool, Doc("Indicates whether the user is authenticated.")]:
        """
        Checks if the user is authenticated.

        This property should be overridden in subclasses to return `True` for
        authenticated users and `False` for unauthenticated users.

        Returns:
            bool: `True` if the user is authenticated, otherwise `False`.
        """
        raise NotImplementedError()

    @property
    def display_name(
        self,
    ) -> Annotated[str, Doc("The name to be displayed for the user.")]:
        """
        Retrieves the display name of the user.

        This property should be overridden to return a human-readable
        name for authenticated users or an empty string for unauthenticated users.

        Returns:
            str: The display name of the user.
        """
        raise NotImplementedError()

    @property
    def identity(
        self,
    ) -> Annotated[
        str, Doc("A unique identifier for the user, such as a username or ID.")
    ]:
        """
        Retrieves the unique identity of the user.

        This property should be overridden to return a unique identifier
        (e.g., username, email, or user ID).

        Returns:
            str: The unique identifier of the user.
        """
        raise NotImplementedError()

    def has_permission(self, permission: str) -> bool:
        """checks if the request user has the provided permission"""
        raise NotImplementedError()

    @classmethod
    async def load_user(
        cls, identity: Annotated[str, Doc("The unique identifier of the user.")]
    ) -> "BaseUser":
        """loads a user by identity"""
        raise NotImplementedError()
