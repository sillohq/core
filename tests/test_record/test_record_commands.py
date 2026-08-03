"""
sillo.record.commands — migrations as plain functions, and the config they run on.

The migration engine writes files and touches a database, so these tests use a
real temporary project rather than mocks: the failures worth catching here are
"nothing happened but it reported success", which a mock cannot show.
"""

import sys
import textwrap
from pathlib import Path

import pytest

from sillo.record import DatabaseConfig, DatabaseManager
from sillo.record.commands import init, make, migrate, plan


@pytest.fixture
def project(tmp_path, monkeypatch):
    """A minimal importable project with one model and a config module."""
    (tmp_path / "models_pkg").mkdir()
    (tmp_path / "models_pkg" / "__init__.py").write_text(
        textwrap.dedent(
            """
            from tortoise import fields
            from tortoise.models import Model


            class Widget(Model):
                id = fields.IntField(primary_key=True)
                name = fields.CharField(max_length=50)

                class Meta:
                    table = "widgets"
            """
        )
    )
    (tmp_path / "migrations_pkg").mkdir()

    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.chdir(tmp_path)
    yield tmp_path
    for name in ("models_pkg", "migrations_pkg"):
        sys.modules.pop(name, None)


@pytest.fixture
def database(project):
    """A manager for the temporary project — how a real project drives this."""
    manager = DatabaseManager(DatabaseConfig(url=f"sqlite://{project / 'test.db'}"))
    manager.register_models("models_pkg").set_migrations("migrations_pkg")
    return manager


def tables(project):
    """The tables that exist in the project's database."""
    import sqlite3

    connection = sqlite3.connect(project / "test.db")
    try:
        return {
            row[0]
            for row in connection.execute(
                "select name from sqlite_master where type='table'"
            )
        }
    finally:
        connection.close()


class TestManagerConfiguration:
    def test_the_manager_exposes_the_config_it_runs_on(self):
        """So migrations use the application's settings, not a second copy."""
        manager = DatabaseManager(DatabaseConfig(url="sqlite://x.db"))
        manager.register_models("database.models")

        config = manager.orm_config()

        assert config["apps"]["models"]["models"] == ["database.models"]
        assert "connections" in config

    def test_the_migrations_package_is_included(self):
        """Without it the app is treated as unmigrated and nothing happens."""
        manager = DatabaseManager(DatabaseConfig(url="sqlite://x.db"))

        manager.set_migrations("myproject.migrations")

        assert manager.orm_config()["apps"]["models"]["migrations"] == (
            "myproject.migrations"
        )

    def test_it_defaults_to_the_conventional_location(self):
        manager = DatabaseManager(DatabaseConfig(url="sqlite://x.db"))

        assert manager.orm_config()["apps"]["models"]["migrations"] == (
            "database.migrations"
        )

    def test_registration_chains(self):
        """So a project's database module is one expression, not four statements."""
        manager = DatabaseManager(DatabaseConfig(url="sqlite://x.db"))

        assert manager.register_models("a").set_migrations("b") is manager


class TestMigrationCommands:
    async def test_init_make_and_migrate_create_the_table(self, project, database):
        """The whole point: after this the table exists and is recorded."""
        await init(database)
        await make(database, "initial")
        await migrate(database)

        assert "widgets" in tables(project)
        # Applied migrations are recorded, so a second run is a no-op rather
        # than an attempt to create the table again.
        assert "tortoise_migrations" in tables(project)

    async def test_make_writes_a_migration_file(self, project, database):
        await init(database)
        await make(database, "initial")

        written = [
            path.name
            for path in (project / "migrations_pkg").glob("*.py")
            if path.name != "__init__.py"
        ]
        assert written == ["0001_initial.py"]

    async def test_plan_lists_what_would_run_without_running_it(self, project, database):
        await init(database)
        await make(database, "initial")

        pending = await plan(database)
        assert any("0001_initial" in line for line in pending)

        assert "widgets" not in tables(project)

    async def test_plan_is_empty_once_everything_is_applied(self, database):
        await init(database)
        await make(database, "initial")
        await migrate(database)

        assert not [line for line in await plan(database) if "+" in line]

    async def test_a_config_mapping_works_as_well_as_a_manager(self, database):
        """Tooling that has only the resolved mapping is still served."""
        config = database.orm_config()

        await init(config)
        await make(config, "initial")
        await migrate(config)

        assert not [line for line in await plan(config) if "+" in line]

    async def test_a_dotted_path_still_works(self, project, database, monkeypatch):
        """The old form: a module exporting the mapping, named in a string."""
        (project / "settings.py").write_text(
            textwrap.dedent(
                f"""
                CONFIG = {database.orm_config()!r}
                """
            )
        )

        await init("settings.CONFIG")
        await make("settings.CONFIG", "initial")
        await migrate("settings.CONFIG")

        sys.modules.pop("settings", None)
        assert "widgets" in tables(project)

    async def test_writing_a_migration_needs_no_config_module(self, project, database):
        """``make`` used to demand a dotted path, because the engine's command
        layer reads its config by import. sillo publishes the config itself now,
        so a project needs no module written for the migration engine's benefit.
        """
        await init(database)
        await make(database, "initial")

        assert not (project / "settings.py").exists()
        assert (project / "migrations_pkg" / "0001_initial.py").exists()
