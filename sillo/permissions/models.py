from __future__ import annotations

from tortoise import fields
from sillo.record import Model


class Permission(Model):
    """A named, grantable permission that can be assigned to users or groups.

    Permissions are defined (once) with :meth:`define` and assigned to
    users (via :meth:`assign`) or groups (via :meth:`Group.add_permissions`).
    The mixin :class:`~sillo.permissions.PermissionMixin` bridges them into
    a user model so ``has_permission(…)`` works, resolving both direct and
    group-inherited permissions.

    A permission is simply a name string (e.g. ``"view_posts"``,
    ``"edit_posts"``).  There is no dotted-convention requirement.

    Attributes:
        name: Unique string identifier for the permission, e.g. ``"edit_posts"``.
            Maximum length is 255 characters and must be unique across all
            permission records in the database.
        description: Optional human-readable description of what the permission
            grants access to. Defaults to ``None`` if not provided.

    Raises:
        None: No exceptions are raised by the class definition itself.
    """

    name = fields.CharField(max_length=255, unique=True)
    description = fields.TextField(null=True, default=None)

    class Meta:
        table = "permissions"

    def __str__(self):
        """Return the string representation of this permission.

        Returns the permission's ``name`` attribute, which serves as the
        human-readable and machine-identifiable label for this permission
        record. Used by Django/Tortoise admin views and debug output.

        Args:
            self: The ``Permission`` model instance.

        Returns:
            The ``name`` field value as a string, e.g. ``"edit_posts"``.

        Raises:
            None: This method performs no I/O and raises no exceptions.
        """
        return self.name

    # ── definition ────────────────────────────────────────────────

    @classmethod
    async def define(cls, name: str, description: str = "") -> Permission:
        """Define a new permission in the system, creating it if it does not already exist.

        Uses ``get_or_create`` to ensure idempotency: calling ``define`` with
        the same name multiple times will return the existing record without
        duplication. If a description is provided and the permission already
        exists, the existing description is NOT updated.

        This is the recommended entry point for registering new permissions
        during application setup or migration scripts.

        Args:
            name: The unique string identifier for the permission, e.g.
                ``"edit_posts"`` or ``"delete_comments"``.
            description: An optional human-readable description of what the
                permission grants. Defaults to an empty string, which is
                stored as ``None`` in the database.

        Returns:
            The ``Permission`` instance, either newly created or fetched
            from the database if it already existed.

        Raises:
            tortoise.exceptions.IntegrityError: If a concurrent insert causes
                a unique constraint violation on the ``name`` field.
        """
        perm, _ = await cls.get_or_create(
            name=name, defaults={"description": description or None}
        )
        return perm

    # ── user assignment (direct) ──────────────────────────────────

    @classmethod
    async def assign(cls, user, *names: str) -> None:
        """Grant one or more permissions directly to a user.

        Each permission name is auto-defined via ``get_or_create`` if it does
        not already exist in the database, then a ``UserPermission`` link row
        is created (also idempotently) between the user and the permission.
        Duplicate assignments are silently ignored.

        The user argument can be either a model instance with an ``identity``
        attribute or a raw identity string (e.g. a UUID or email).

        Args:
            user: The target user, either a model instance with an
                ``identity`` attribute or a raw identity string.
            *names: One or more permission name strings to grant, e.g.
                ``"edit_posts"``, ``"delete_comments"``.

        Returns:
            None. This method modifies database state but returns nothing.

        Raises:
            tortoise.exceptions.IntegrityError: If a concurrent insert causes
                a unique constraint violation on the ``UserPermission`` table.
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
        """Remove one or more directly assigned permissions from a user.

        Looks up the ``Permission`` records matching the given names, then
        deletes the corresponding ``UserPermission`` link rows for the
        specified user. Permissions that do not exist in the database are
        silently ignored. If no names are provided, the method returns
        immediately without performing any database operations.

        This only removes direct user-permission assignments. Permissions
        inherited through group membership are not affected by this method.

        Args:
            user: The target user, either a model instance with an
                ``identity`` attribute or a raw identity string.
            *names: One or more permission name strings to revoke, e.g.
                ``"edit_posts"``, ``"delete_comments"``.

        Returns:
            None. This method modifies database state but returns nothing.

        Raises:
            tortoise.exceptions.OperationalError: If the database delete
                operation fails due to a connection or schema issue.
        """
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
        """Return all permission names directly assigned to a user.

        Queries the ``UserPermission`` join table for the given user and
        prefetches the related ``Permission`` records to extract permission
        names. The result is returned as a sorted list for deterministic
        output. Only direct assignments are included; group-inherited
        permissions are not considered.

        Args:
            user: The target user, either a model instance with an
                ``identity`` attribute or a raw identity string.

        Returns:
            A sorted ``list`` of unique permission name strings directly
            assigned to the user. Returns an empty list if the user has
            no direct permission assignments.

        Raises:
            tortoise.exceptions.OperationalError: If the database query fails
                due to a connection or schema issue.
        """
        user_id = user.identity if hasattr(user, "identity") else str(user)
        rows = await UserPermission.filter(user_id=user_id).prefetch_related(
            "permission"
        )
        return sorted({r.permission.name for r in rows})

    # ── user checks (read-only) ───────────────────────────────────

    @classmethod
    async def has(cls, user, name: str) -> bool:
        """Check whether a user has a specific permission directly assigned.

        Performs a two-step database lookup: first resolves the ``Permission``
        record by name, then checks for the existence of a ``UserPermission``
        link row between that permission and the given user. This is a live
        database check and does NOT use the in-memory permission cache.

        For cached checks in request handlers, prefer calling
        ``user.has_permission(name)`` after ``user.load_permissions()``
        has been invoked during authentication.

        Args:
            user: The target user, either a model instance with an
                ``identity`` attribute or a raw identity string.
            name: The permission name to check, e.g. ``"edit_posts"``.

        Returns:
            ``True`` if the permission exists and is directly assigned to the
            user, ``False`` if the permission does not exist or is not
            assigned to the user.

        Raises:
            tortoise.exceptions.OperationalError: If the database query fails
                due to a connection or schema issue.
        """
        user_id = user.identity if hasattr(user, "identity") else str(user)
        perm = await cls.get_or_none(name=name)
        if perm is None:
            return False
        return await UserPermission.filter(user_id=user_id, permission=perm).exists()

    # ── group helpers ─────────────────────────────────────────────

    @classmethod
    async def of_group(cls, group) -> list[str]:
        """Return all permission names assigned to a specific group.

        Queries the ``GroupPermission`` join table for the given group and
        prefetches the related ``Permission`` records to extract permission
        names. The result is returned as a sorted list for deterministic
        output and deduplication.

        Args:
            group: The target group, either a ``Group`` model instance with
                an ``id`` attribute or a raw integer group ID.

        Returns:
            A sorted ``list`` of unique permission name strings assigned to
            the group. Returns an empty list if the group has no permissions.

        Raises:
            tortoise.exceptions.OperationalError: If the database query fails
                due to a connection or schema issue.
        """
        group_id = group.id if hasattr(group, "id") else int(group)
        rows = await GroupPermission.filter(group_id=group_id).prefetch_related(
            "permission"
        )
        return sorted({r.permission.name for r in rows})

    @classmethod
    async def holders(cls, name: str) -> list[str]:
        """Return the identity strings of all users who hold a specific permission directly.

        Resolves the ``Permission`` record by name, then queries the
        ``UserPermission`` join table to find all user identity strings
        linked to that permission. Only direct assignments are considered;
        users who inherit the permission through group membership are NOT
        included in the result.

        Args:
            name: The permission name to look up, e.g. ``"edit_posts"``.

        Returns:
            A ``list`` of user identity strings (e.g. UUIDs or emails) that
            have the permission directly assigned. Returns an empty list if
            the permission does not exist or has no direct holders.

        Raises:
            tortoise.exceptions.OperationalError: If the database query fails
                due to a connection or schema issue.
        """
        perm = await cls.get_or_none(name=name)
        if perm is None:
            return []
        rows = await UserPermission.filter(permission=perm)
        return [r.user_id for r in rows]


class UserPermission(Model):
    """Direct link between a user (identified by identity string) and a Permission.

    This is the join/through table that records direct user-to-permission
    assignments. Each row represents a single permission grant for a single
    user. The ``user_id`` field stores the user's identity string (not a
    foreign key to a user table), allowing permissions to be assigned to
    any identity regardless of the user model implementation.

    Attributes:
        user_id: The identity string of the user (e.g. UUID or email),
            indexed for efficient lookup by user.
        permission: Foreign key reference to the ``Permission`` model
            instance that is being granted.

    Raises:
        None: No exceptions are raised by the class definition itself.
    """

    user_id = fields.CharField(max_length=255, db_index=True)
    permission = fields.ForeignKeyField("models.Permission")

    class Meta:
        table = "user_permissions"

    def __str__(self):
        """Return a human-readable string representation of this user-permission link.

        Formats the user identity and permission ID as an arrow-separated
        pair for easy identification in admin views, debug output, and
        log messages.

        Args:
            self: The ``UserPermission`` model instance.

        Returns:
            A string in the format ``"{user_id} → {permission_id}"``,
            e.g. ``"user@example.com → 42"``.

        Raises:
            None: This method performs no I/O and raises no exceptions.
        """


class Group(Model):
    """A named group that users can belong to for bulk permission inheritance.

    Permissions assigned to a group are inherited by all its members.
    Groups can contain any number of users, and a user can belong to
    any number of groups. Group membership is managed through the
    ``UserGroup`` join table.

    Attributes:
        name: Unique string identifier for the group, e.g. ``"admins"``.
            Maximum length is 150 characters and must be unique across
            all group records in the database.
        description: Optional human-readable description of the group's
            purpose or role. Defaults to ``None`` if not provided.
        created_at: Timestamp of when the group was first created, set
            automatically on initial insert.
        modified_at: Timestamp of the most recent modification, updated
            automatically on every save operation.

    Raises:
        None: No exceptions are raised by the class definition itself.
    """

    name = fields.CharField(max_length=150, unique=True, db_index=True)
    description = fields.TextField(null=True, default=None)
    created_at = fields.DatetimeField(auto_now_add=True)
    modified_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "perm_groups"

    def __str__(self):
        """Return the string representation of this group.

        Returns the group's ``name`` attribute, which serves as the
        human-readable label for this group record. Used by admin views,
        debug output, and string formatting contexts.

        Args:
            self: The ``Group`` model instance.

        Returns:
            The ``name`` field value as a string, e.g. ``"admins"``.

        Raises:
            None: This method performs no I/O and raises no exceptions.
        """

    # ── lifecycle ─────────────────────────────────────────────────

    @classmethod
    async def get_or_create(cls, name: str, description: str = None) -> Group:  # ty: ignore[invalid-method-override]
        """Fetch an existing group by name or create a new one if it does not exist.

        Delegates to the parent class's ``get_or_create`` via ``super()`` to
        avoid infinite recursion, since this class overrides the method.
        If the group already exists, the existing record is returned without
        modification. If it does not exist, a new ``Group`` row is inserted.

        Args:
            name: The unique name for the group, e.g. ``"admins"`` or
                ``"editors"``. Used as the lookup key.
            description: An optional description of the group's purpose.
                Only used when creating a new group; ignored if the group
                already exists. Defaults to ``None``.

        Returns:
            The ``Group`` instance, either fetched from the database if it
            already existed or newly created.

        Raises:
            tortoise.exceptions.IntegrityError: If a concurrent insert causes
                a unique constraint violation on the ``name`` field.
        """
        # Use the super's get_or_create to avoid recursion
        group, _ = await super(cls, cls).get_or_create(
            name=name, defaults={"description": description}
        )
        return group

    # ── user membership ───────────────────────────────────────────

    async def add_user(self, user) -> None:
        """Add a user to this group, creating the membership if it does not exist.

        Uses ``get_or_create`` on the ``UserGroup`` join table to ensure
        idempotency: adding a user who is already a member is a no-op.
        The user argument can be either a model instance with an ``identity``
        attribute or a raw identity string.

        Args:
            user: The user to add, either a model instance with an
                ``identity`` attribute or a raw identity string.

        Returns:
            None. This method modifies database state but returns nothing.

        Raises:
            tortoise.exceptions.IntegrityError: If a concurrent insert causes
                a unique constraint violation on the ``UserGroup`` table.
        """
        user_id = user.identity if hasattr(user, "identity") else str(user)
        await UserGroup.get_or_create(group=self, user_id=user_id)

    async def remove_user(self, user) -> None:
        """Remove a user from this group by deleting the membership link.

        Deletes the ``UserGroup`` join row connecting the user to this group.
        If the user is not a member of the group, the operation is a no-op
        and no error is raised. The user argument can be either a model
        instance with an ``identity`` attribute or a raw identity string.

        Args:
            user: The user to remove, either a model instance with an
                ``identity`` attribute or a raw identity string.

        Returns:
            None. This method modifies database state but returns nothing.

        Raises:
            tortoise.exceptions.OperationalError: If the database delete
                operation fails due to a connection or schema issue.
        """
        user_id = user.identity if hasattr(user, "identity") else str(user)
        await UserGroup.filter(group=self, user_id=user_id).delete()

    async def has_user(self, user) -> bool:
        """Check whether a specific user is a member of this group.

        Queries the ``UserGroup`` join table to determine if a link exists
        between this group and the given user. The user argument can be
        either a model instance with an ``identity`` attribute or a raw
        identity string.

        Args:
            user: The user to check, either a model instance with an
                ``identity`` attribute or a raw identity string.

        Returns:
            ``True`` if the user is a member of this group, ``False``
            otherwise.

        Raises:
            tortoise.exceptions.OperationalError: If the database query fails
                due to a connection or schema issue.
        """
        user_id = user.identity if hasattr(user, "identity") else str(user)
        return await UserGroup.filter(group=self, user_id=user_id).exists()

    async def get_members(self) -> list[str]:
        """Return the identity strings of all users who are members of this group.

        Queries the ``UserGroup`` join table for all rows associated with
        this group and extracts the ``user_id`` field from each row. The
        result is returned as an unsorted list; callers should sort if
        deterministic ordering is required.

        Args:
            self: The ``Group`` model instance to query members for.

        Returns:
            A ``list`` of user identity strings (e.g. UUIDs or emails)
            representing all current group members. Returns an empty list
            if the group has no members.

        Raises:
            tortoise.exceptions.OperationalError: If the database query fails
                due to a connection or schema issue.
        """
        rows = await UserGroup.filter(group=self)
        return [r.user_id for r in rows]

    async def get_member_count(self) -> int:
        """Return the total number of users currently in this group.

        Performs a ``COUNT`` query on the ``UserGroup`` join table filtered
        by this group's primary key. This is more efficient than calling
        ``get_members()`` and taking the length, as it avoids fetching
        full row data from the database.

        Args:
            self: The ``Group`` model instance to count members for.

        Returns:
            An integer count of group members. Returns ``0`` if the group
            has no members.

        Raises:
            tortoise.exceptions.OperationalError: If the database query fails
                due to a connection or schema issue.
        """
        return await UserGroup.filter(group=self).count()

    # ── permission assignment ─────────────────────────────────────

    async def add_permissions(self, *names: str) -> None:
        """Assign one or more permissions to this group for inheritance by members.

        Each permission name is auto-defined via ``Permission.get_or_create``
        if it does not already exist, then a ``GroupPermission`` link row is
        created (also idempotently) between this group and the permission.
        Duplicate assignments are silently ignored.

        All group members will inherit these permissions when they next
        call ``load_permissions()``.

        Args:
            *names: One or more permission name strings to assign to the
                group, e.g. ``"edit_posts"``, ``"delete_comments"``.

        Returns:
            None. This method modifies database state but returns nothing.

        Raises:
            tortoise.exceptions.IntegrityError: If a concurrent insert causes
                a unique constraint violation on the ``GroupPermission`` table.
        """
        for name in names:
            perm, _ = await Permission.get_or_create(
                name=name,
                defaults={"description": None},
            )
            await GroupPermission.get_or_create(group=self, permission=perm)

    async def remove_permissions(self, *names: str) -> None:
        """Remove one or more permissions from this group.

        Looks up the ``Permission`` records matching the given names, then
        deletes the corresponding ``GroupPermission`` link rows for this
        group. Permissions that do not exist in the database are silently
        ignored. Group members will lose access to these permissions on
        their next call to ``load_permissions()``.

        Args:
            *names: One or more permission name strings to remove from the
                group, e.g. ``"edit_posts"``, ``"delete_comments"``.

        Returns:
            None. This method modifies database state but returns nothing.

        Raises:
            tortoise.exceptions.OperationalError: If the database delete
                operation fails due to a connection or schema issue.
        """
        perms = await Permission.filter(name__in=names)
        if perms:
            perm_ids = [p.id for p in perms]
            await GroupPermission.filter(
                group=self, permission_id__in=perm_ids
            ).delete()

    async def has_permission(self, name: str) -> bool:
        """Check whether this group has a specific permission assigned.

        Resolves the ``Permission`` record by name, then checks for the
        existence of a ``GroupPermission`` link row between that permission
        and this group. Returns ``False`` if the permission does not exist
        in the database at all.

        Args:
            name: The permission name to check, e.g. ``"edit_posts"``.

        Returns:
            ``True`` if the permission exists and is assigned to this group,
            ``False`` if the permission does not exist or is not assigned
            to this group.

        Raises:
            tortoise.exceptions.OperationalError: If the database query fails
                due to a connection or schema issue.
        """
        perm = await Permission.get_or_none(name=name)
        if perm is None:
            return False
        return await GroupPermission.filter(group=self, permission=perm).exists()

    async def get_permissions(self) -> list[str]:
        """Return all permission names currently assigned to this group.

        Queries the ``GroupPermission`` join table for this group and
        prefetches the related ``Permission`` records to extract permission
        names. The result is returned as a sorted list for deterministic
        output and deduplication.

        Args:
            self: The ``Group`` model instance to query permissions for.

        Returns:
            A sorted ``list`` of unique permission name strings assigned to
            this group. Returns an empty list if the group has no permissions.

        Raises:
            tortoise.exceptions.OperationalError: If the database query fails
                due to a connection or schema issue.
        """
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
    """Link table between a user (identified by identity string) and a Group.

    This is the join/through table that records group membership for users.
    Each row represents a single user's membership in a single group. The
    ``user_id`` field stores the user's identity string (not a foreign key
    to a user table), allowing any identity to be associated with groups
    regardless of the user model implementation.

    Attributes:
        user_id: The identity string of the user (e.g. UUID or email),
            indexed for efficient lookup by user.
        group: Foreign key reference to the ``Group`` model instance the
            user is a member of.

    Raises:
        None: No exceptions are raised by the class definition itself.
    """

    user_id = fields.CharField(max_length=255, db_index=True)
    group = fields.ForeignKeyField("models.Group", related_name="memberships")

    class Meta:
        table = "perm_user_groups"
        unique_together = (("user_id", "group"),)

    def __str__(self):
        """Return a human-readable string representation of this user-group membership.

        Formats the user identity and group ID as a set-membership expression
        for easy identification in admin views, debug output, and log messages.

        Args:
            self: The ``UserGroup`` model instance.

        Returns:
            A string in the format ``"{user_id} ∈ {group_id}"``,
            e.g. ``"user@example.com ∈ 5"``.

        Raises:
            None: This method performs no I/O and raises no exceptions.
        """


class GroupPermission(Model):
    """Link table between a Group and a Permission.

    This is the join/through table that records which permissions are
    assigned to which groups. Each row represents a single permission
    grant for a single group. All members of the group inherit the
    permission when they call ``load_permissions()``.

    Attributes:
        group: Foreign key reference to the ``Group`` model instance
            that receives the permission.
        permission: Foreign key reference to the ``Permission`` model
            instance being granted to the group.

    Raises:
        None: No exceptions are raised by the class definition itself.
    """

    group = fields.ForeignKeyField("models.Group", related_name="group_permissions")
    permission = fields.ForeignKeyField(
        "models.Permission", related_name="group_permissions"
    )

    class Meta:
        table = "perm_group_permissions"
        unique_together = (("group", "permission"),)

    def __str__(self):
        """Return a human-readable string representation of this group-permission link.

        Formats the group ID and permission ID as an arrow-separated pair
        for easy identification in admin views, debug output, and log
        messages.

        Args:
            self: The ``GroupPermission`` model instance.

        Returns:
            A string in the format ``"Group#{group_id} → #{permission_id}"``,
            e.g. ``"Group#5 → #42"``.

        Raises:
            None: This method performs no I/O and raises no exceptions.
        """
