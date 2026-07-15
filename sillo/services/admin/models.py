"""
sillo.services.admin.models — Admin-specific models for activity logging and RBAC.
"""

from tortoise import fields
from sillo.record import Model


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
        table = "admin_activity"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user_email} {self.action} {self.model_name} at {self.created_at}"


class AdminRole(Model):
    """RBAC role for admin users."""

    name = fields.CharField(max_length=100, unique=True)
    slug = fields.CharField(max_length=100, unique=True)
    permissions = fields.JSONField(default=list)  # ["users.view", "users.create", ...]
    description = fields.TextField(null=True)

    class Meta:
        table = "admin_roles"

    def __str__(self):
        return self.name


class AdminUser(Model):
    """Admin user with role-based access control."""

    email = fields.CharField(max_length=255, unique=True)
    username = fields.CharField(max_length=100, unique=True)
    password_hash = fields.CharField(max_length=255)
    is_active = fields.BooleanField(default=True)
    is_superuser = fields.BooleanField(default=False)
    last_login = fields.DatetimeField(null=True)
    role: fields.ForeignKeyRelation[AdminRole] = fields.ForeignKeyField("models.AdminRole", null=True)

    class Meta:
        table = "admin_users"

    def __str__(self):
        return self.email

    def has_permission(self, permission: str) -> bool:
        if self.is_superuser:
            return True
        if self.role and hasattr(self.role, "permissions"):
            return permission in (self.role.permissions or [])
        return False

    def to_dict(self, **kwargs):
        d = super().to_dict(**kwargs)
        d.pop("password_hash", None)
        return d
