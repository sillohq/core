"""Record-specific field behavior."""

import inspect
from typing import Any

import pytest
from tortoise import Tortoise, fields
from tortoise.exceptions import ConfigurationError, FieldError, ValidationError

from sillo.record import AnyJSONField, Model

_has_global_fallback = (
    "_enable_global_fallback" in inspect.signature(Tortoise.init).parameters
)


class JSONValue(Model):
    id = fields.IntField(pk=True)
    value = AnyJSONField(null=True)

    class Meta:
        table = "record_json_values"


@pytest.fixture(autouse=True)
async def record_db():
    init_kwargs = {
        "db_url": "sqlite://:memory:",
        "modules": {"models": ["tests.test_record.test_fields"]},
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


class TestAnyJSONField:
    async def test_bare_string_round_trips_through_the_database(self):
        created = await JSONValue.create(value="authenticated")

        assert created.value == "authenticated"
        assert (await JSONValue.get(id=created.id)).value == "authenticated"

    @pytest.mark.parametrize(
        "value",
        [
            {"role": "authenticated"},
            ["authenticated", 2],
            True,
            42,
            3.5,
            None,
        ],
    )
    async def test_other_json_values_keep_tortoise_behavior(self, value: Any):
        created = await JSONValue.create(value=value)

        assert (await JSONValue.get(id=created.id)).value == value

    @pytest.mark.parametrize(
        "value",
        ['{"role":"authenticated"}', '["authenticated"]', "true", "null", "42"],
    )
    async def test_serialized_json_text_remains_a_string(self, value: str):
        created = await JSONValue.create(value=value)

        assert (await JSONValue.get(id=created.id)).value == value

    def test_string_uses_the_configured_encoder(self):
        seen = []

        def encoder(value):
            seen.append(value)
            return '"encoded"'

        field = AnyJSONField(encoder=encoder)

        assert field.to_db_value("authenticated", JSONValue) == '"encoded"'
        assert seen == ["authenticated"]

    def test_string_runs_configured_validators(self):
        def reject_authenticated(value):
            if value == "authenticated":
                raise ValidationError("reserved value")

        field = AnyJSONField(validators=[reject_authenticated])

        with pytest.raises(ValidationError, match="reserved value"):
            field.to_db_value("authenticated", JSONValue)

    def test_already_decoded_string_is_accepted_on_read(self):
        assert AnyJSONField().to_python_value("authenticated") == "authenticated"

    def test_invalid_bytes_are_not_silently_accepted(self):
        with pytest.raises(FieldError):
            AnyJSONField().to_python_value(b"not-json")
