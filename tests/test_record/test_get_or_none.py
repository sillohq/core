"""``Model.get_or_none`` is Tortoise's: chainable, and only ``None`` for no row.

It used to be a coroutine that swallowed every exception, so
``await Model.get_or_none(...).select_related(...)`` failed and real errors
came back as ``None`` (sillohq/core#464).
"""

import inspect

import pytest
from tortoise import Tortoise, fields
from tortoise.exceptions import ConfigurationError, MultipleObjectsReturned
from tortoise.expressions import Q

from sillo.record import Model

_has_global_fallback = (
    "_enable_global_fallback" in inspect.signature(Tortoise.init).parameters
)


class LookupTeam(Model):
    id = fields.IntField(primary_key=True)
    name = fields.CharField(max_length=50)

    class Meta:
        table = "lookup_teams"


class LookupPlayer(Model):
    id = fields.IntField(primary_key=True)
    name = fields.CharField(max_length=50)
    team = fields.ForeignKeyField(
        "models.LookupTeam", related_name="players", null=True
    )

    class Meta:
        table = "lookup_players"


@pytest.fixture(autouse=True)
async def record_db():
    init_kwargs = {
        "db_url": "sqlite://:memory:",
        "modules": {"models": ["tests.test_record.test_get_or_none"]},
    }
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


class TestLookup:
    async def test_returns_the_row(self):
        team = await LookupTeam.create(name="Core")

        found = await LookupTeam.get_or_none(name="Core")

        assert found is not None and found.id == team.id

    async def test_returns_none_when_there_is_no_row(self):
        assert await LookupTeam.get_or_none(name="nobody") is None

    async def test_accepts_q_objects(self):
        await LookupTeam.create(name="Core")

        assert await LookupTeam.get_or_none(Q(name="Core") | Q(name="x")) is not None

    async def test_soft_deleted_rows_are_found_like_every_other_lookup(self):
        team = await LookupTeam.create(name="Core")
        await team.soft_delete()

        assert await LookupTeam.get_or_none(name="Core") is not None
        assert (
            await LookupTeam.get_or_none(name="Core").filter(deleted_at__isnull=True)
            is None
        )


class TestChaining:
    async def test_select_related(self):
        team = await LookupTeam.create(name="Core")
        await LookupPlayer.create(name="Ada", team=team)

        player = await LookupPlayer.get_or_none(name="Ada").select_related("team")

        assert player is not None
        assert player.team.name == "Core"

    async def test_prefetch_related(self):
        team = await LookupTeam.create(name="Core")
        await LookupPlayer.create(name="Ada", team=team)
        await LookupPlayer.create(name="Bob", team=team)

        found = await LookupTeam.get_or_none(name="Core").prefetch_related("players")

        assert sorted(p.name for p in found.players) == ["Ada", "Bob"]

    async def test_a_chained_miss_is_none(self):
        assert await LookupPlayer.get_or_none(name="x").select_related("team") is None

    async def test_values_and_only(self):
        await LookupTeam.create(name="Core")

        found = await LookupTeam.get_or_none(name="Core").only("id", "name")

        assert found is not None and found.name == "Core"

    async def test_can_be_gathered_with_other_awaitables(self):
        import asyncio

        await LookupTeam.create(name="Core")

        found, missing = await asyncio.gather(
            LookupTeam.get_or_none(name="Core"), LookupTeam.get_or_none(name="x")
        )

        assert found is not None and missing is None


class TestErrorsAreNotNone:
    async def test_two_matching_rows_raise(self):
        await LookupTeam.create(name="Twin")
        await LookupTeam.create(name="Twin")

        with pytest.raises(MultipleObjectsReturned):
            await LookupTeam.get_or_none(name="Twin")

    async def test_a_bad_filter_raises(self):
        with pytest.raises(Exception, match="nonsense"):
            await LookupTeam.get_or_none(nonsense=1)

    async def test_get_or_create_does_not_duplicate_when_the_lookup_is_ambiguous(self):
        await LookupTeam.create(name="Twin")
        await LookupTeam.create(name="Twin")

        with pytest.raises(MultipleObjectsReturned):
            await LookupTeam.get_or_create(name="Twin")

        assert await LookupTeam.filter(name="Twin").count() == 2


class TestGetOrCreate:
    async def test_returns_the_existing_row(self):
        team = await LookupTeam.create(name="Core")

        found, created = await LookupTeam.get_or_create(name="Core")

        assert created is False and found.id == team.id

    async def test_creates_when_missing_with_defaults(self):
        player, created = await LookupPlayer.get_or_create(
            name="Ada", defaults={"team": None}
        )

        assert created is True and player.name == "Ada"
