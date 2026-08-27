"""Coverage for sillo.record.factories: Factory.make/create/create_many/state
and FactoryBuilder's register/get, none of which had any prior tests.
"""

from __future__ import annotations

import inspect
from uuid import uuid4

import pytest
from tortoise import Tortoise, fields
from tortoise.exceptions import ConfigurationError

from sillo.record import Model
from sillo.record.factories import Factory, FactoryBuilder

_has_global_fallback = (
    "_enable_global_fallback" in inspect.signature(Tortoise.init).parameters
)


class Widget(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=255)
    color = fields.CharField(max_length=32, default="red")

    class Meta:
        table = "factory_widgets"


class WidgetFactory(Factory):
    model = Widget
    definition = staticmethod(
        lambda: {"name": f"widget-{uuid4().hex[:8]}", "color": "red"}
    )


@pytest.fixture(autouse=True)
async def factory_db():
    init_kwargs = dict(
        db_url="sqlite://:memory:",
        modules={"models": ["tests.test_record.test_factories"]},
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


def test_make_builds_unsaved_instance_with_overrides():
    widget = WidgetFactory.make({"color": "blue"})
    assert widget.color == "blue"
    assert widget.name.startswith("widget-")
    assert widget.pk is None


async def test_create_persists_instance():
    widget = await WidgetFactory.create()
    assert widget.pk is not None
    fetched = await Widget.get(id=widget.pk)
    assert fetched.name == widget.name


async def test_create_many_persists_count_instances_with_overrides():
    widgets = await WidgetFactory.create_many(3, {"color": "green"})
    assert len(widgets) == 3
    assert all(w.pk is not None for w in widgets)
    assert all(w.color == "green" for w in widgets)
    assert await Widget.all().count() == 3


def test_state_returns_a_modifier_applying_overrides():
    modifier = WidgetFactory.state(color="purple")
    data = modifier()
    assert data["color"] == "purple"
    assert data["name"].startswith("widget-")


def test_factory_builder_register_and_get():
    builder = FactoryBuilder()
    builder.register("widget", WidgetFactory)
    assert builder.get("widget") is WidgetFactory


def test_factory_builder_get_missing_raises_key_error():
    builder = FactoryBuilder()
    with pytest.raises(KeyError, match="not registered"):
        builder.get("missing")
