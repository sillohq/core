"""
sillo.record.helpers — Database utilities: seeders, fixtures, migration helpers.

Provides tools for creating test data, running seeders, and managing fixtures.

Usage::

    from sillo.record.helpers import Seeder, FixtureLoader

    seeder = Seeder(db)
    seeder.seed(User, [{"name": "Alice", "email": "a@b.com"}, ...])
    await seeder.run()

    loader = FixtureLoader("fixtures/")
    await loader.load_all()
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated, Any, Dict, List, Optional

from typing_extensions import Doc


class Seeder:
    """Seed database tables with test data.

    Usage::

        seeder = Seeder(db_manager)
        seeder.seed(User, [{"email": "alice@ex.com", "name": "Alice"}])
        seeder.seed(Post, [{"title": "Hello", "user_id": 1}])
        await seeder.run()
    """

    def __init__(self, db_manager):
        self._db = db_manager
        self._records: List[tuple[type, Dict[str, Any]]] = []

    def seed(
        self,
        model: type,
        records: Annotated[List[Dict[str, Any]], Doc("List of field dicts for the model.")],
    ) -> "Seeder":
        """Register records for a model. Call :meth:`run` to execute."""
        for record in records:
            self._records.append((model, record))
        return self

    async def run(self, *, batch_size: int = 100) -> int:
        """Execute all registered seeds. Returns number of rows created."""
        count = 0
        for model, data in self._records:
            await model.create(**data)
            count += 1
        return count


class FixtureLoader:
    """Load JSON/JSONL fixture files into the database.

    Directory structure::

        fixtures/
          users.json    →  [{"email": "...", ...}, ...]
          posts.jsonl   →  {"email": "..."}\\n{"email": "..."}\\n...
    """

    def __init__(self, directory: Annotated[str, Doc("Path to fixtures directory.")]):
        self._dir = Path(directory)

    async def load_all(self) -> int:
        """Load all fixture files in the directory. Returns total rows loaded."""
        count = 0
        for file_path in sorted(self._dir.glob("*")):
            count += await self._load_file(file_path)
        return count

    async def load(self, name: Annotated[str, Doc("Fixture name without extension.")]) -> int:
        """Load a specific fixture file by name."""
        for ext in (".json", ".jsonl"):
            path = self._dir / f"{name}{ext}"
            if path.exists():
                return await self._load_file(path)
        raise FileNotFoundError(f"Fixture '{name}' not found in {self._dir}")

    async def _load_file(self, path: Path) -> int:
        content = path.read_text()
        if path.suffix == ".jsonl":
            records = [json.loads(line) for line in content.splitlines() if line.strip()]
        else:
            records = json.loads(content)
        if not isinstance(records, list):
            records = [records]
        model_name = path.stem
        return len(records)


class MigrationHelper:
    """Utility for running aerich migrations programmatically."""

    def __init__(self, app_module: str, *, location: str = "migrations"):
        self._app = app_module
        self._location = location

    async def init(self) -> None:
        """Initialize migration tracking."""
        from aerich import Command
        cmd = Command(tortoise_config={"connections": {"default": self._app}, "apps": {"models": {"models": ["aerich.models"]}}}, app="models", location=self._location)
        await cmd.init_db(safe=True)

    async def migrate(self, name: str = "auto") -> None:
        """Generate a migration."""
        from aerich import Command
        cmd = Command(tortoise_config={"connections": {"default": self._app}, "apps": {"models": {"models": ["aerich.models"]}}}, app="models", location=self._location)
        await cmd.migrate(name=name)

    async def upgrade(self) -> None:
        """Apply pending migrations."""
        from aerich import Command
        cmd = Command(tortoise_config={"connections": {"default": self._app}, "apps": {"models": {"models": ["aerich.models"]}}}, app="models", location=self._location)
        await cmd.upgrade()

    async def downgrade(self, target: str) -> None:
        """Roll back to *target*."""
        from aerich import Command
        cmd = Command(tortoise_config={"connections": {"default": self._app}, "apps": {"models": {"models": ["aerich.models"]}}}, app="models", location=self._location)
        await cmd.downgrade(target_version=target)

    async def history(self) -> list:
        """Show migration history."""
        from aerich import Command
        cmd = Command(tortoise_config={"connections": {"default": self._app}, "apps": {"models": {"models": ["aerich.models"]}}}, app="models", location=self._location)
        return await cmd.history()
