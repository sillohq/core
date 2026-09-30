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
from sillo.record.mixins import SerializesToDictMixin

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


class ToDictMixedBook(SerializesToDictMixin, Model):
    id = fields.IntField(primary_key=True)
    title = fields.CharField(max_length=50)
    author = fields.ForeignKeyField("models.ToDictAuthor", related_name="mixed_books")

    class Meta:
        table = "to_dict_mixed_books"


@pytest.fixture(autouse=True)
async def record_db():
    init_kwargs = {
        "db_url": "sqlite://:memory:",
        "modules": {"models": ["tests.test_record.test_to_dict_relations"]},
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


class TestOptInRelations:
    async def test_a_fetched_foreign_key_is_nested_when_asked(self):
        _, book = await _book()
        await book.fetch_related("author")

        data = book.to_dict(relations=["author"])

        assert data["author"]["name"] == "Ada"
        assert data["author_id"] == data["author"]["id"]

    async def test_fetched_relations_are_left_out_unless_asked(self):
        _, book = await _book()
        await book.fetch_related("author")

        assert "author" not in book.to_dict()

    async def test_an_unfetched_relation_is_skipped_not_queried(self):
        _, book = await _book()

        data = book.to_dict(relations=["author"])

        assert "author" not in data
        json.dumps(data)

    async def test_true_includes_every_fetched_relation(self):
        author, _ = await _book()
        await ToDictBook.create(title="More", author=author)
        fresh = await ToDictAuthor.get(id=author.id)
        await fresh.fetch_related("books")

        data = fresh.to_dict(relations=True)

        assert sorted(b["title"] for b in data["books"]) == ["More", "Notes"]
        json.dumps(data)

    async def test_a_reverse_relation_that_was_not_fetched_is_skipped(self):
        author, _ = await _book()
        fresh = await ToDictAuthor.get(id=author.id)

        assert "books" not in fresh.to_dict(relations=["books"])

    async def test_an_empty_fetched_relation_is_an_empty_list(self):
        author = await ToDictAuthor.create(name="No books")
        await author.fetch_related("books")

        assert author.to_dict(relations=["books"])["books"] == []

    async def test_a_null_foreign_key_is_none(self):
        book = await ToDictBook.create(title="Orphan")
        await book.fetch_related("author")

        assert book.to_dict(relations=["author"])["author"] is None

    async def test_relations_that_point_back_stop_at_max_depth(self):
        author, _ = await _book()
        fresh = await ToDictAuthor.get(id=author.id).prefetch_related("books__author")

        data = fresh.to_dict(relations=True, max_depth=2)

        assert data["books"][0]["author"]["name"] == "Ada"
        assert "books" not in data["books"][0]["author"]
        json.dumps(data)

    async def test_names_apply_to_this_model_only(self):
        author, _ = await _book()
        fresh = await ToDictAuthor.get(id=author.id).prefetch_related("books__author")

        data = fresh.to_dict(relations=["books"])

        assert "author" not in data["books"][0]

    async def test_exclude_applies_to_relations(self):
        _, book = await _book()
        await book.fetch_related("author")

        assert "author" not in book.to_dict(relations=True, exclude=["author"])

    async def test_an_unknown_relation_name_is_an_error(self):
        _, book = await _book()

        with pytest.raises(ValueError, match="no relation named 'writer'"):
            book.to_dict(relations=["writer"])

    async def test_a_column_name_is_not_a_relation(self):
        _, book = await _book()

        with pytest.raises(ValueError, match="'title'"):
            book.to_dict(relations=["title"])

    async def test_to_json_forwards_relations(self):
        _, book = await _book()
        await book.fetch_related("author")

        assert json.loads(book.to_json(relations=True))["author"]["name"] == "Ada"


class TestEveryPathThatSerializes:
    """Collections, pagination and the mixin all route through ``to_dict``."""

    async def test_a_collection_of_unfetched_models_encodes(self):
        await _book()
        books = await ToDictBook.all()

        from sillo.record import Collection

        assert json.loads(Collection(books).to_json())[0]["title"] == "Notes"

    async def test_a_paginated_page_of_unfetched_models_encodes(self):
        await _book()
        from sillo.record import paginate

        page = await paginate(ToDictBook.all(), page=1, page_size=10)

        assert json.loads(json.dumps(page.to_dict()))["items"][0]["title"] == "Notes"

    async def test_the_mixin_behaves_the_same(self):
        author = await ToDictAuthor.create(name="Ada")
        await ToDictMixedBook.create(title="Notes", author=author)
        book = await ToDictMixedBook.first()

        data = book.to_dict()

        assert "author" not in data
        assert data["author_id"] == author.id
        json.dumps(data)
        await book.fetch_related("author")
        assert book.to_dict(relations=["author"])["author"]["name"] == "Ada"
