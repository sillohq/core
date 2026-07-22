class PermissionMixin:
    """Adds ``has_permission`` / ``has_perm`` to a user model.

    Resolves permissions from **two** sources:
    1. Direct user–permission assignments (``Permission.assign``).
    2. Group-inherited permissions — any permission assigned to a group
       the user belongs to is automatically available.

    Mix this into your user class **first** in the base list so its
    methods take precedence over ``UserBaseModel``::

        class Account(PermissionMixin, UserBaseModel):
            ...

    Permission caching is automatic: ``UserBaseModel.load_user`` and
    ``UserBaseModel.verify_credentials`` already call ``load_permissions()``
    when the mixin is present.  Handlers just call ``user.has_permission(…)``.
    """

    is_active = None  # Satisfies static analysis — real value comes from the
    is_superuser = None  # concrete model (UserBaseModel provides both fields).

    async def load_permissions(self) -> set[str]:
        """Load direct + group-inherited permissions from DB into cache.

        Called automatically on login by ``load_user`` and
        ``verify_credentials``.  Also safe to call manually to refresh.
        """
        from sillo.permissions.models import UserPermission, Group, GroupPermission

        direct: set[str] = set()
        assignments = await UserPermission.filter(
            user_id=self.identity
        ).prefetch_related("permission")
        for a in assignments:
            direct.add(a.permission.name)

        # collect permissions inherited through groups
        inherited: set[str] = set()
        memberships = await Group.of_user(self)
        if memberships:
            group_ids = [g.id for g in memberships]
            gp_rows = (
                await GroupPermission.filter(group_id__in=group_ids)
                .prefetch_related("permission")
            )
            for gp in gp_rows:
                inherited.add(gp.permission.name)

        cache = direct | inherited
        object.__setattr__(self, "_perm_cache", cache)
        return cache

    def has_permission(self, permission: str) -> bool:
        """Check whether the user has *permission* (reads from cache).

        Checks both direct assignments and group-inherited permissions.
        Returns ``True`` for superusers, ``False`` for inactive users.
        """
        if not self.is_active:
            return False
        if self.is_superuser:
            return True
        cache = getattr(self, "_perm_cache", None)
        return cache is not None and permission in cache

    def has_perm(self, perm: str) -> bool:
        """Alias for :meth:`has_permission` (satisfies ``UserProtocol``)."""
        return self.has_permission(perm)

    # ── group introspection ───────────────────────────────────────

    async def get_groups(self) -> list[str]:
        """Return names of all groups this user belongs to."""
        from sillo.permissions.models import Group

        return await Group.names_of_user(self)

    async def is_in_group(self, name: str) -> bool:
        """Check if the user is a member of the group *name*."""
        groups = await self.get_groups()
        return name in groups

    async def get_group_permissions(self) -> set[str]:
        """Return all permission names inherited through group membership."""
        from sillo.permissions.models import Group, GroupPermission

        memberships = await Group.of_user(self)
        if not memberships:
            return set()
        group_ids = [g.id for g in memberships]
        gp_rows = (
            await GroupPermission.filter(group_id__in=group_ids)
            .prefetch_related("permission")
        )
        return {gp.permission.name for gp in gp_rows}
