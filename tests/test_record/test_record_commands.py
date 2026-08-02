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

    database = tmp_path / "test.db"
    (tmp_path / "settings.py").write_text(
        textwrap.dedent(
            f"""
            TORTOISE_ORM = {{
                "connections": {{"default": "sqlite://{database}"}},
                "apps": {{
                    "models": {{
                        "models": ["models_pkg"],
                        "default_connection": "default",
                        "migrations": "migrations_pkg",
                    }}
                }},
            }}
            """
        )
    )

    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.chdir(tmp_path)
    yield tmp_path
    for name in ("settings", "models_pkg", "migrations_pkg"):
        sys.modules.pop(name, None)


class TestTortoiseConfig:
    def test_the_manager_exposes_the_config_it_runs_on(self):
        """So migrations use the application's settings, not a second copy."""
        manager = DatabaseManager(DatabaseConfig(url="sqlite://x.db"))
        manager.register_models("database.models")

        config = manager.tortoise_config()

        assert config["apps"]["models"]["models"] == ["database.models"]
        assert "connections" in config

    def test_the_migrations_package_is_included(self):
        """Without it Tortoise calls the app unmigrated and silently does nothing."""
        manager = DatabaseManager(DatabaseConfig(url="sqlite://x.db"))

        config = manager.tortoise_config("myproject.migrations")

        assert config["apps"]["models"]["migrations"] == "myproject.migrations"

    def test_it_defaults_to_the_conventional_location(self):
        manager = DatabaseManager(DatabaseConfig(url="sqlite://x.db"))

        assert manager.tortoise_config()["apps"]["models"]["migrations"] == (
            "database.migrations"
        )


class TestMigrationCommands:
    async def test_init_make_and_migrate_create_the_table(self, project):
        """The whole point: after this the table exists and is recorded."""
        import sqlite3

        await init("settings.TORTOISE_ORM")
        await make("settings.TORTOISE_ORM", "initial")
        await migrate("settings.TORTOISE_ORM")

        connection = sqlite3.connect(project / "test.db")
        tables = {row[0] for row in connection.execute(
            "select name from sqlite_master where type='table'"
        )}
        connection.close()

        assert "widgets" in tables
        # Applied migrations are recorded, so a second run is a no-op rather
        # than an attempt to create the table again.
        assert "tortoise_migrations" in tables

    async def test_make_writes_a_migration_file(self, project):
        await init("settings.TORTOISE_ORM")
        await make("settings.TORTOISE_ORM", "initial")

        written = [
            path.name
            for path in (project / "migrations_pkg").glob("*.py")
            if path.name != "__init__.py"
        ]
        assert written == ["0001_initial.py"]

    async def test_plan_lists_what_would_run_without_running_it(self, project):
        import sqlite3

        await init("settings.TORTOISE_ORM")
        await make("settings.TORTOISE_ORM", "initial")

        pending = await plan("settings.TORTOISE_ORM")
        assert any("0001_initial" in line for line in pending)

        connection = sqlite3.connect(project / "test.db")
        tables = {row[0] for row in connection.execute(
            "select name from sqlite_master where type='table'"
        )}
        connection.close()
        assert "widgets" not in tables

    async def test_plan_is_empty_once_everything_is_applied(self, project):
        await init("settings.TORTOISE_ORM")
        await make("settings.TORTOISE_ORM", "initial")
        await migrate("settings.TORTOISE_ORM")

        assert not [line for line in await plan("settings.TORTOISE_ORM") if "+" in line]

    async def test_a_config_mapping_works_as_well_as_a_path(self, project):
        """upgrade/plan take the config by value; only init and make need a path."""
        from settings import TORTOISE_ORM

        await init("settings.TORTOISE_ORM")
        await make("settings.TORTOISE_ORM", "initial")
        await migrate(TORTOISE_ORM)

        assert not [line for line in await plan(TORTOISE_ORM) if "+" in line]
