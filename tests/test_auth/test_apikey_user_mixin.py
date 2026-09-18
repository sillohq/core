"""Coverage for ``ApiKeyUserMixin`` -- nothing exercised it directly."""

import inspect

import pytest
from tortoise import Tortoise
from tortoise.exceptions import ConfigurationError

from sillo.auth.apikey.mixins import ApiKeyUserMixin
from sillo.auth.apikey.models import ApiKey

_has_global_fallback = (
    "_enable_global_fallback" in inspect.signature(Tortoise.init).parameters
)


@pytest.fixture(autouse=True)
async def apikey_db():
    init_kwargs = dict(
        db_url="sqlite://:memory:",
        modules={"models": ["sillo.auth.apikey.models"]},
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


class FakeUser(ApiKeyUserMixin):
    def __init__(self, identity: int):
        self.identity = identity


class TestCreateApiKey:
    async def test_creates_a_key_scoped_to_the_user(self):
        user = FakeUser(1)
        full_key, apikey = await user.create_api_key("ci", scopes=["read"])
        assert full_key.startswith("sillo_")
        assert apikey.user_id == 1
        assert apikey.name == "ci"

    async def test_prefix_is_configurable(self):
        user = FakeUser(1)
        full_key, _ = await user.create_api_key("ci", prefix="acme")
        assert full_key.startswith("acme_")


class TestGetApiKeys:
    async def test_returns_only_this_users_keys(self):
        user = FakeUser(1)
        other = FakeUser(2)
        await user.create_api_key("a")
        await user.create_api_key("b")
        await other.create_api_key("c")

        keys = await user.get_api_keys()

        assert {k.name for k in keys} == {"a", "b"}


class TestRevokeAllApiKeys:
    async def test_revokes_every_active_key_for_this_user(self):
        user = FakeUser(1)
        theirs_user = FakeUser(2)
        await user.create_api_key("a")
        await user.create_api_key("b")
        _, theirs = await theirs_user.create_api_key("c")

        count = await user.revoke_all_api_keys()

        assert count == 2
        for key in await ApiKey.filter(user_id=1).all():
            assert key.is_active is False
        assert (await ApiKey.get(id=theirs.id)).is_active is True


class TestRevokeApiKey:
    async def test_revokes_a_matching_key_and_returns_true(self):
        user = FakeUser(1)
        _, apikey = await user.create_api_key("a")

        assert await user.revoke_api_key(apikey.id) is True
        assert (await ApiKey.get(id=apikey.id)).is_active is False

    async def test_returns_false_when_no_key_matches(self):
        user = FakeUser(1)
        assert await user.revoke_api_key(999) is False

    async def test_does_not_revoke_another_users_key(self):
        theirs_user = FakeUser(2)
        _, theirs = await theirs_user.create_api_key("c")
        user = FakeUser(1)

        assert await user.revoke_api_key(theirs.id) is False
        assert (await ApiKey.get(id=theirs.id)).is_active is True
