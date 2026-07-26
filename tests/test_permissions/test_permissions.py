from __future__ import annotations

import inspect

import pytest

from tortoise import Tortoise
from tortoise.exceptions import ConfigurationError

from sillo.permissions import (
    Permission,
    PermissionMixin,
    Group,
    GroupPermission,
    UserGroup,
    UserPermission,
)
from sillo.users.base import UserBaseModel
from sillo.users.managers import UserManager
from sillo.users.password import make_password

_has_global_fallback = "_enable_global_fallback" in inspect.signature(Tortoise.init).parameters


class PermUser(PermissionMixin, UserBaseModel):
    objects = UserManager()

    class Meta:
        table = "perm_users"


class NoPermUser(UserBaseModel):
    objects = UserManager()

    class Meta:
        table = "no_perm_users"


# ── helpers ─────────────────────────────────────────────────────────

@pytest.fixture
async def db():
    init_kwargs = dict(
        db_url="sqlite://:memory:",
        modules={
            "models": [
                "tests.test_permissions.test_permissions",
                "sillo.permissions.models",
            ]
        },
    )
    if _has_global_fallback:
        init_kwargs["_enable_global_fallback"] = True
    await Tortoise.init(**init_kwargs)
    await Tortoise.generate_schemas(safe=True)
    yield
    try:
        await Tortoise._drop_databases()
    except ConfigurationError:
        pass
    try:
        await Tortoise.close_connections()
    except Exception:
        pass


async def make_user(db, **kw):
    return await PermUser.create(
        email=kw.get("email", "a@x.com"),
        username=kw.get("username", "a"),
        password=make_password("secret"),
        **{k: v for k, v in kw.items() if k not in ("email", "username")},
    )


# ═══════════════════════════════════════════════════════════════════════
# Permission model — define / assign / revoke / query
# ═══════════════════════════════════════════════════════════════════════

class TestPermissionDefine:
    async def test_creates_permission(self, db):
        p = await Permission.define("view_posts", "Can view posts")
        assert p.name == "view_posts"
        assert p.description == "Can view posts"

    async def test_is_idempotent(self, db):
        p1 = await Permission.define("view_posts")
        p2 = await Permission.define("view_posts")
        assert p2.id == p1.id


class TestPermissionAssignRevoke:
    async def test_assign_single(self, db):
        u = await make_user(db)
        await Permission.assign(u, "view_posts")
        names = await Permission.of(u)
        assert names == ["view_posts"]

    async def test_assign_multiple(self, db):
        u = await make_user(db)
        await Permission.assign(u, "read", "write", "delete")
        names = await Permission.of(u)
        assert names == ["delete", "read", "write"]

    async def test_assign_auto_defines(self, db):
        u = await make_user(db)
        await Permission.assign(u, "never_seen")
        assert await Permission.get_or_none(name="never_seen") is not None

    async def test_revoke_single(self, db):
        u = await make_user(db)
        await Permission.assign(u, "a", "b", "c")
        await Permission.revoke(u, "b")
        names = await Permission.of(u)
        assert names == ["a", "c"]

    async def test_revoke_multiple(self, db):
        u = await make_user(db)
        await Permission.assign(u, "a", "b", "c", "d")
        await Permission.revoke(u, "b", "d")
        names = await Permission.of(u)
        assert names == ["a", "c"]

    async def test_revoke_nonexistent_does_not_error(self, db):
        u = await make_user(db)
        await Permission.revoke(u, "nobody_has_this")  # should not raise

    async def test_assign_via_identity_string(self, db):
        u = await make_user(db)
        await Permission.assign(u.identity, "by_string")
        names = await Permission.of(u)
        assert names == ["by_string"]

    async def test_has_direct(self, db):
        u = await make_user(db)
        await Permission.assign(u, "ping")
        assert await Permission.has(u, "ping") is True
        assert await Permission.has(u, "pong") is False

    async def test_holders(self, db):
        u1 = await make_user(db, email="one@x.com", username="one")
        u2 = await make_user(db, email="two@x.com", username="two")
        await Permission.assign(u1, "admin")
        await Permission.assign(u2, "admin")
        holders = await Permission.holders("admin")
        assert sorted(holders) == sorted([u1.identity, u2.identity])


# ═══════════════════════════════════════════════════════════════════════
# PermissionMixin — has_permission / has_perm / cache
# ═══════════════════════════════════════════════════════════════════════

class TestPermissionMixin:
    async def test_has_direct_permission(self, db):
        u = await make_user(db)
        await Permission.assign(u, "view_posts")
        await u.load_permissions()
        assert u.has_permission("view_posts") is True
        assert u.has_permission("edit_posts") is False

    async def test_superuser_bypass(self, db):
        u = await make_user(db, is_superuser=True)
        # no assignments needed
        await u.load_permissions()
        assert u.has_permission("anything") is True
        assert u.has_perm("anything") is True

    async def test_inactive_user_denied(self, db):
        u = await make_user(db, is_active=False)
        await Permission.assign(u, "view_posts")
        await u.load_permissions()
        assert u.has_permission("view_posts") is False

    async def test_cache_reflects_revoke(self, db):
        u = await make_user(db)
        await Permission.assign(u, "perm_a", "perm_b")
        perms = await u.load_permissions()
        assert perms == {"perm_a", "perm_b"}

        await Permission.revoke(u, "perm_a")
        perms2 = await u.load_permissions()
        assert perms2 == {"perm_b"}
        assert u.has_permission("perm_a") is False
        assert u.has_permission("perm_b") is True

    async def test_has_perm_alias(self, db):
        u = await make_user(db)
        await Permission.assign(u, "some_perm")
        await u.load_permissions()
        assert u.has_perm("some_perm") is True
        assert u.has_perm("missing") is False

    async def test_no_mixin_fallback(self, db):
        u = await NoPermUser.create(
            email="fall@x.com", username="fallback",
            password=make_password("secret"),
        )
        assert not hasattr(u, "load_permissions")
        # UserBaseModel's has_perm only checks superuser + _permissions list
        assert u.has_perm("anything") is False

    async def test_end_to_end_via_load_user(self, db):
        u = await make_user(db)
        await Permission.assign(u, "e2e_perm")
        loaded = await PermUser.load_user(str(u.id))
        assert loaded is not None
        assert loaded.has_permission("e2e_perm") is True

    async def test_multiple_direct_permissions(self, db):
        u = await make_user(db)
        await Permission.assign(u, "read", "write", "delete")
        await u.load_permissions()
        assert u.has_permission("read") is True
        assert u.has_permission("write") is True
        assert u.has_permission("delete") is True
        assert u.has_permission("admin") is False


# ═══════════════════════════════════════════════════════════════════════
# Group model — create / membership
# ═══════════════════════════════════════════════════════════════════════

class TestGroupCreate:
    async def test_create_group(self, db):
        g = await Group.get_or_create("editors")
        assert g.name == "editors"
        assert g.description is None

    async def test_create_with_description(self, db):
        g = await Group.get_or_create("admins", "System administrators")
        assert g.description == "System administrators"

    async def test_create_idempotent(self, db):
        g1 = await Group.get_or_create("moderators")
        g2 = await Group.get_or_create("moderators")
        assert g2.id == g1.id


class TestGroupMembership:
    async def test_add_user(self, db):
        u = await make_user(db)
        g = await Group.get_or_create("editors")
        await g.add_user(u)
        assert await g.has_user(u) is True

    async def test_add_user_idempotent(self, db):
        u = await make_user(db)
        g = await Group.get_or_create("editors")
        await g.add_user(u)
        await g.add_user(u)  # second add should not raise
        assert await g.get_member_count() == 1

    async def test_remove_user(self, db):
        u = await make_user(db)
        g = await Group.get_or_create("editors")
        await g.add_user(u)
        await g.remove_user(u)
        assert await g.has_user(u) is False

    async def test_remove_nonexistent(self, db):
        u = await make_user(db)
        g = await Group.get_or_create("editors")
        await g.remove_user(u)  # should not raise

    async def test_get_members(self, db):
        u1 = await make_user(db, email="a@x.com", username="a")
        u2 = await make_user(db, email="b@x.com", username="b")
        g = await Group.get_or_create("team")
        await g.add_user(u1)
        await g.add_user(u2)
        members = await g.get_members()
        assert sorted(members) == sorted([u1.identity, u2.identity])

    async def test_member_count(self, db):
        u1 = await make_user(db, email="a@x.com", username="a")
        u2 = await make_user(db, email="b@x.com", username="b")
        g = await Group.get_or_create("team")
        assert await g.get_member_count() == 0
        await g.add_user(u1)
        assert await g.get_member_count() == 1
        await g.add_user(u2)
        assert await g.get_member_count() == 2

    async def test_of_user(self, db):
        u = await make_user(db)
        g1 = await Group.get_or_create("group_a")
        g2 = await Group.get_or_create("group_b")
        await g1.add_user(u)
        await g2.add_user(u)
        groups = await Group.of_user(u)
        assert sorted([g.name for g in groups]) == ["group_a", "group_b"]

    async def test_names_of_user(self, db):
        u = await make_user(db)
        g1 = await Group.get_or_create("alpha")
        g2 = await Group.get_or_create("beta")
        await g1.add_user(u)
        await g2.add_user(u)
        names = await Group.names_of_user(u)
        assert names == ["alpha", "beta"]

    async def test_add_user_by_identity_string(self, db):
        u = await make_user(db)
        g = await Group.get_or_create("editors")
        await g.add_user(u.identity)
        assert await g.has_user(u.identity) is True


# ═══════════════════════════════════════════════════════════════════════
# Group permissions — add / remove / query
# ═══════════════════════════════════════════════════════════════════════

class TestGroupPermissions:
    async def test_add_single(self, db):
        g = await Group.get_or_create("editors")
        await g.add_permissions("edit_posts")
        perms = await g.get_permissions()
        assert perms == ["edit_posts"]

    async def test_add_multiple(self, db):
        g = await Group.get_or_create("editors")
        await g.add_permissions("read", "write", "delete")
        perms = await g.get_permissions()
        assert perms == ["delete", "read", "write"]

    async def test_add_auto_defines_permission(self, db):
        g = await Group.get_or_create("editors")
        await g.add_permissions("brand_new_perm")
        assert await Permission.get_or_none(name="brand_new_perm") is not None

    async def test_remove_single(self, db):
        g = await Group.get_or_create("editors")
        await g.add_permissions("a", "b", "c")
        await g.remove_permissions("b")
        perms = await g.get_permissions()
        assert perms == ["a", "c"]

    async def test_remove_multiple(self, db):
        g = await Group.get_or_create("editors")
        await g.add_permissions("a", "b", "c", "d")
        await g.remove_permissions("b", "d")
        perms = await g.get_permissions()
        assert perms == ["a", "c"]

    async def test_remove_nonexistent(self, db):
        g = await Group.get_or_create("editors")
        await g.remove_permissions("nothing")  # should not raise

    async def test_has_permission(self, db):
        g = await Group.get_or_create("editors")
        await g.add_permissions("edit")
        assert await g.has_permission("edit") is True
        assert await g.has_permission("delete") is False

    async def test_add_idempotent(self, db):
        g = await Group.get_or_create("editors")
        await g.add_permissions("x")
        await g.add_permissions("x")  # second add — should be noop
        perms = await g.get_permissions()
        assert perms == ["x"]

    async def test_permission_of_group_via_model(self, db):
        g = await Group.get_or_create("editors")
        await g.add_permissions("read", "write")
        names = await Permission.of_group(g)
        assert names == ["read", "write"]


# ═══════════════════════════════════════════════════════════════════════
# Group-inherited permissions — user gets permissions via groups
# ═══════════════════════════════════════════════════════════════════════

class TestGroupInheritedPermissions:
    async def test_user_inherits_group_permissions(self, db):
        u = await make_user(db)
        g = await Group.get_or_create("editors")
        await g.add_user(u)
        await g.add_permissions("edit_posts", "view_drafts")
        await u.load_permissions()

        assert u.has_permission("edit_posts") is True
        assert u.has_permission("view_drafts") is True
        assert u.has_permission("delete_posts") is False

    async def test_user_inherits_from_multiple_groups(self, db):
        u = await make_user(db)
        g1 = await Group.get_or_create("readers")
        g2 = await Group.get_or_create("editors")
        await g1.add_user(u)
        await g2.add_user(u)
        await g1.add_permissions("read")
        await g2.add_permissions("write", "delete")
        await u.load_permissions()

        assert u.has_permission("read") is True
        assert u.has_permission("write") is True
        assert u.has_permission("delete") is True

    async def test_direct_and_group_permissions_combine(self, db):
        u = await make_user(db)
        g = await Group.get_or_create("editors")
        await g.add_user(u)
        await g.add_permissions("edit_posts")
        await Permission.assign(u, "view_posts")  # direct
        await u.load_permissions()

        assert u.has_permission("edit_posts") is True   # from group
        assert u.has_permission("view_posts") is True    # direct
        assert u.has_permission("delete") is False

    async def test_group_perm_revoke_removes_from_user_cache(self, db):
        u = await make_user(db)
        g = await Group.get_or_create("editors")
        await g.add_user(u)
        await g.add_permissions("perm_x")
        await u.load_permissions()
        assert u.has_permission("perm_x") is True

        await g.remove_permissions("perm_x")
        await u.load_permissions()
        assert u.has_permission("perm_x") is False

    async def test_user_removed_from_group_loses_permissions(self, db):
        u = await make_user(db)
        g = await Group.get_or_create("editors")
        await g.add_user(u)
        await g.add_permissions("secret")
        await u.load_permissions()
        assert u.has_permission("secret") is True

        await g.remove_user(u)
        await u.load_permissions()
        assert u.has_permission("secret") is False

    async def test_multiple_users_in_group(self, db):
        u1 = await make_user(db, email="a@x.com", username="a")
        u2 = await make_user(db, email="b@x.com", username="b")
        g = await Group.get_or_create("team")
        await g.add_user(u1)
        await g.add_user(u2)
        await g.add_permissions("shared_perm")

        await u1.load_permissions()
        await u2.load_permissions()
        assert u1.has_permission("shared_perm") is True
        assert u2.has_permission("shared_perm") is True

    async def test_group_permissions_not_leaked_to_non_members(self, db):
        u1 = await make_user(db, email="a@x.com", username="a")
        u2 = await make_user(db, email="b@x.com", username="b")
        g = await Group.get_or_create("vip")
        await g.add_user(u1)
        await g.add_permissions("vip_access")

        await u1.load_permissions()
        await u2.load_permissions()
        assert u1.has_permission("vip_access") is True
        assert u2.has_permission("vip_access") is False

    async def test_superuser_in_group_still_bypasses(self, db):
        u = await make_user(db, is_superuser=True)
        g = await Group.get_or_create("editors")
        await g.add_user(u)
        # no group permissions assigned
        await u.load_permissions()
        assert u.has_permission("anything") is True

    async def test_inactive_in_group_still_denied(self, db):
        u = await make_user(db, is_active=False)
        g = await Group.get_or_create("editors")
        await g.add_user(u)
        await g.add_permissions("anything")
        await u.load_permissions()
        assert u.has_permission("anything") is False

    async def test_overlapping_permissions_deduped(self, db):
        u = await make_user(db)
        g = await Group.get_or_create("editors")
        await g.add_user(u)
        await Permission.assign(u, "read")       # direct
        await g.add_permissions("read")           # same perm via group
        perms = await u.load_permissions()
        assert perms == {"read"}  # no dupe


# ═══════════════════════════════════════════════════════════════════════
# PermissionMixin — group introspection
# ═══════════════════════════════════════════════════════════════════════

class TestMixinGroupIntrospection:
    async def test_get_groups(self, db):
        u = await make_user(db)
        g1 = await Group.get_or_create("alpha")
        g2 = await Group.get_or_create("beta")
        await g1.add_user(u)
        await g2.add_user(u)
        groups = await u.get_groups()
        assert sorted(groups) == ["alpha", "beta"]

    async def test_get_groups_empty(self, db):
        u = await make_user(db)
        groups = await u.get_groups()
        assert groups == []

    async def test_is_in_group(self, db):
        u = await make_user(db)
        g = await Group.get_or_create("editors")
        await g.add_user(u)
        assert await u.is_in_group("editors") is True
        assert await u.is_in_group("admins") is False

    async def test_get_group_permissions(self, db):
        u = await make_user(db)
        g = await Group.get_or_create("editors")
        await g.add_user(u)
        await g.add_permissions("a", "b")
        gp = await u.get_group_permissions()
        assert gp == {"a", "b"}

    async def test_get_group_permissions_empty(self, db):
        u = await make_user(db)
        gp = await u.get_group_permissions()
        assert gp == set()

    async def test_get_group_permissions_excludes_direct(self, db):
        u = await make_user(db)
        g = await Group.get_or_create("editors")
        await g.add_user(u)
        await g.add_permissions("from_group")
        await Permission.assign(u, "direct_perm")
        gp = await u.get_group_permissions()
        assert gp == {"from_group"}


# ═══════════════════════════════════════════════════════════════════════
# Edge cases
# ═══════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    async def test_empty_group_has_no_permissions(self, db):
        g = await Group.get_or_create("lonely")
        perms = await g.get_permissions()
        assert perms == []

    async def test_user_with_no_groups_and_no_perms(self, db):
        u = await make_user(db)
        await u.load_permissions()
        assert u.has_permission("anything") is False
        groups = await u.get_groups()
        assert groups == []
