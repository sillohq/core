"""Coverage for sillo.record.scopes: ScopeRegistry's own methods, and the
RecordQuerySet/RecordManager paths not already exercised indirectly through
test_model_features.py's global/local scope tests."""

from __future__ import annotations

import inspect

import pytest
from tortoise import Model as TortoiseModel
from tortoise import Tortoise, fields
from tortoise.exceptions import ConfigurationError

from sillo.record import Model
from sillo.record.scopes import RecordManager, ScopeRegistry

_has_global_fallback = (
    "_enable_global_fallback" in inspect.signature(Tortoise.init).parameters
)


class ScopedWidget(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100)

    class Meta:
        table = "scoped_widgets"

    @classmethod
    def scope_named(cls, queryset, name):
        return queryset.filter(name=name)


class UnscopedWidget(TortoiseModel):
    """A model that does not mix in HasScopes -- RecordManager still has to
    work against it, since nothing guarantees every model using it does."""

    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100)

    class Meta:
        table = "unscoped_widgets"
        manager = RecordManager()


@pytest.fixture(autouse=True)
async def record_db():
    init_kwargs = {
        "db_url": "sqlite://:memory:",
        "modules": {"models": ["tests.test_record.test_scopes"]},
    }
    if _has_global_fallback:
        init_kwargs["_enable_global_fallback"] = True
    await Tortoise.init(**init_kwargs)
    await Tortoise.generate_schemas()
    yield
    ScopedWidget._scope_registry = None
    try:
        await Tortoise._drop_databases()
    except ConfigurationError:
        pass
    try:
        await Tortoise.close_connections()
    except Exception:
        pass


class TestScopeRegistry:
    def test_remove_returns_true_for_a_registered_scope(self):
        registry = ScopeRegistry()
        scope = lambda qs: qs
        registry.add(scope)

        assert registry.remove(scope) is True
        assert registry._global_scopes == []

    def test_remove_returns_false_for_an_unregistered_scope(self):
        registry = ScopeRegistry()

        assert registry.remove(lambda qs: qs) is False

    def test_without_global_scopes_returns_the_queryset_unchanged(self):
        registry = ScopeRegistry()
        sentinel = object()

        assert registry.without_global_scopes(sentinel) is sentinel


class TestRecordQuerySet:
    async def test_an_unknown_scope_name_raises_attribute_error(self):
        with pytest.raises(AttributeError, match="no_such_scope"):
            ScopedWidget.all().no_such_scope()

    async def test_without_global_scopes_returns_a_fresh_queryset(self):
        await ScopedWidget.create(name="a")

        queryset = ScopedWidget.all().without_global_scopes()

        assert await queryset.count() == 1


class TestRecordManagerWithoutHasScopes:
    """RecordManager.get_queryset's fallback when the model it manages has
    no ``apply_scopes`` attribute at all -- true for any plain Tortoise
    model that opts into RecordManager without also mixing in HasScopes."""

    async def test_get_queryset_still_works_without_apply_scopes(self):
        await UnscopedWidget.create(name="a")

        assert await UnscopedWidget.all().count() == 1

    async def test_without_global_scopes_on_the_manager_itself(self):
        await UnscopedWidget.create(name="a")

        queryset = UnscopedWidget._meta.manager.without_global_scopes()

        assert await queryset.count() == 1
