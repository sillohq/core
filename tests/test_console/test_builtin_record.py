"""The migration commands, driven through a console against a real database.

The migration engine writes files and touches a database, so these use a real
temporary project rather than mocks — the failure worth catching is "reported
success but nothing happened", which a mock cannot show.
"""

from __future__ import annotations

import io
import sqlite3
import sys
import textwrap

import pytest

from sillo.console import Console, strip_ansi
from sillo.record import DatabaseConfig, DatabaseManager
from sillo.record.console import record_commands


@pytest.fixture
def project(tmp_path, monkeypatch):
    """A minimal importable project with one model."""
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
    """A manager for the temporary project."""

    def build():
        manager = DatabaseManager(DatabaseConfig(url=f"sqlite://{project / 'test.db'}"))
        manager.register_models("models_pkg").set_migrations("migrations_pkg")
        return manager

    return build


@pytest.fixture
def console(database):
    """A console with the migration commands and a captured stream."""
    stream = io.StringIO()
    built = Console(
        prog="console.py",
        output=stream,
        error=stream,
        input=io.StringIO(),
        color=False,
        interactive=False,
    )
    built.add_many(record_commands(database))
    return built, stream


def written(stream) -> str:
    """What the console wrote, unstyled."""
    return strip_ansi(stream.getvalue())


def tables(project) -> set:
    """The tables that exist in the project's database."""
    connection = sqlite3.connect(project / "test.db")
    try:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    finally:
        connection.close()
    return {row[0] for row in rows}


async def prepare(console) -> None:
    """Take a fresh project as far as one written migration."""
    built, _ = console
    await built.run_async(["db:init"])
    await built.run_async(["db:make", "initial"])


# -- the workflow ------------------------------------------------------


async def test_init_creates_the_migration_package(console, project):
    built, stream = console

    assert await built.run_async(["db:init"]) == 0
    assert "Migration package ready." in written(stream)


async def test_make_writes_a_migration_file(console, project):
    built, stream = console
    await built.run_async(["db:init"])

    assert await built.run_async(["db:make", "initial"]) == 0

    written_files = list((project / "migrations_pkg").rglob("*.py"))
    assert any("initial" in path.name for path in written_files)


async def test_make_points_at_the_command_that_applies_it(console, project):
    built, stream = console
    await built.run_async(["db:init"])

    await built.run_async(["db:make", "initial"])

    assert "console.py db:migrate" in written(stream)


async def test_migrate_creates_the_table(console, project):
    built, _ = console
    await prepare(console)

    assert await built.run_async(["db:migrate"]) == 0
    assert "widgets" in tables(project)


async def test_make_can_apply_what_it_writes(console, project):
    built, stream = console
    await built.run_async(["db:init"])

    assert await built.run_async(["db:make", "initial", "--apply"]) == 0
    assert "written and applied" in written(stream)
    assert "widgets" in tables(project)


async def test_migrate_lists_what_it_is_about_to_run(console, project):
    built, stream = console
    await prepare(console)

    await built.run_async(["db:migrate"])
    text = written(stream)

    assert "initial" in text
    assert "Applied 1 migration." in text


async def test_migrate_says_so_when_there_is_nothing_to_do(console, project):
    built, stream = console
    await prepare(console)
    await built.run_async(["db:migrate"])

    stream.truncate(0)
    stream.seek(0)
    assert await built.run_async(["db:migrate"]) == 0
    assert "Nothing pending." in written(stream)


async def test_a_faked_migration_records_without_creating_the_table(console, project):
    built, stream = console
    await prepare(console)

    assert await built.run_async(["db:migrate", "--fake"]) == 0
    assert "without running" in written(stream)
    assert "widgets" not in tables(project)


# -- inspecting --------------------------------------------------------


async def test_plan_shows_pending_migrations_without_running_them(console, project):
    built, stream = console
    await prepare(console)

    assert await built.run_async(["db:plan"]) == 0

    assert "1 migration pending:" in written(stream)
    assert "widgets" not in tables(project)


async def test_plan_says_so_when_nothing_is_pending(console, project):
    built, stream = console
    await prepare(console)
    await built.run_async(["db:migrate"])

    stream.truncate(0)
    stream.seek(0)
    await built.run_async(["db:plan"])

    assert "Nothing pending." in written(stream)


async def test_status_reports_an_up_to_date_database(console, project):
    built, stream = console
    await prepare(console)
    await built.run_async(["db:migrate"])

    stream.truncate(0)
    stream.seek(0)
    assert await built.run_async(["db:status"]) == 0
    assert "Up to date." in written(stream)


async def test_status_reports_pending_work(console, project):
    built, stream = console
    await prepare(console)

    await built.run_async(["db:status"])
    text = written(stream)

    assert "not applied" in text
    assert "pending" in text


async def test_sql_shows_the_statements_without_running_them(console, project):
    built, stream = console
    await prepare(console)

    assert await built.run_async(["db:sql", "0001_initial"]) == 0

    assert "widgets" in written(stream).lower()
    assert "widgets" not in tables(project)


# -- rolling back ------------------------------------------------------


async def test_rollback_to_a_named_migration_runs_without_confirmation(
    console, project
):
    built, stream = console
    await prepare(console)
    await built.run_async(["db:migrate"])

    assert await built.run_async(["db:rollback", "0001_initial"]) == 0
    assert "Rolled back to 0001_initial." in written(stream)


async def test_rollback_to_zero_refuses_without_a_terminal(console, project):
    # confirm_destructive returns False when there is nobody to type the
    # phrase, so an unattended run cannot drop the schema by accident.
    built, stream = console
    await prepare(console)
    await built.run_async(["db:migrate"])

    assert await built.run_async(["db:rollback", "zero"]) == 1
    assert "Nothing done." in written(stream)
    assert "widgets" in tables(project)


async def test_the_force_flag_skips_the_confirmation(console, project):
    built, _ = console
    await prepare(console)
    await built.run_async(["db:migrate"])

    assert await built.run_async(["db:rollback", "zero", "--force"]) == 0
    assert "widgets" not in tables(project)


async def test_typing_the_phrase_confirms_the_rollback(project, database):
    stream = io.StringIO()
    built = Console(
        output=stream,
        error=stream,
        input=io.StringIO("zero\n"),
        color=False,
        interactive=True,
    )
    built.add_many(record_commands(database))

    await built.run_async(["db:init"])
    await built.run_async(["db:make", "initial"])
    await built.run_async(["db:migrate"])

    assert await built.run_async(["db:rollback", "zero"]) == 0
    assert "widgets" not in tables(project)


# -- binding -----------------------------------------------------------


def test_a_database_instance_works_as_well_as_a_factory(project):
    manager = DatabaseManager(DatabaseConfig(url=f"sqlite://{project / 'test.db'}"))
    commands = record_commands(manager)

    assert commands[0].config.resolve() is manager


def test_an_unbound_command_says_how_to_register_it():
    from sillo.record.console import Migrate

    stream = io.StringIO()
    built = Console(output=stream, error=stream, color=False, interactive=False)
    built.add(Migrate)

    with pytest.raises(RuntimeError, match="record_commands"):
        built.run(["db:migrate"])


def test_only_registers_the_named_commands(database):
    stream = io.StringIO()
    built = Console(output=stream, error=stream, color=False, interactive=False)
    built.add_many(record_commands(database, only=["db:migrate", "db:make"]))

    assert set(built.commands) == {"db:migrate", "db:make"}


def test_only_rejects_a_name_it_does_not_define(database):
    with pytest.raises(ValueError, match="record_commands has no 'db:nope'"):
        record_commands(database, only=["db:nope"])


def test_the_app_label_is_carried_through(database):
    commands = record_commands(database, app="billing")

    assert commands[0].config.app == "billing"


async def test_make_says_so_when_there_is_nothing_to_record(console, project):
    """``make`` writes no file when the models already match the last
    migration, and reports that only through the engine's own stdout. Without
    checking, the command printed "Migration written." for a file that was
    never created.
    """
    built, stream = console
    await prepare(console)
    await built.run_async(["db:migrate"])

    stream.truncate(0)
    stream.seek(0)
    assert await built.run_async(["db:make", "again"]) == 0
    text = written(stream)

    assert "No model changes to record." in text
    assert "Migration written." not in text
