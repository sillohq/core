"""``pydantic_model_from_tortoise`` — generating request schemas from models.

The generator decides three things per field: the Python type, whether the
field is required, and whether it is Optional. Each is driven by a different
property of the Tortoise field, so they are tested separately rather than
through one representative model.
"""

import pytest
from pydantic import BaseModel, ValidationError
from tortoise import fields

from sillo.record import Model
from sillo.record.pydantic import (
    _tortoise_to_python_type,
    pydantic_model_from_tortoise,
)


class Article(Model):
    id = fields.IntField(pk=True)
    title = fields.CharField(max_length=255)
    body = fields.TextField()
    views = fields.IntField(default=0)
    rating = fields.FloatField(null=True)
    published = fields.BooleanField(default=False)
    metadata = fields.JSONField(null=True)

    class Meta:
        table = "pydantic_bridge_articles"


class TestGeneratedModel:
    def test_it_returns_a_pydantic_model(self):
        schema = pydantic_model_from_tortoise(Article)
        assert issubclass(schema, BaseModel)

    def test_the_default_name_is_derived_from_the_model(self):
        assert pydantic_model_from_tortoise(Article).__name__ == "ArticleSchema"

    def test_the_name_can_be_given(self):
        schema = pydantic_model_from_tortoise(Article, name="ArticleCreate")
        assert schema.__name__ == "ArticleCreate"

    def test_every_field_appears_by_default(self):
        schema = pydantic_model_from_tortoise(Article)
        for name in ("id", "title", "body", "views", "rating", "published"):
            assert name in schema.model_fields


class TestSelectingFields:
    def test_exclude_drops_the_named_fields(self):
        schema = pydantic_model_from_tortoise(Article, exclude=["id", "views"])
        assert "id" not in schema.model_fields
        assert "views" not in schema.model_fields
        assert "title" in schema.model_fields

    def test_include_keeps_only_the_named_fields(self):
        schema = pydantic_model_from_tortoise(Article, include=["title", "body"])
        assert set(schema.model_fields) == {"title", "body"}

    def test_exclude_wins_over_include_for_the_same_field(self):
        # exclude is checked first, so naming a field in both removes it.
        schema = pydantic_model_from_tortoise(
            Article, include=["title", "body"], exclude=["body"]
        )
        assert set(schema.model_fields) == {"title"}


class TestRequirednessAndOptionality:
    def test_a_non_null_field_is_required(self):
        schema = pydantic_model_from_tortoise(Article, include=["title"])
        with pytest.raises(ValidationError):
            schema()

    def test_a_null_field_is_optional_and_defaults_to_none(self):
        schema = pydantic_model_from_tortoise(Article, include=["rating"])
        assert schema().rating is None

    def test_optional_fields_makes_a_required_field_optional(self):
        schema = pydantic_model_from_tortoise(
            Article, include=["title"], optional_fields=["title"]
        )
        assert schema().title is None

    def test_a_primary_key_is_not_required(self):
        # is_required excludes the pk, so a create-schema that keeps `id`
        # does not force the caller to invent one.
        schema = pydantic_model_from_tortoise(Article, include=["id"])
        assert schema().id is None

    def test_a_provided_value_is_still_validated(self):
        schema = pydantic_model_from_tortoise(Article, include=["views"])
        with pytest.raises(ValidationError):
            schema(views="not-an-int")


class TestTypeMapping:
    @pytest.mark.parametrize(
        "field,expected",
        [
            (fields.IntField(), int),
            (fields.SmallIntField(), int),
            (fields.BigIntField(), int),
            (fields.FloatField(), float),
            (fields.DecimalField(max_digits=8, decimal_places=2), float),
            (fields.BooleanField(), bool),
            (fields.CharField(max_length=10), str),
            (fields.TextField(), str),
            (fields.DatetimeField(), str),
            (fields.DateField(), str),
            (fields.TimeDeltaField(), float),
            (fields.JSONField(), dict),
        ],
    )
    def test_each_known_field_maps_to_its_python_type(self, field, expected):
        assert _tortoise_to_python_type(field) is expected

    def test_an_unknown_field_falls_back_to_str(self):
        class Exotic:
            """Not a Tortoise field at all, so no mapping entry matches."""

        assert _tortoise_to_python_type(Exotic()) is str

    def test_the_generated_model_carries_the_mapped_types(self):
        schema = pydantic_model_from_tortoise(
            Article, include=["title", "views", "published"]
        )
        parsed = schema(title="hi", views="3", published="true")
        assert parsed.views == 3
        assert parsed.published is True
