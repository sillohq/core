"""The composable model mixins in ``sillo.record.mixins``.

These carry behaviour that models opt into — soft deletes, timestamps,
serialisation, validation hooks, cascading deletes. They were almost entirely
unexercised, which is how ``HasUlidMixin.generate_ulid`` shipped calling an
API that does not exist in the ULID package this project depends on.
"""

import inspect
import json
from datetime import datetime, timezone

import pytest
from tortoise import Tortoise, fields
from tortoise.exceptions import ConfigurationError

from sillo.record import Model
from sillo.record.mixins import (
    CascadesDeletesMixin,
    HasUlidMixin,
    SerializesToDictMixin,
    SoftDeletesMixin,
    TimestampsMixin,
    ValidatesBeforeSaveMixin,
)

_has_global_fallback = (
    "_enable_global_fallback" in inspect.signature(Tortoise.init).parameters
)


class Post(SoftDeletesMixin, SerializesToDictMixin, TimestampsMixin, Model):
    id = fields.IntField(pk=True)
    title = fields.CharField(max_length=255)

    class Meta:
        table = "mixin_posts"


class Validated(ValidatesBeforeSaveMixin, Model):
    id = fields.IntField(pk=True)
    title = fields.CharField(max_length=255)

    class Meta:
        table = "mixin_validated"

    async def validate(self) -> None:
        if not self.title.strip():
            raise ValueError("title must not be blank")


@pytest.fixture(autouse=True)
async def record_db():
    init_kwargs = dict(
        db_url="sqlite://:memory:",
        modules={"models": ["tests.test_record.test_mixins"]},
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


class TestSoftDeletes:
    async def test_soft_delete_sets_the_timestamp_without_removing_the_row(self):
        post = await Post.create(title="one")

        await post.soft_delete()

        assert post.deleted_at is not None
        assert await Post.filter(id=post.id).exists()

    async def test_is_trashed_reflects_the_state(self):
        post = await Post.create(title="one")
        assert post.is_trashed is False

        await post.soft_delete()
        assert post.is_trashed is True

    async def test_restore_clears_the_timestamp(self):
        post = await Post.create(title="one")
        await post.soft_delete()

        await post.restore()

        assert post.deleted_at is None
        assert post.is_trashed is False

    async def test_force_delete_removes_the_row(self):
        post = await Post.create(title="one")

        await post.force_delete()

        assert not await Post.filter(id=post.id).exists()

    async def test_active_excludes_soft_deleted_rows(self):
        kept = await Post.create(title="kept")
        gone = await Post.create(title="gone")
        await gone.soft_delete()

        ids = {p.id for p in await Post.active()}
        assert ids == {kept.id}

    async def test_only_trashed_returns_just_the_deleted_rows(self):
        await Post.create(title="kept")
        gone = await Post.create(title="gone")
        await gone.soft_delete()

        ids = {p.id for p in await Post.only_trashed()}
        assert ids == {gone.id}

    async def test_with_trashed_returns_everything(self):
        kept = await Post.create(title="kept")
        gone = await Post.create(title="gone")
        await gone.soft_delete()

        ids = {p.id for p in await Post.with_trashed()}
        assert ids == {kept.id, gone.id}


class TestTimestamps:
    async def test_touch_moves_updated_at_forward(self):
        post = await Post.create(title="one")
        before = post.updated_at

        await post.touch()

        assert post.updated_at >= before

    async def test_set_created_at_fills_a_missing_value(self):
        post = Post(title="one")
        post.created_at = None

        post.set_created_at()

        assert isinstance(post.created_at, datetime)

    async def test_set_created_at_leaves_an_existing_value_alone(self):
        post = Post(title="one")
        original = datetime(2020, 1, 1, tzinfo=timezone.utc)
        post.created_at = original

        post.set_created_at()

        assert post.created_at == original


class TestSerialization:
    async def test_to_dict_includes_every_field(self):
        post = await Post.create(title="one")

        data = post.to_dict()

        assert data["title"] == "one"
        assert data["id"] == post.id

    async def test_datetimes_are_rendered_as_iso_strings(self):
        post = await Post.create(title="one")

        created = post.to_dict()["created_at"]

        assert isinstance(created, str)
        datetime.fromisoformat(created)  # parses, or this raises

    async def test_exclude_drops_fields(self):
        post = await Post.create(title="one")

        assert "title" not in post.to_dict(exclude=["title"])

    async def test_include_keeps_only_those_fields(self):
        post = await Post.create(title="one")

        assert set(post.to_dict(include=["title"])) == {"title"}

    async def test_nested_objects_are_expanded_within_max_depth(self):
        class Inner:
            def to_dict(self, max_depth=3):
                return {"depth": max_depth}

        post = await Post.create(title="one")
        post.title = Inner()

        assert post.to_dict(max_depth=2)["title"] == {"depth": 1}

    async def test_max_depth_zero_stops_expanding(self):
        class Inner:
            def to_dict(self, max_depth=3):  # pragma: no cover - must not run
                raise AssertionError("should not recurse at max_depth=0")

        post = await Post.create(title="one")
        inner = Inner()
        post.title = inner

        assert post.to_dict(max_depth=0)["title"] is inner

    async def test_to_json_round_trips(self):
        post = await Post.create(title="one")

        parsed = json.loads(post.to_json())

        assert parsed["title"] == "one"

    async def test_to_json_accepts_indent_and_forwards_kwargs(self):
        post = await Post.create(title="one")

        out = post.to_json(indent=2, include=["title"])

        assert "\n" in out
        assert json.loads(out) == {"title": "one"}


class TestValidatesBeforeSave:
    async def test_a_valid_model_saves(self):
        row = await Validated.create(title="fine")
        assert row.id is not None

    async def test_an_invalid_model_is_refused(self):
        with pytest.raises(ValueError, match="must not be blank"):
            await Validated.create(title="   ")

    async def test_the_default_validate_permits_everything(self):
        class Open(ValidatesBeforeSaveMixin):
            async def save(self, *a, **k):
                await self.validate()
                return "saved"

        assert await Open().save() == "saved"


class TestCascadesDeletes:
    async def test_related_objects_are_deleted_first(self):
        deleted = []

        class Related:
            async def delete(self):
                deleted.append("related")

        class Parent(CascadesDeletesMixin):
            _cascade_deletes = ["child"]

            def __init__(self):
                self.child = Related()

            async def delete(self):
                await super().delete()
                return "parent-deleted"

        class Base:
            async def delete(self):
                deleted.append("parent")

        class Combined(CascadesDeletesMixin, Base):
            _cascade_deletes = ["child"]

            def __init__(self):
                self.child = Related()

        await Combined().delete()

        assert deleted == ["related", "parent"]

    async def test_a_missing_relation_is_skipped(self):
        order = []

        class Base:
            async def delete(self):
                order.append("parent")

        class Combined(CascadesDeletesMixin, Base):
            _cascade_deletes = ["absent"]

        await Combined().delete()

        assert order == ["parent"]

    async def test_a_relation_without_delete_is_skipped(self):
        order = []

        class Base:
            async def delete(self):
                order.append("parent")

        class Combined(CascadesDeletesMixin, Base):
            _cascade_deletes = ["child"]

            def __init__(self):
                self.child = object()  # no delete()

        await Combined().delete()

        assert order == ["parent"]


class TestHasUlid:
    def test_it_returns_a_26_character_ulid(self):
        value = HasUlidMixin().generate_ulid()

        assert isinstance(value, str)
        assert len(value) == 26

    def test_successive_calls_differ(self):
        mixin = HasUlidMixin()
        assert mixin.generate_ulid() != mixin.generate_ulid()

    def test_ulids_sort_in_generation_order(self):
        mixin = HasUlidMixin()
        values = [mixin.generate_ulid() for _ in range(5)]
        assert values == sorted(values)

    def test_a_missing_package_reports_what_to_install(self, monkeypatch):
        import sillo.record.mixins as mixins

        monkeypatch.setattr(mixins, "ulid", None)

        with pytest.raises(RuntimeError, match="python-ulid"):
            HasUlidMixin().generate_ulid()
