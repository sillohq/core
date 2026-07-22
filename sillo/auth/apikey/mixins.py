from __future__ import annotations

from datetime import datetime
from typing import Optional

from sillo.auth.apikey.models import ApiKey, ApiKeyManager


class ApiKeyUserMixin:
    """Mixin that adds API key management capabilities to a user model.

    Provides methods for creating, listing, and revoking API keys
    associated with the authenticated user. This mixin expects to be
    composed into a user class that exposes an ``identity`` attribute
    representing the user's unique identifier.

    Attributes:
        identity: Inherited from the host user class. Represents the
            unique identifier of the user whose API keys are managed.
    """

    async def create_api_key(
        self,
        name: str,
        scopes: Optional[list[str]] = None,
        expires_at: Optional[datetime] = None,
        prefix: str = "sillo",
    ) -> tuple[str, object]:
        """Create a new API key for the current user.

        Delegates key generation and storage to ``ApiKeyManager``,
        producing a full API key string and persisting its hashed
        form in the database associated with this user's identity.

        Args:
            name: A human-readable label for the API key, used to
                identify its purpose in management interfaces.
            scopes: Optional list of permission scope strings that
                restrict what operations this key can perform. If
                None, the key inherits the user's full permissions.
            expires_at: Optional datetime after which the key becomes
                invalid and can no longer be used for authentication.
                If None, the key does not expire automatically.
            prefix: A short string prepended to the generated key
                for easy identification. Defaults to ``"sillo"``.

        Returns:
            tuple[str, object]: A tuple containing the full API key
            string and the created API key model object.

        Raises:
            ValueError: If the user identity cannot be converted to
                an integer for database storage.
        """
        return await ApiKeyManager().create_key(
            user_id=int(str(self.identity)),
            name=name,
            scopes=scopes,
            expires_at=expires_at,
            prefix=prefix,
        )

    async def get_api_keys(self):
        """Retrieve all API keys belonging to the current user.

        Queries the database through ``ApiKeyManager`` for every
        API key record associated with this user's identity,
        including both active and revoked keys.

        Args:
            None: This method takes no arguments beyond self.

        Returns:
            list[ApiKey]: A list of API key model instances belonging
            to the current user, as fetched from the database.

        Raises:
            ValueError: If the user identity cannot be converted to
                an integer for the database query.
        """
        return await ApiKeyManager().get_for_user(int(str(self.identity)))

    async def revoke_all_api_keys(self) -> int:
        """Revoke every active API key belonging to the current user.

        Iterates through all active API keys for this user and marks
        each one as revoked in the database via ``ApiKeyManager``.

        Args:
            None: This method takes no arguments beyond self.

        Returns:
            int: The number of API keys that were successfully revoked
            during this operation.

        Raises:
            ValueError: If the user identity cannot be converted to
                an integer for the database operation.
        """
        return await ApiKeyManager().revoke_all_for_user(int(str(self.identity)))

    async def revoke_api_key(self, key_id: int) -> bool:
        """Revoke a single API key by its database identifier.

        Looks up the API key with the given ID that belongs to the
        current user and is still active. If found, the key is marked
        as revoked. Keys belonging to other users or already revoked
        keys are silently ignored.

        Args:
            key_id: The primary key identifier of the API key record
                to revoke. Must correspond to a key owned by the
                current user.

        Returns:
            bool: True if the API key was found and successfully
            revoked, False if no matching active key was found for
            the current user.

        Raises:
            ValueError: If the user identity cannot be converted to
                an integer for the database query.
        """
        apikey = await ApiKey.filter(
            id=key_id,
            user_id=int(str(self.identity)),
            is_active=True,
        ).first()
        if apikey:
            await apikey.revoke()
            return True
        return False
