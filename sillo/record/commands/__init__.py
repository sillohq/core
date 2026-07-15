"""
sillo.record.commands — CLI commands for database migrations and seeding.

Provides ``sillo record init``, ``sillo record migrate``, ``sillo record upgrade``,
etc. — wrapping aerich with sillo-native command names.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated, Optional

from typing_extensions import Doc


class RecordCLI:
    """Command-line interface for sillo.record migrations.

    Usage (in your CLI entry point)::

        cli = RecordCLI(app_module="myapp.models", location="migrations")
        cli.register(click_group)
    """

    def __init__(
        self,
        app_module: Annotated[str, Doc("Dotted path to the Tortoise config or app.")],
        *,
        location: Annotated[str, Doc("Directory for migration files.")] = "migrations",
    ):
        self._app = app_module
        self._location = Path(location)

    def register(self, group) -> None:
        """Register sub-commands on a Click group."""
        import click

        @group.group(name="record")
        def record_group():
            """Database migration and seeding commands."""
            pass

        @record_group.command()
        def init():
            """Initialize migration tracking."""
            from sillo.record.helpers import MigrationHelper
            asyncio.run(MigrationHelper(self._app, location=str(self._location)).init())
            click.echo(f"Migration tracking initialized in {self._location}/")

        @record_group.command()
        @click.option("--name", "-n", default="auto", help="Migration name.")
        def migrate(name):
            """Generate a new migration."""
            from sillo.record.helpers import MigrationHelper
            asyncio.run(MigrationHelper(self._app, location=str(self._location)).migrate(name))
            click.echo("Migration created.")

        @record_group.command()
        def upgrade():
            """Apply pending migrations."""
            from sillo.record.helpers import MigrationHelper
            asyncio.run(MigrationHelper(self._app, location=str(self._location)).upgrade())
            click.echo("Database upgraded.")

        @record_group.command()
        @click.argument("target")
        def downgrade(target):
            """Roll back to a specific migration."""
            from sillo.record.helpers import MigrationHelper
            asyncio.run(MigrationHelper(self._app, location=str(self._location)).downgrade(target))
            click.echo(f"Rolled back to {target}.")

        @record_group.command()
        def history():
            """Show migration history."""
            from sillo.record.helpers import MigrationHelper
            result = asyncio.run(MigrationHelper(self._app, location=str(self._location)).history())
            for r in result:
                click.echo(r)
