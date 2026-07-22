from __future__ import annotations

from typing import Optional

from sillo.users.password import validate_password


class UserManager:
    """Manager for ``User`` model — create users, superusers, lookups.

    Attach as ``objects = UserManager()`` on the User model.
    """

    model = None

    def contribute_to_class(self, model, name: str):
        """Contribute To Class

        Args:
            model: [description]
            name: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        self.model = model

    async def create_user(
        self,
        email: str,
        username: str,
        password: Optional[str] = None,
        **extra_fields,
    ):
        """Create User

        Args:
            email: [description]
            username: [description]
            password: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        if self.model is None:
            from sillo.users.base import User as DefaultUser

            self.model = DefaultUser

        extra_fields.setdefault("is_active", True)

        if not password:
            from sillo.users.password import UNUSABLE_PASSWORD_PREFIX
            import secrets

            password = UNUSABLE_PASSWORD_PREFIX + secrets.token_hex(40)

        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        await user.save()
        return user

    async def create_superuser(
        self,
        email: str,
        username: str,
        password: str,
        **extra_fields,
    ):
        """Create Superuser

        Args:
            email: [description]
            username: [description]
            password: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if not password:
            raise ValueError("Superuser must have a password.")

        errors = validate_password(password)
        if errors:
            raise ValueError(" ".join(errors))

        return await self.create_user(
            email=email, username=username, password=password, **extra_fields
        )

    async def get_by_id(self, user_id: int):
        """Get By Id

        Args:
            user_id: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        if self.model is None:
            from sillo.users.base import User as DefaultUser

            self.model = DefaultUser
        return await self.model.filter(id=user_id, is_active=True).first()

    async def get_by_email(self, email: str):
        """Get By Email

        Args:
            email: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        if self.model is None:
            from sillo.users.base import User as DefaultUser

            self.model = DefaultUser
        return await self.model.filter(email=email, is_active=True).first()

    async def get_by_username(self, username: str):
        """Get By Username

        Args:
            username: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        if self.model is None:
            from sillo.users.base import User as DefaultUser

            self.model = DefaultUser
        return await self.model.filter(username=username, is_active=True).first()

    async def get_by_natural_key(self, identifier: str):
        """Find user by email OR username (used by auth backends)."""
        user = await self.get_by_email(identifier)
        if user is None:
            user = await self.get_by_username(identifier)
        return user
