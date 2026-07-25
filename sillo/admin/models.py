"""
sillo.admin.models — Admin-specific models for activity logging and RBAC.
"""

from tortoise import fields
from sillo.record import Model
from sillo.record.fields import PasswordField
from sillo.users import UserBaseModel


class AdminActivity(Model):
    """Tracks every admin action for audit purposes."""

    user_email = fields.CharField(max_length=255)
    action = fields.CharField(max_length=50)  # create, update, delete, login, logout
    model_name = fields.CharField(max_length=100)
    object_id = fields.CharField(max_length=50, null=True)
    detail = fields.TextField(null=True)
    ip_address = fields.CharField(max_length=50, null=True)
    user_agent = fields.TextField(null=True)

    class Meta:
        """Meta

        Returns:
            [description]

        Raises:
            [description]
        """

        table = "admin_activity"
        ordering = ["-created_at"]

    def __str__(self):
        """Str

        Returns:
            [description]

        Raises:
            [description]
        """
        return f"{self.user_email} {self.action} {self.model_name} at {self.created_at}"


class AdminRole(Model):
    """RBAC role for admin users."""

    name = fields.CharField(max_length=100, unique=True)
    slug = fields.CharField(max_length=100, unique=True)
    permissions = fields.JSONField(default=list)  # ["users.view", "users.create", ...]
    description = fields.TextField(null=True)

    class Meta:
        """Meta

        Returns:
            [description]

        Raises:
            [description]
        """

        table = "admin_roles"

    def __str__(self):
        """Str

        Returns:
            [description]

        Raises:
            [description]
        """
        return self.name


class AdminUser(UserBaseModel):
    """Admin user with role-based access control.

    Extends :class:`sillo.users.UserBaseModel` — sillo's shared user/auth
    contract — so admin login goes through the same
    ``set_password``/``check_password``/``verify_credentials`` machinery as
    the rest of the app. ``password`` is overridden to a :class:`PasswordField`
    so it keeps auto-hashing plaintext on assignment (``AdminUser(password="x")``),
    which is the same bcrypt scheme ``UserBaseModel.check_password`` verifies
    against.

    This is only the *default* admin user model. Build your own by
    subclassing :class:`sillo.users.UserBaseModel` (or this class, to keep
    the role/permission scaffolding) and pass it to ``setup_admin(app,
    user_model=YourAdminUser)``.
    """

    password = PasswordField()
    role: fields.ForeignKeyRelation[AdminRole] = fields.ForeignKeyField(  # ty: ignore[invalid-assignment]
        "models.AdminRole", null=True
    )

    class Meta:
        """Meta

        Returns:
            [description]

        Raises:
            [description]
        """

        table = "admin_users"

    def __str__(self):
        """Str

        Returns:
            [description]

        Raises:
            [description]
        """
        return self.email

    def has_permission(self, permission: str) -> bool:
        """Has Permission

        Args:
            permission: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        if self.is_superuser:
            return True
        if self.role and hasattr(self.role, "permissions"):
            return permission in (self.role.permissions or [])
        return False

    def to_dict(self, **kwargs):
        """To Dict

        Returns:
            [description]

        Raises:
            [description]
        """
        d = super().to_dict(**kwargs)
        d.pop("password", None)
        return d
