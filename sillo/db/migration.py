"""
sillo.db.migration — Custom migration engine.

Wraps ``aerich`` internally but exposes a sillo-native API with clean
command names: init, migrate, upgrade, downgrade, history.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional


class MigrationManager:
    """Manages database schema migrations.

    Internally delegates to ``aerich`` but provides a sillo-native
    interface with simpler command names and automatic config detection.

    Usage::

        mgr = MigrationManager(app_module="myapp.main:app")
        await mgr.init()
        await mgr.migrate("add users table")
        await mgr.upgrade()
    """

    def __init__(
        self,
        app_module: str,
        *,
        tortoise_config_module: Optional[str] = None,
        location: str = "migrations",
    ):
        self.app_module = app_module
        self.tortoise_config_module = tortoise_config_module or self._detect_config()
        self.location = Path(location)

    def _detect_config(self) -> str:
        """Try to find a Tortoise config in common locations."""
        candidates = [
            "settings.DATABASE_CONFIG",
            "config.DATABASE",
            "app.config.TORTOISE_ORM",
        ]
        for c in candidates:
            try:
                mod, _, attr = c.rpartition(".")
                __import__(mod)
                return c
            except ImportError:
                continue
        return "settings.TORTOISE_ORM"

    @property
    def _aerich_config(self) -> dict:
        return {
            "apps": {"models": {"models": ["aerich.models"]}},
            "connections": {"default": self.tortoise_config_module},
        }

    async def init(self, *, src_folder: str = ".") -> None:
        """Initialize aerich — creates migration table and config.

        This must be run once per project before any migrations.
        """
        from aerich import Command

        self.location.mkdir(parents=True, exist_ok=True)
        command = Command(
            tortoise_config=self._aerich_config,
            app="models",
            location=str(self.location),
        )
        await command.init_db(safe=True)
        print(f"[sillo.db] Migration system initialized in {self.location}/")

    async def migrate(self, name: str = "auto") -> str:
        """Generate a new migration file from model changes.

        Args:
            name: Human-readable migration name.

        Returns:
            The migration filename.
        """
        from aerich import Command

        command = Command(
            tortoise_config=self._aerich_config,
            app="models",
            location=str(self.location),
        )
        result = await command.migrate(name=name)
        migration_file = (
            f"{self.location}/models/{result}.py"
            if hasattr(command, "migrate")
            else str(result)
        )
        print(f"[sillo.db] Migration created: {migration_file}")
        return str(result) if result else ""

    async def upgrade(self, *, target: Optional[str] = None) -> None:
        """Apply pending migrations.

        Args:
            target: Specific migration to upgrade TO (default: latest).
        """
        from aerich import Command

        command = Command(
            tortoise_config=self._aerich_config,
            app="models",
            location=str(self.location),
        )
        if target:
            await command.upgrade(target_version=target)
        else:
            await command.upgrade()
        print("[sillo.db] Database upgraded to latest migration")

    async def downgrade(self, target: str) -> None:
        """Roll back to a specific migration.

        Args:
            target: Migration version to roll back TO.
        """
        from aerich import Command

        command = Command(
            tortoise_config=self._aerich_config,
            app="models",
            location=str(self.location),
        )
        await command.downgrade(target_version=target)
        print(f"[sillo.db] Database downgraded to {target}")

    async def history(self) -> list:
        """Show migration history."""
        from aerich import Command

        command = Command(
            tortoise_config=self._aerich_config,
            app="models",
            location=str(self.location),
        )
        return await command.history()

    async def heads(self) -> list:
        """Show current migration heads."""
        from aerich import Command

        command = Command(
            tortoise_config=self._aerich_config,
            app="models",
            location=str(self.location),
        )
        return await command.heads()
