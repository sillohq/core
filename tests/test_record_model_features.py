import inspect

import pytest
from tortoise import Tortoise, fields
from tortoise.exceptions import ConfigurationError

from sillo.record import Model

_has_global_fallback = "_enable_global_fallback" in inspect.signature(Tortoise.init).parameters


class RecordFeatureUser(Model):
    id = fields.IntField(pk=True)
    email = fields.CharField(max_length=255, unique=True)
    name = fields.CharField(max_length=255)
    metadata = fields.TextField(null=True)
    is_active = fields.BooleanField(default=True)
    plan = fields.CharField(max_length=50, default="free")
    tenant_id = fields.IntField(default=1)

    _casts = {"metadata": "json"}

    class Meta:
        table = "record_feature_users"

    def set_email_attribute(self, value):
        return value.strip().lower()

    def get_name_attribute(self, value):
        return value.title()

    @classmethod
    def scope_vip(cls, queryset):
        return queryset.filter(plan="vip")

    @classmethod
    def scope_active_status(cls, queryset):
        return queryset.filter(is_active=True)


@pytest.fixture(autouse=True)
async def record_db():
    init_kwargs = dict(
        db_url="sqlite://:memory:",
        modules={"models": ["tests.test_record_model_features"]},
    )
    if _has_global_fallback:
        init_kwargs["_enable_global_fallback"] = True
    await Tortoise.init(**init_kwargs)
    await Tortoise.generate_schemas()
    yield
    RecordFeatureUser._scope_registry = None
    try:
        await Tortoise._drop_databases()
    except ConfigurationError:
        pass
    try:
        await Tortoise.close_connections()
    except Exception:
        pass
    Tortoise._inited = False


async def test_accessors_mutators_and_casts_round_trip():
    user = await RecordFeatureUser.create(
        email="  ALICE@EXAMPLE.COM ",
        name="alice smith",
        metadata={"theme": "dark"},
    )

    assert user.email == "alice@example.com"
    assert user.name == "Alice Smith"
    assert user.metadata == {"theme": "dark"}
    assert user.to_dict()["metadata"] == {"theme": "dark"}

    fetched = await RecordFeatureUser.get(email="alice@example.com")
    assert fetched.metadata == {"theme": "dark"}
    assert fetched.name == "Alice Smith"


async def test_local_scopes_chain_on_querysets():
    await RecordFeatureUser.bulk_create(
        [
            {"email": "a@example.com", "name": "A", "plan": "vip"},
            {"email": "b@example.com", "name": "B", "plan": "free"},
            {
                "email": "c@example.com",
                "name": "C",
                "plan": "vip",
                "is_active": False,
            },
        ]
    )

    users = await RecordFeatureUser.all().vip().active_status().order_by("email")

    assert [user.email for user in users] == ["a@example.com"]


async def test_global_scopes_apply_and_can_be_bypassed():
    RecordFeatureUser.add_global_scope(lambda query: query.filter(tenant_id=7))
    await RecordFeatureUser.create(email="a@example.com", name="A", tenant_id=7)
    await RecordFeatureUser.create(email="b@example.com", name="B", tenant_id=8)

    assert await RecordFeatureUser.all().count() == 1
    assert await RecordFeatureUser.without_global_scopes().count() == 2


async def test_upsert_uses_database_conflict_update():
    created = await RecordFeatureUser.upsert(
        {
            "email": "upsert@example.com",
            "name": "First",
            "metadata": {"version": 1},
        },
        conflict_fields=["email"],
        update_fields=["name", "metadata"],
    )
    updated = await RecordFeatureUser.upsert(
        {
            "email": "upsert@example.com",
            "name": "second value",
            "metadata": {"version": 2},
        },
        conflict_fields=["email"],
        update_fields=["name", "metadata"],
    )

    assert created.email == "upsert@example.com"
    assert updated.name == "Second Value"
    assert updated.metadata == {"version": 2}
    assert await RecordFeatureUser.all().count() == 1
