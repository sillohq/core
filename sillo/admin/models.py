"""
sillo.admin.models — the admin's own system models.

Only what an admin site always needs, which is the activity log: every mounted
site records what was done and shows it on the dashboard, so this module has to
be in ``model_modules`` for the admin to work.

The *default* user model lives in :mod:`sillo.admin.default_user` instead, and
is deliberately not imported here. Model discovery scans a module's namespace,
so importing it would put ``admin_users`` and ``admin_roles`` in the database of
every project that registers this module — including the great majority that
pass their own ``user_model`` and would never write a row to either.
"""

from typing import ClassVar

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
        """Meta"""

        table = "admin_activity"
        ordering: ClassVar[list[str]] = ["-created_at"]

    def __str__(self):
        """Str"""
        return f"{self.user_email} {self.action} {self.model_name} at {self.created_at}"
