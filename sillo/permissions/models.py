from __future__ import annotations

from tortoise import fields
from sillo.record import Model


class Permission(Model):
    """A named, grantable permission.

    Permissions are defined (once) with :meth:`define` and assigned to
    users (via :meth:`assign`) or groups (via :meth:`Group.add_permissions`).
    The mixin :class:`~sillo.permissions.PermissionMixin` bridges them into
    a user model so ``has_permission(…)`` works, resolving both direct and
    group-inherited permissions.

    A permission is simply a name string (e.g. ``"view_posts"``,
    ``"edit_posts"``).  There is no dotted-convention requirement.
    """

    name = fields.CharField(max_length=255, unique=True)
    description = fields.TextField(null=True, default=None)

    class Meta:
        table = "permissions"

    def __str__(self):
        return self.name

    # ── definition ────────────────────────────────────────────────

    @classmethod
    async def define(cls, name: str, description: str = "") -> Permission:
        """Define a new permission, created if it doesn't exist."""
        perm, _ = await cls.get_or_create(
            name=name, defaults={"description": description or None}
        )
        return perm

    # ── user assignment (direct) ──────────────────────────────────

    @classmethod
    async def assign(cls, user, *names: str) -> None:
        """Grant *names* directly to *user*.

        Each permission is auto-defined if it doesn't exist yet.
        *user* can be a model instance (with ``.identity``) or a raw
        identity string.
        """
        user_id = user.identity if hasattr(user, "identity") else str(user)
        for name in names:
            perm, _ = await cls.get_or_create(
                name=name,
                defaults={"description": None},
            )
            await UserPermission.get_or_create(user_id=user_id, permission=perm)

    @classmethod
    async def revoke(cls, user, *names: str) -> None:
        """Remove *names* directly from *user*."""
        user_id = user.identity if hasattr(user, "identity") else str(user)
        if not names:
            return
        perms = await cls.filter(name__in=names)
        if perms:
            perm_ids = [p.id for p in perms]
            await UserPermission.filter(
                user_id=user_id, permission_id__in=perm_ids
            ).delete()

    @classmethod
    async def of(cls, user) -> list[str]:
        """Return all permission names directly assigned to *user*."""
        user_id = user.identity if hasattr(user, "identity") else str(user)
        rows = await UserPermission.filter(user_id=user_id).prefetch_related(
            "permission"
        )
        return sorted({r.permission.name for r in rows})

    # ── user checks (read-only) ───────────────────────────────────

    @classmethod
    async def has(cls, user, name: str) -> bool:
        """Check whether *user* has *name* directly assigned.

        This is a synchronous DB check.  For cached checks use
        ``user.has_permission(name)`` after calling
        ``user.load_permissions()``.
        """
        user_id = user.identity if hasattr(user, "identity") else str(user)
        perm = await cls.get_or_none(name=name)
        if perm is None:
            return False
        return await UserPermission.filter(user_id=user_id, permission=perm).exists()

    # ── group helpers ─────────────────────────────────────────────

    @classmethod
    async def of_group(cls, group) -> list[str]:
        """Return all permission names assigned to *group*."""
        group_id = group.id if hasattr(group, "id") else int(group)
        rows = await GroupPermission.filter(group_id=group_id).prefetch_related(
            "permission"
        )
        return sorted({r.permission.name for r in rows})

    @classmethod
    async def holders(cls, name: str) -> list[str]:
        """Return user identity strings that hold *name* (direct only)."""
        perm = await cls.get_or_none(name=name)
        if perm is None:
            return []
        rows = await UserPermission.filter(permission=perm)
        return [r.user_id for r in rows]


class UserPermission(Model):
    """Direct link between a user (by identity string) and a Permission."""

    user_id = fields.CharField(max_length=255, db_index=True)
    permission = fields.ForeignKeyField("models.Permission")

    class Meta:
        table = "user_permissions"

    def __str__(self):
        return f"{self.user_id} → {self.permission_id}"


class Group(Model):
    """A named group that users can belong to.

    Permissions assigned to a group are inherited by all its members.
    Groups can contain any number of users, and a user can belong to
    any number of groups.
    """

    name = fields.CharField(max_length=150, unique=True, db_index=True)
    description = fields.TextField(null=True, default=None)
    created_at = fields.DatetimeField(auto_now_add=True)
    modified_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "perm_groups"

    def __str__(self):
        return self.name

    # ── lifecycle ─────────────────────────────────────────────────

    @classmethod
    async def get_or_create(cls, name: str, description: str = None) -> Group:
        """Fetch an existing group or create a new one."""
        # Use the super's get_or_create to avoid recursion
        group, _ = await super(cls, cls).get_or_create(
            name=name, defaults={"description": description}
        )
        return group

    # ── user membership ───────────────────────────────────────────

    async def add_user(self, user) -> None:
        """Add *user* to this group."""
        user_id = user.identity if hasattr(user, "identity") else str(user)
        await UserGroup.get_or_create(group=self, user_id=user_id)

    async def remove_user(self, user) -> None:
        """Remove *user* from this group."""
        user_id = user.identity if hasattr(user, "identity") else str(user)
        await UserGroup.filter(group=self, user_id=user_id).delete()

    async def has_user(self, user) -> bool:
        """Check if *user* is a member of this group."""
        user_id = user.identity if hasattr(user, "identity") else str(user)
        return await UserGroup.filter(group=self, user_id=user_id).exists()

    async def get_members(self) -> list[str]:
        """Return identity strings of all group members."""
        rows = await UserGroup.filter(group=self)
        return [r.user_id for r in rows]

    async def get_member_count(self) -> int:
        """Return the number of members in this group."""
        return await UserGroup.filter(group=self).count()

    # ── permission assignment ─────────────────────────────────────

    async def add_permissions(self, *names: str) -> None:
        """Assign *names* to this group.

        All group members will inherit these permissions when they next
        call ``load_permissions()``.
        """
        for name in names:
            perm, _ = await Permission.get_or_create(
                name=name,
                defaults={"description": None},
            )
            await GroupPermission.get_or_create(group=self, permission=perm)

    async def remove_permissions(self, *names: str) -> None:
        """Remove *names* from this group."""
        perms = await Permission.filter(name__in=names)
        if perms:
            perm_ids = [p.id for p in perms]
            await GroupPermission.filter(
                group=self, permission_id__in=perm_ids
            ).delete()

    async def has_permission(self, name: str) -> bool:
        """Check if this group has *name* assigned."""
        perm = await Permission.get_or_none(name=name)
        if perm is None:
            return False
        return await GroupPermission.filter(group=self, permission=perm).exists()

    async def get_permissions(self) -> list[str]:
        """Return all permission names assigned to this group."""
        rows = await GroupPermission.filter(group=self).prefetch_related("permission")
        return sorted({r.permission.name for r in rows})

    # ── queries ───────────────────────────────────────────────────

    @classmethod
    async def of_user(cls, user) -> list[Group]:
        """Return all groups *user* belongs to."""
        user_id = user.identity if hasattr(user, "identity") else str(user)
        rows = await UserGroup.filter(user_id=user_id).prefetch_related("group")
        return [r.group for r in rows]

    @classmethod
    async def names_of_user(cls, user) -> list[str]:
        """Return names of all groups *user* belongs to."""
        groups = await cls.of_user(user)
        return sorted([g.name for g in groups])


class UserGroup(Model):
    """Link table between a user (by identity string) and a Group."""

    user_id = fields.CharField(max_length=255, db_index=True)
    group = fields.ForeignKeyField("models.Group", related_name="memberships")

    class Meta:
        table = "perm_user_groups"
        unique_together = (("user_id", "group"),)

    def __str__(self):
        return f"{self.user_id} ∈ {self.group_id}"


class GroupPermission(Model):
    """Link table between a Group and a Permission."""

    group = fields.ForeignKeyField("models.Group", related_name="group_permissions")
    permission = fields.ForeignKeyField(
        "models.Permission", related_name="group_permissions"
    )

    class Meta:
        table = "perm_group_permissions"
        unique_together = (("group", "permission"),)

    def __str__(self):
        return f"Group#{self.group_id} → #{self.permission_id}"
