"""
sillo.admin.default_user — the admin's fallback user model.

Used when :class:`~sillo.admin.AdminSite` is built without a ``user_model``.
Most applications pass their own — the people who sign in to the admin are
usually the same people who sign in to the application, and one user model is
one place to add a field, one password policy, one set of rows.

Register this module in ``model_modules`` **only** if you rely on the default::

    model_modules = ["database.models", "sillo.admin.models", "sillo.admin.default_user"]

Bringing your own user model is the ordinary path::

    from sillo.users import UserBaseModel

    class User(UserBaseModel):
        class Meta:
            table = "users"

    AdminSite(user_model=User).mount(app)
"""

from tortoise import fields
from sillo.record import Model
from sillo.record.fields import PasswordField
from sillo.users import UserBaseModel


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
    the rest of the app, and so does any user model you write yourself.
    ``password`` is overridden to a :class:`PasswordField` so it keeps
    auto-hashing plaintext on assignment (``AdminUser(password="x")``), which
    is the same scheme ``UserBaseModel.check_password`` verifies against.

    This is only the *default*, for an admin panel standing on its own. When
    the application already has users, pass that model instead — one user
    model means one place to add a field and one set of accounts::

        AdminSite(user_model=User).mount(app)

    Keep the role scaffolding by subclassing this class rather than
    :class:`~sillo.users.UserBaseModel`, and register this module so
    ``admin_roles`` exists.
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
