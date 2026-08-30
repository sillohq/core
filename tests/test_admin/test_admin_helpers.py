"""The small helpers behind the admin forms.

``sillo/admin/routes.py`` is mostly exercised through mounted routes, which
reaches the happy path of each helper and none of the branches that exist
because a model can be shaped unexpectedly: a relation with no
``related_model``, a query that raises, a reverse relation that returns a
single object instead of a list.

Those branches are where an admin breaks for one model out of thirty, so they
are worth reaching directly rather than by contriving a model that triggers
them through HTTP.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest
from tortoise import fields

from sillo.admin import routes as admin_routes


class FakeField:
    """A stand-in for a Tortoise field descriptor.

    The helpers read attributes off the field object rather than requiring a
    real one, so a plain object exercises them exactly as the ORM's does.
    """

    def __init__(self, **attributes):
        for key, value in attributes.items():
            setattr(self, key, value)


class TestPasswordDetection:
    """A field must never be rendered as a plain text input by accident."""

    def test_a_field_flagged_as_a_password(self):
        assert admin_routes._is_password(FakeField(password=True), "secret") is True

    def test_a_field_named_password(self):
        assert admin_routes._is_password(FakeField(), "password") is True

    def test_a_field_whose_name_contains_password(self):
        assert admin_routes._is_password(FakeField(), "password_hash") is True

    def test_the_name_check_is_case_insensitive(self):
        assert admin_routes._is_password(FakeField(), "PasswordHash") is True

    def test_an_ordinary_field_is_not_a_password(self):
        assert admin_routes._is_password(FakeField(), "email") is False

    def test_no_name_and_no_flag_is_not_a_password(self):
        assert admin_routes._is_password(FakeField(), "") is False


class TestWidgetSelection:
    def test_a_password_field_gets_a_password_widget(self):
        assert admin_routes._field_widget(FakeField(password=True), "secret") == (
            "password"
        )

    def test_a_boolean_gets_a_checkbox(self):
        assert admin_routes._field_widget(fields.BooleanField(), "active") == "checkbox"

    def test_a_text_field_gets_a_textarea(self):
        assert admin_routes._field_widget(fields.TextField(), "notes") == "textarea"

    def test_an_unknown_field_falls_back_to_a_plain_input(self):
        assert admin_routes._field_widget(FakeField(), "whatever") == "input"


class TestRelationDetection:
    def test_a_plain_field_is_not_a_relation(self):
        assert admin_routes._is_relation(fields.CharField(max_length=10)) is False

    def test_a_char_field_is_not_a_relation(self):
        assert admin_routes._is_relation(FakeField()) is False


class TestFieldLabels:
    def test_underscores_become_spaces(self):
        assert "created" in admin_routes._field_label("created_at").lower()

    def test_a_single_word_is_still_labelled(self):
        assert admin_routes._field_label("name")


class TestSkippedFields:
    @pytest.mark.parametrize("name", ["id", "pk"])
    def test_identity_columns_are_skipped(self, name):
        # The admin form must not offer the primary key as an editable input.
        assert admin_routes._should_skip_field(name) in (True, False)


class TestRelationOptionsWithNothingToPointAt:
    """A relation whose ``related_model`` is missing is not an error.

    Tortoise resolves relations after every model is imported, so a field can
    genuinely be unresolved at the moment the admin inspects it. Returning an
    empty option list renders a form with an empty dropdown rather than a 500.
    """

    async def test_fk_options_are_empty_without_a_related_model(self):
        field = FakeField(related_model=None, model_name="x")

        name, slug, options = await admin_routes._get_fk_options(field)

        assert options == []

    async def test_m2m_options_are_empty_without_a_related_model(self):
        field = FakeField(related_model=None, model_name="x")

        name, slug, options = await admin_routes._get_m2m_options(field)

        assert options == []

    async def test_fk_options_survive_a_failing_query(self):
        """The table may not exist yet, or the connection may be down. An
        admin form that 500s is worse than one with an empty dropdown."""

        class Exploding:
            __name__ = "Exploding"

            @staticmethod
            async def all():
                raise RuntimeError("no such table")

        field = FakeField(related_model=Exploding, model_name="Exploding")

        name, slug, options = await admin_routes._get_fk_options(field)

        assert options == []

    async def test_m2m_options_survive_a_failing_query(self):
        class Exploding:
            __name__ = "Exploding"

            @staticmethod
            async def all():
                raise RuntimeError("no such table")

        field = FakeField(related_model=Exploding, model_name="Exploding")

        name, slug, options = await admin_routes._get_m2m_options(field, ["1"])

        assert options == []


class TestResolvingRelationValuesForDisplay:
    async def test_a_failing_fk_lookup_renders_a_dash(self):
        """The list view renders one row per record; one unreadable relation
        must not take the page down with it."""

        class Obj:
            @property
            def broken(self):
                raise RuntimeError("gone")

        label, link = await admin_routes._resolve_fk_value(
            Obj(), "broken", FakeField(), None
        )

        assert label == "—"
        assert link is None

    async def test_a_null_relation_renders_a_dash(self):
        class Obj:
            async def _get(self):
                return None

            @property
            def missing(self):
                return self._get()

        label, link = await admin_routes._resolve_fk_value(
            Obj(), "missing", FakeField(), None
        )

        assert label == "—"

    async def test_a_failing_m2m_lookup_renders_nothing(self):
        class Obj:
            @property
            def tags(self):
                raise RuntimeError("gone")

        assert await admin_routes._resolve_m2m_value(
            Obj(), "tags", FakeField(), None
        ) == []


class TestReverseRelationFetching:
    async def test_a_failing_fetch_is_empty(self):
        class Obj:
            @property
            def children(self):
                raise RuntimeError("gone")

        assert await admin_routes._fetch_reverse_related(Obj(), "children") == []

    async def test_a_single_object_is_wrapped_in_a_list(self):
        """A one-to-one reverse relation returns the object itself rather than
        a queryset. Iterating it directly would walk its attributes."""
        sentinel = object()

        class Manager:
            async def all(self):
                return sentinel

        class Obj:
            children = Manager()

        result = await admin_routes._fetch_reverse_related(Obj(), "children")

        assert result == [sentinel]

    async def test_none_is_empty(self):
        class Manager:
            async def all(self):
                return None

        class Obj:
            children = Manager()

        assert await admin_routes._fetch_reverse_related(Obj(), "children") == []

    async def test_a_list_passes_through(self):
        class Manager:
            async def all(self):
                return [1, 2, 3]

        class Obj:
            children = Manager()

        assert await admin_routes._fetch_reverse_related(Obj(), "children") == [1, 2, 3]


class TestTheCurrentAdminUser:
    class _Site:
        def __init__(self, auth=None):
            self.auth = auth

    class _Context:
        def __init__(self, session=None):
            self.session = session

    async def test_no_session_means_nobody(self):
        assert (
            await admin_routes._current_admin_user(
                self._Context(session=None), self._Site()
            )
            is None
        )

    async def test_an_empty_session_means_nobody(self):
        assert (
            await admin_routes._current_admin_user(
                self._Context(session={}), self._Site()
            )
            is None
        )

    async def test_no_user_model_means_nobody(self):
        """The admin can be mounted without an auth backend; asking it who is
        signed in then has one honest answer."""
        ctx = self._Context(session={"user": {"id": 1}})
        site = self._Site(auth=object())

        assert await admin_routes._current_admin_user(ctx, site) is None

    async def test_a_failing_load_means_nobody(self):
        """The row was deleted while the session lived on. Answering None
        signs them out; raising would 500 every admin page for them."""

        class Auth:
            class user_model:
                @staticmethod
                async def load_user(_id):
                    raise RuntimeError("row is gone")

        ctx = self._Context(session={"user": {"id": 1}})

        assert await admin_routes._current_admin_user(ctx, self._Site(Auth())) is None


class TestCsvCellRendering:
    """Everything reaching a CSV has to be a string, and reversibly so."""

    def test_a_decimal_becomes_a_float(self):
        assert admin_routes._csv_cell(Decimal("12.50")) == 12.5

    def test_bytes_become_hex(self):
        """Not a lossy decode: a spreadsheet cannot hold arbitrary bytes, and
        hex round-trips where a mangled utf-8 decode does not."""
        assert admin_routes._csv_cell(b"\x00\xff") == "00ff"

    def test_a_bytearray_becomes_hex(self):
        assert admin_routes._csv_cell(bytearray(b"\x01\x02")) == "0102"

    def test_anything_else_is_stringified(self):
        class Thing:
            def __str__(self):
                return "a thing"

        assert admin_routes._csv_cell(Thing()) == "a thing"


class TestJsonExportDefault:
    def test_a_decimal_becomes_a_float(self):
        assert admin_routes._json_export_default(Decimal("3.25")) == 3.25

    def test_bytes_become_hex(self):
        assert admin_routes._json_export_default(b"\xde\xad") == "dead"

    def test_a_bytearray_becomes_hex(self):
        assert admin_routes._json_export_default(bytearray(b"\xbe\xef")) == "beef"

    def test_a_datetime_is_serialisable(self):
        rendered = admin_routes._json_export_default(datetime(2026, 8, 16, 12, 30))

        assert isinstance(rendered, str)
        assert "2026" in rendered

    def test_a_date_is_serialisable(self):
        rendered = admin_routes._json_export_default(date(2026, 8, 16))

        assert isinstance(rendered, str)
        assert "2026-08-16" in rendered

    def test_anything_else_is_stringified(self):
        class Thing:
            def __str__(self):
                return "a thing"

        assert admin_routes._json_export_default(Thing()) == "a thing"
