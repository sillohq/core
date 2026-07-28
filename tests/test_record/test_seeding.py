"""
Seeder and FixtureLoader.

Both write rows. ``Seeder`` takes them from Python, ``FixtureLoader`` from
JSON/JSONL files on disk, resolving the model from the filename unless an
explicit mapping is given.
"""

import inspect
import json

import pytest
from tortoise import Tortoise, fields
from tortoise.exceptions import ConfigurationError

from sillo.record import Model
from sillo.record.helpers import FixtureLoader, Seeder

_has_global_fallback = (
    "_enable_global_fallback" in inspect.signature(Tortoise.init).parameters
)


class SeedUser(Model):
    id = fields.IntField(pk=True)
    email = fields.CharField(max_length=255, unique=True)
    name = fields.CharField(max_length=255, default="")

    class Meta:
        table = "seed_users"


class SeedPost(Model):
    id = fields.IntField(pk=True)
    title = fields.CharField(max_length=255)

    class Meta:
        table = "seed_posts"


@pytest.fixture(autouse=True)
async def record_db():
    init_kwargs = dict(
        db_url="sqlite://:memory:",
        modules={"models": ["tests.test_record.test_seeding"]},
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


# ── Seeder ───────────────────────────────────────────────────────────────


async def test_a_seeded_row_is_created():
    seeder = Seeder(None)
    seeder.seed(SeedUser, [{"email": "a@example.com", "name": "Ada"}])
    await seeder.run()
    assert await SeedUser.get_or_none(email="a@example.com") is not None


async def test_run_reports_how_many_rows_it_wrote():
    seeder = Seeder(None)
    seeder.seed(SeedUser, [{"email": "a@x.com"}, {"email": "b@x.com"}])
    assert await seeder.run() == 2


async def test_seed_is_chainable():
    """Registration returns the seeder so several models can be queued in
    one expression."""
    seeder = Seeder(None)
    result = seeder.seed(SeedUser, [{"email": "a@x.com"}]).seed(
        SeedPost, [{"title": "Hello"}]
    )
    assert result is seeder
    assert await seeder.run() == 2


async def test_rows_for_several_models_are_all_written():
    seeder = Seeder(None)
    seeder.seed(SeedUser, [{"email": "a@x.com"}])
    seeder.seed(SeedPost, [{"title": "Hello"}])
    await seeder.run()
    assert await SeedUser.all().count() == 1
    assert await SeedPost.all().count() == 1


async def test_registering_nothing_writes_nothing():
    assert await Seeder(None).run() == 0


async def test_an_empty_record_list_is_accepted():
    seeder = Seeder(None)
    seeder.seed(SeedUser, [])
    assert await seeder.run() == 0


async def test_field_values_reach_the_row():
    seeder = Seeder(None)
    seeder.seed(SeedUser, [{"email": "a@x.com", "name": "Ada Lovelace"}])
    await seeder.run()
    user = await SeedUser.get(email="a@x.com")
    assert user.name == "Ada Lovelace"


async def test_a_failing_row_propagates():
    """A unique-constraint violation is a broken seed, not something to hide."""
    await SeedUser.create(email="dup@x.com")
    seeder = Seeder(None)
    seeder.seed(SeedUser, [{"email": "dup@x.com"}])
    with pytest.raises(Exception):
        await seeder.run()


async def test_seeds_run_in_registration_order():
    seeder = Seeder(None)
    seeder.seed(SeedUser, [{"email": "first@x.com"}, {"email": "second@x.com"}])
    await seeder.run()
    users = await SeedUser.all().order_by("id")
    assert [u.email for u in users] == ["first@x.com", "second@x.com"]


async def test_a_batch_size_is_accepted():
    seeder = Seeder(None)
    seeder.seed(SeedUser, [{"email": f"{i}@x.com"} for i in range(5)])
    assert await seeder.run(batch_size=2) == 5


# ── FixtureLoader ────────────────────────────────────────────────────────


@pytest.fixture
def fixtures(tmp_path):
    (tmp_path / "seeduser.json").write_text(
        json.dumps([{"email": "a@x.com"}, {"email": "b@x.com"}])
    )
    (tmp_path / "seedpost.jsonl").write_text(
        '{"title": "One"}\n{"title": "Two"}\n{"title": "Three"}\n'
    )
    return tmp_path


async def test_a_json_fixture_is_read(fixtures):
    assert await FixtureLoader(str(fixtures)).load("seeduser") == 2


async def test_a_jsonl_fixture_is_read(fixtures):
    assert await FixtureLoader(str(fixtures)).load("seedpost") == 3


async def test_blank_lines_in_a_jsonl_file_are_skipped(tmp_path):
    (tmp_path / "seedpost.jsonl").write_text(
        '{"title": "One"}\n\n\n{"title": "Two"}\n'
    )
    assert await FixtureLoader(str(tmp_path)).load("seedpost") == 2
    assert await SeedPost.all().count() == 2


async def test_a_single_json_object_counts_as_one_row(tmp_path):
    (tmp_path / "seeduser.json").write_text(json.dumps({"email": "solo@x.com"}))
    assert await FixtureLoader(str(tmp_path)).load("seeduser") == 1
    assert await SeedUser.get_or_none(email="solo@x.com") is not None


async def test_an_empty_json_array(tmp_path):
    (tmp_path / "empty.json").write_text("[]")
    assert await FixtureLoader(str(tmp_path)).load("empty") == 0


async def test_load_all_covers_every_file(fixtures):
    assert await FixtureLoader(str(fixtures)).load_all() == 5


async def test_load_all_on_an_empty_directory(tmp_path):
    assert await FixtureLoader(str(tmp_path)).load_all() == 0


async def test_a_missing_fixture_is_an_error(fixtures):
    with pytest.raises(FileNotFoundError, match="nonexistent"):
        await FixtureLoader(str(fixtures)).load("nonexistent")


async def test_the_error_names_the_directory(fixtures):
    with pytest.raises(FileNotFoundError, match=str(fixtures)):
        await FixtureLoader(str(fixtures)).load("nonexistent")


async def test_malformed_json_propagates(tmp_path):
    (tmp_path / "broken.json").write_text("{not json")
    with pytest.raises(json.JSONDecodeError):
        await FixtureLoader(str(tmp_path)).load("broken")


async def test_json_is_preferred_over_jsonl_for_the_same_name(tmp_path):
    (tmp_path / "seedpost.json").write_text(json.dumps([{"title": "from json"}]))
    (tmp_path / "seedpost.jsonl").write_text('{"title": "a"}\n{"title": "b"}\n')
    assert await FixtureLoader(str(tmp_path)).load("seedpost") == 1
    assert [p.title for p in await SeedPost.all()] == ["from json"]


async def test_loading_writes_the_rows(fixtures):
    """The returned count is rows persisted, not merely rows parsed."""
    assert await FixtureLoader(str(fixtures)).load_all() == 5
    assert await SeedUser.all().count() == 2
    assert await SeedPost.all().count() == 3
    assert sorted(u.email for u in await SeedUser.all()) == ["a@x.com", "b@x.com"]


async def test_a_plural_filename_resolves_to_the_singular_model(tmp_path):
    (tmp_path / "seedusers.json").write_text(json.dumps([{"email": "p@x.com"}]))
    assert await FixtureLoader(str(tmp_path)).load("seedusers") == 1
    assert await SeedUser.get_or_none(email="p@x.com") is not None


async def test_an_explicit_mapping_overrides_the_filename(tmp_path):
    (tmp_path / "people.json").write_text(json.dumps([{"email": "m@x.com"}]))
    loader = FixtureLoader(str(tmp_path), models={"people": SeedUser})
    assert await loader.load("people") == 1
    assert await SeedUser.get_or_none(email="m@x.com") is not None


async def test_an_unresolvable_filename_is_an_error(tmp_path):
    (tmp_path / "widgets.json").write_text(json.dumps([{"a": 1}]))
    with pytest.raises(LookupError, match="widgets"):
        await FixtureLoader(str(tmp_path)).load("widgets")


async def test_a_failing_row_rolls_back_the_whole_file(tmp_path):
    """A constraint violation half way through leaves the table untouched."""
    (tmp_path / "seeduser.json").write_text(
        json.dumps([{"email": "dup@x.com"}, {"email": "dup@x.com"}])
    )
    with pytest.raises(Exception):
        await FixtureLoader(str(tmp_path)).load("seeduser")
    assert await SeedUser.all().count() == 0


async def test_non_fixture_files_are_ignored(tmp_path):
    (tmp_path / "seedpost.json").write_text(json.dumps([{"title": "kept"}]))
    (tmp_path / "README.md").write_text("not a fixture")
    (tmp_path / "notes.txt").write_text("also not a fixture")
    assert await FixtureLoader(str(tmp_path)).load_all() == 1
