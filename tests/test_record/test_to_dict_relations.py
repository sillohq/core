"""``to_dict`` on models that have relations.

A relation that was never fetched is a lazy query handle, and putting it in
the dict made ``json.dumps`` fail with "not JSON serializable"
(sillohq/core#465).
"""

import inspect
import json

import pytest
from tortoise import Tortoise, fields
from tortoise.exceptions import ConfigurationError

from sillo.record import Model

_has_global_fallback = (
    "_enable_global_fallback" in inspect.signature(Tortoise.init).parameters
)


class ToDictAuthor(Model):
    id = fields.IntField(primary_key=True)
    name = fields.CharField(max_length=50)

    class Meta:
        table = "to_dict_authors"


class ToDictBook(Model):
    id = fields.IntField(primary_key=True)
    title = fields.CharField(max_length=50)
    author = fields.ForeignKeyField(
        "models.ToDictAuthor", related_name="books", null=True
    )

    class Meta:
        table = "to_dict_books"


@pytest.fixture(autouse=True)
async def record_db():
    init_kwargs = dict(
        db_url="sqlite://:memory:",
        modules={"models": ["tests.test_record.test_to_dict_relations"]},
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


async def _book():
    author = await ToDictAuthor.create(name="Ada")
    book = await ToDictBook.create(title="Notes", author=author)
    return author, await ToDictBook.get(id=book.id)


class TestUnfetchedRelations:
    async def test_a_freshly_loaded_instance_encodes_as_json(self):
        _, book = await _book()

        assert json.loads(json.dumps(book.to_dict()))["title"] == "Notes"

    async def test_to_json_works_without_fetching(self):
        _, book = await _book()

        assert json.loads(book.to_json())["title"] == "Notes"

    async def test_the_foreign_key_column_is_still_there(self):
        author, book = await _book()

        data = book.to_dict()

        assert data["author_id"] == author.id
        assert "author" not in data

    async def test_reverse_relations_are_left_out(self):
        author, _ = await _book()
        fresh = await ToDictAuthor.get(id=author.id)

        data = fresh.to_dict()

        assert "books" not in data
        assert json.loads(json.dumps(data))["name"] == "Ada"

    async def test_columns_are_unchanged(self):
        _, book = await _book()

        assert set(book.to_dict()) == {
            "id",
            "title",
            "author_id",
            "created_at",
            "updated_at",
            "deleted_at",
        }

    async def test_include_and_exclude_still_apply(self):
        _, book = await _book()

        assert set(book.to_dict(include=["title"])) == {"title"}
        assert "title" not in book.to_dict(exclude=["title"])
