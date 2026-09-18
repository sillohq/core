"""Coverage for ``DatabaseManager``'s lifecycle: init/shutdown/health,
``ensure_context``'s branches, the context-manager protocol, ``orm_config``'s
override, and ``setup_record``'s already-registered short circuit. All of
this only ran through ``_build_tortoise_config`` before -- nothing actually
opened a connection.
"""

from __future__ import annotations

import pathlib
import sys
import unittest.mock

import sillo.record.manager as manager_module
from sillo.record.config import DatabaseConfig
from sillo.record.manager import DatabaseManager, setup_record
from sillo import SilloApp


def make_manager(**overrides) -> DatabaseManager:
    config = DatabaseConfig(url="sqlite://:memory:", generate_schemas=True, **overrides)
    return DatabaseManager(config).register_models("tests.test_record.test_manager_lifecycle")


class TestInit:
    async def test_marks_itself_initialized(self):
        db = make_manager()
        assert db._initialized is False
        await db.init()
        try:
            assert db._initialized is True
        finally:
            await db.shutdown()

    async def test_calling_init_twice_is_a_no_op(self):
        db = make_manager()
        await db.init()
        try:
            root_after_first = db._root_context
            await db.init()
            assert db._root_context is root_after_first
        finally:
            await db.shutdown()


class TestShutdown:
    async def test_shutting_down_without_init_is_a_no_op(self):
        db = make_manager()
        await db.shutdown()  # must not raise
        assert db._initialized is False

    async def test_closes_connections_and_flips_the_flag(self):
        db = make_manager()
        await db.init()
        await db.shutdown()
        assert db._initialized is False


class TestHealth:
    async def test_true_once_connected(self):
        db = make_manager()
        await db.init()
        try:
            assert await db.health() is True
        finally:
            await db.shutdown()

    async def test_false_when_not_connected(self):
        db = make_manager()
        assert await db.health() is False


class TestEnsureContext:
    async def test_passes_through_before_init(self):
        db = make_manager()

        async def call_next():
            return "downstream"

        assert await db.ensure_context(None, call_next) == "downstream"

    async def test_passes_through_when_the_root_context_never_inited(self):
        db = make_manager()
        db._root_context = object()  # has no `inited` attribute

        async def call_next():
            return "downstream"

        assert await db.ensure_context(None, call_next) == "downstream"

    async def test_reenters_the_root_context_for_the_call(self):
        """``init()`` itself already entered the root context in this task
        (it is the startup task, in the real flow) -- a request lands in a
        *different* task where the contextvar was never set, which is
        forced here rather than relied on, since a task created from this
        one would otherwise inherit the copy `init()` just made."""
        db = make_manager()
        await db.init()
        try:
            reset_token = manager_module._current_context.set(None)
            try:
                seen = {}

                async def call_next():
                    seen["current"] = manager_module._current_context.get()
                    return "ok"

                result = await db.ensure_context(None, call_next)

                assert result == "ok"
                assert seen["current"] is db._root_context
                # The token is reset afterwards -- no leak into later code.
                assert manager_module._current_context.get() is None
            finally:
                manager_module._current_context.reset(reset_token)
        finally:
            await db.shutdown()

    async def test_does_not_reenter_when_already_inside_a_context(self):
        db = make_manager()
        await db.init()
        try:
            token = manager_module._current_context.set(db._root_context)
            try:
                calls = []

                async def call_next():
                    calls.append(manager_module._current_context.get())
                    return "ok"

                assert await db.ensure_context(None, call_next) == "ok"
                assert calls == [db._root_context]
            finally:
                manager_module._current_context.reset(token)
        finally:
            await db.shutdown()

    async def test_pre_context_tortoise_falls_back_to_pass_through(self, monkeypatch):
        db = make_manager()
        await db.init()
        try:
            monkeypatch.setattr(manager_module, "_current_context", None)

            async def call_next():
                return "downstream"

            assert await db.ensure_context(None, call_next) == "downstream"
        finally:
            await db.shutdown()


class TestContextManagerProtocol:
    async def test_aenter_initializes_and_aexit_shuts_down(self):
        db = make_manager()
        async with db as opened:
            assert opened is db
            assert db._initialized is True
        assert db._initialized is False


class TestOrmConfig:
    def test_defaults_to_the_configured_migrations_module(self):
        db = make_manager()
        assert db.orm_config()["apps"]["models"]["migrations"] == "database.migrations"

    def test_an_override_replaces_it_and_sticks(self):
        db = make_manager()
        config = db.orm_config(migrations="myapp.migrations")
        assert config["apps"]["models"]["migrations"] == "myapp.migrations"
        assert db._migrations_module == "myapp.migrations"


class TestPreContextTortoiseImportFallback:
    def test_current_context_is_none_when_tortoise_context_is_unavailable(self):
        """Older Tortoise releases have no ``tortoise.context`` module at
        all -- the import itself raises, and the module falls back to
        treating connections as global state rather than crashing on
        import.

        Re-executed in a scratch namespace rather than via
        ``importlib.reload``: reloading ``sillo.record.manager`` in this
        process would swap out the very ``DatabaseManager`` class other
        already-imported test modules hold a reference to, breaking their
        ``isinstance``/identity checks. Compiling with the real file's path
        as the filename keeps these lines attributed to it for coverage.
        """
        source_path = manager_module.__file__
        source = pathlib.Path(source_path).read_text()
        code = compile(source, source_path, "exec")
        namespace = {"__name__": "sillo.record._manager_reimport_for_coverage"}

        with unittest.mock.patch.dict(sys.modules, {"tortoise.context": None}):
            exec(code, namespace)

        assert namespace["_current_context"] is None


class TestSetupRecord:
    def test_wires_hooks_and_stores_the_manager(self):
        app = SilloApp()
        config = DatabaseConfig(url="sqlite://:memory:")

        manager = setup_record(app, config, model_modules=["tests.test_record.test_manager_lifecycle"])

        assert app.state["record"] is manager
        assert manager._model_modules == ["tests.test_record.test_manager_lifecycle"]

    def test_calling_it_again_returns_the_existing_manager(self):
        app = SilloApp()
        config = DatabaseConfig(url="sqlite://:memory:")

        first = setup_record(app, config)
        second = setup_record(app, DatabaseConfig(url="sqlite://:memory:"))

        assert first is second
