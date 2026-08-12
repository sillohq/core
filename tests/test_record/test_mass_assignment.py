"""Regression tests for the mass-assignment finding reported 2026-08-12.

``update_from_dict`` applied any key naming a field, so a dict taken straight
from a request body could set columns the caller was never meant to reach —
the ones deciding what they are allowed to do above all. The behaviour is
unchanged for a model that says nothing, because plenty of callers pass a dict
they built themselves; ``fillable``, ``guarded`` and ``only=`` are how a model
narrows it.
"""

import inspect

import pytest
from tortoise import Tortoise, fields
from tortoise.exceptions import ConfigurationError

from sillo.record import Model

_has_global_fallback = (
    "_enable_global_fallback" in inspect.signature(Tortoise.init).parameters
)


class OpenUser(Model):
    """States nothing, so every field stays writable."""

    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=255)
    is_admin = fields.BooleanField(default=False)

    class Meta:
        table = "mass_assign_open_users"


class GuardedUser(Model):
    """Names what must never be written."""

    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=255)
    is_admin = fields.BooleanField(default=False)
    credits = fields.IntField(default=0)

    guarded = ("is_admin", "credits")

    class Meta:
        table = "mass_assign_guarded_users"


class FillableUser(Model):
    """Names the only fields that may be written."""

    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=255)
    is_admin = fields.BooleanField(default=False)

    fillable = ("name",)

    class Meta:
        table = "mass_assign_fillable_users"


@pytest.fixture(autouse=True)
async def record_db():
    init_kwargs = dict(
        db_url="sqlite://:memory:",
        modules={"models": ["tests.test_record.test_mass_assignment"]},
    )
    if _has_global_fallback:
        init_kwargs["_enable_global_fallback"] = True
    await Tortoise.init(**init_kwargs)
    await Tortoise.generate_schemas()
    yield
    try:
        await Tortoise._drop_databases()
    except ConfigurationError:
        pass
    try:
        await Tortoise.close_connections()
    except Exception:
        pass


class TestTheDefaultIsUnchanged:
    async def test_every_field_is_writable_when_nothing_is_stated(self):
        user = await OpenUser.create(name="Ada", is_admin=False)

        await user.update_from_dict({"name": "Ada L", "is_admin": True})

        assert user.name == "Ada L"
        assert user.is_admin is True

    async def test_unknown_keys_are_still_ignored(self):
        user = await OpenUser.create(name="Ada")

        await user.update_from_dict({"name": "Ada L", "not_a_field": "x"})

        assert user.name == "Ada L"
        assert not hasattr(user, "not_a_field")


class TestGuarded:
    async def test_a_guarded_field_is_not_written(self):
        user = await GuardedUser.create(name="Ada", is_admin=False, credits=0)

        await user.update_from_dict(
            {"name": "Ada L", "is_admin": True, "credits": 9999}
        )

        assert user.name == "Ada L"
        assert user.is_admin is False
        assert user.credits == 0

    async def test_it_survives_a_reload(self):
        user = await GuardedUser.create(name="Ada")
        await user.update_from_dict({"is_admin": True})

        reloaded = await GuardedUser.get(id=user.id)
        assert reloaded.is_admin is False


class TestFillable:
    async def test_only_named_fields_are_written(self):
        user = await FillableUser.create(name="Ada", is_admin=False)

        await user.update_from_dict({"name": "Ada L", "is_admin": True})

        assert user.name == "Ada L"
        assert user.is_admin is False

    async def test_fillable_wins_over_guarded(self):
        # `fillable` already says what is allowed, so `guarded` is not
        # consulted — stating both must not widen what fillable permits.
        class BothUser(FillableUser):
            guarded = ()

            class Meta:
                abstract = True

        assert "is_admin" not in BothUser.mass_assignable_fields()


class TestOnlyOverridesPerCall:
    async def test_only_narrows_an_otherwise_open_model(self):
        user = await OpenUser.create(name="Ada", is_admin=False)

        await user.update_from_dict(
            {"name": "Ada L", "is_admin": True}, only=["name"]
        )

        assert user.name == "Ada L"
        assert user.is_admin is False

    async def test_only_cannot_widen_past_the_models_fields(self):
        assert OpenUser.mass_assignable_fields(only=["name", "nope"]) == {"name"}

    async def test_an_empty_only_writes_nothing(self):
        user = await OpenUser.create(name="Ada")

        await user.update_from_dict({"name": "changed"}, only=[])

        assert user.name == "Ada"
