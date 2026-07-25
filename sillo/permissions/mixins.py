from sillo.permissions.models import Group, GroupPermission, UserPermission


class PermissionMixin:
    """Mixin that adds permission checking and group-based permission inheritance to a user model.

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

    Attributes:
        is_active: Boolean flag indicating whether the user account is active.
            Satisfies static analysis; the real value comes from the concrete
            model (``UserBaseModel`` provides both fields).
        is_superuser: Boolean flag indicating superuser status. Superusers
            bypass all permission checks and always receive ``True``.

    Raises:
        None: No exceptions are raised directly by the mixin itself.
    """

    is_active = None  # Satisfies static analysis — real value comes from the
    is_superuser = None  # concrete model (UserBaseModel provides both fields).

    async def load_permissions(self) -> set[str]:
        """Load direct and group-inherited permissions from the database into an in-memory cache.

        Queries two database tables to build a unified set of permission names:
        first fetches all direct ``UserPermission`` rows for the current user,
        then resolves all group memberships and fetches the ``GroupPermission``
        rows for those groups. The union of both sets is stored as
        ``_perm_cache`` on the instance for fast subsequent lookups.

        Called automatically on login by ``load_user`` and
        ``verify_credentials``.  Also safe to call manually to refresh
        the cache after runtime permission changes.

        Args:
            self: The user model instance this mixin is attached to. Must
                have an ``identity`` attribute used as the user identifier.

        Returns:
            A ``set`` of permission name strings combining both direct
            assignments and group-inherited permissions.

        Raises:
            tortoise.exceptions.OperationalError: If the database query fails
                due to a connection or schema issue.
        """
        direct: set[str] = set()
        assignments = await UserPermission.filter(
            user_id=self.identity  # ty: ignore[unresolved-attribute]
        ).prefetch_related("permission")
        for a in assignments:
            direct.add(a.permission.name)

        # collect permissions inherited through groups
        inherited: set[str] = set()
        memberships = await Group.of_user(self)
        if memberships:
            group_ids = [g.id for g in memberships]
            gp_rows = await GroupPermission.filter(
                group_id__in=group_ids
            ).prefetch_related("permission")
            for gp in gp_rows:
                inherited.add(gp.permission.name)

        cache = direct | inherited
        object.__setattr__(self, "_perm_cache", cache)
        return cache

    def has_permission(self, permission: str) -> bool:
        """Check whether the user holds a specific permission from the cached set.

        Performs a fast in-memory lookup against the ``_perm_cache`` attribute
        previously populated by ``load_permissions()``. The method short-circuits
        for inactive users (always ``False``) and superusers (always ``True``)
        before consulting the cache.

        Checks both direct assignments and group-inherited permissions since
        both are merged into the cache during ``load_permissions()``. If the
        cache has not been loaded yet, returns ``False`` rather than triggering
        a database query.

        Args:
            permission: The name of the permission to check, e.g.
                ``"edit_posts"`` or ``"delete_comments"``.

        Returns:
            ``True`` if the user is a superuser, or if the user is active and
            the permission exists in the cached set. ``False`` if the user is
            inactive, the cache is empty, or the permission is not found.

        Raises:
            None: This method performs no I/O and raises no exceptions.
        """
        if not self.is_active:
            return False
        if self.is_superuser:
            return True
        cache = getattr(self, "_perm_cache", None)
        return cache is not None and permission in cache

    def has_perm(self, perm: str) -> bool:
        """Check whether the user holds a specific permission (alias for ``has_permission``).

        This method exists solely to satisfy the ``UserProtocol`` interface
        contract, which expects a ``has_perm`` method. It delegates directly
        to ``has_permission()`` with no additional logic or side effects.

        Callers should prefer ``has_permission()`` for clarity, but both
        methods are functionally identical and share the same caching
        behavior and short-circuit logic for superusers and inactive users.

        Args:
            perm: The name of the permission to check, e.g.
                ``"edit_posts"`` or ``"delete_comments"``.

        Returns:
            ``True`` if the user holds the permission, ``False`` otherwise.
            Behavior is identical to ``has_permission(perm)``.

        Raises:
            None: This method performs no I/O and raises no exceptions.
        """
        return self.has_permission(perm)

    # ── group introspection ───────────────────────────────────────

    async def get_groups(self) -> list[str]:
        """Return the names of all groups the current user belongs to.

        Delegates to ``Group.names_of_user()`` to query the ``UserGroup``
        join table and resolve the associated ``Group`` records. The
        returned list is sorted alphabetically for deterministic output.

        This method performs a database query each time it is called;
        results are not cached. For repeated checks, consider caching
        the result at the call site.

        Args:
            self: The user model instance this mixin is attached to. Must
                have an ``identity`` attribute used as the user identifier.

        Returns:
            A sorted ``list`` of group name strings the user belongs to.
            Returns an empty list if the user has no group memberships.

        Raises:
            tortoise.exceptions.OperationalError: If the database query fails
                due to a connection or schema issue.
        """
        return await Group.names_of_user(self)

    async def is_in_group(self, name: str) -> bool:
        """Check whether the current user is a member of a specific group.

        Retrieves the full list of group names the user belongs to via
        ``get_groups()`` and tests whether the given name is present.
        The comparison is case-sensitive and requires an exact string match.

        Note that this method performs a database query on each invocation
        since ``get_groups()`` is not cached. Avoid calling this in tight
        loops; prefer ``get_groups()`` once and checking membership locally.

        Args:
            name: The exact name of the group to check membership for,
                e.g. ``"admins"`` or ``"editors"``.

        Returns:
            ``True`` if the user belongs to the named group, ``False``
            otherwise (including when the group does not exist).

        Raises:
            tortoise.exceptions.OperationalError: If the underlying database
                query in ``get_groups()`` fails.
        """
        groups = await self.get_groups()
        return name in groups

    async def get_group_permissions(self) -> set[str]:
        """Return all permission names the current user inherits through group membership.

        Queries the ``Group`` table to find all groups the user belongs to,
        then fetches all ``GroupPermission`` rows for those groups and
        extracts the associated permission names. Unlike ``load_permissions()``,
        this method does NOT include direct user permissions and does NOT
        populate the ``_perm_cache``.

        This is useful for auditing or displaying which permissions a user
        receives specifically from their group memberships, separate from
        any directly assigned permissions.

        Args:
            self: The user model instance this mixin is attached to. Must
                have an ``identity`` attribute used as the user identifier.

        Returns:
            A ``set`` of permission name strings inherited through groups.
            Returns an empty set if the user belongs to no groups or if
            none of their groups have permissions assigned.

        Raises:
            tortoise.exceptions.OperationalError: If the database query fails
                due to a connection or schema issue.
        """
        memberships = await Group.of_user(self)
        if not memberships:
            return set()
        group_ids = [g.id for g in memberships]
        gp_rows = await GroupPermission.filter(group_id__in=group_ids).prefetch_related(
            "permission"
        )
        return {gp.permission.name for gp in gp_rows}
