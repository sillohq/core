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

from aerich import Command


class Seeder:
    """Seed database tables with test data.

    Usage::

        seeder = Seeder(db_manager)
        seeder.seed(User, [{"email": "alice@ex.com", "name": "Alice"}])
        seeder.seed(Post, [{"title": "Hello", "user_id": 1}])
        await seeder.run()
    """

    def __init__(self, db_manager):
        """Init

        Args:
            db_manager: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        self._db = db_manager
        self._records: List[tuple[type, Dict[str, Any]]] = []

    def seed(
        self,
        model: type,
        records: Annotated[
            List[Dict[str, Any]], Doc("List of field dicts for the model.")
        ],
    ) -> "Seeder":
        """Register records for a model. Call :meth:`run` to execute."""
        for record in records:
            self._records.append((model, record))
        return self

    async def run(self, *, batch_size: int = 100) -> int:
        """Execute all registered seeds. Returns number of rows created."""
        count = 0
        for model, data in self._records:
            await model.create(**data)  # ty: ignore[unresolved-attribute]
            count += 1
        return count


class FixtureLoader:
    """Load JSON/JSONL fixture files into the database.

    Directory structure::

        fixtures/
          users.json    →  [{"email": "...", ...}, ...]
          posts.jsonl   →  {"email": "..."}\\n{"email": "..."}\\n...
    """

    #: File extensions ``load_all`` will read. Anything else is ignored.
    SUFFIXES = (".json", ".jsonl")

    def __init__(
        self,
        directory: Annotated[str, Doc("Path to fixtures directory.")],
        *,
        models: Annotated[
            Optional[Dict[str, Any]],
            Doc(
                "Explicit fixture-name to model mapping. Names not listed here "
                "are resolved against Tortoise's model registry."
            ),
        ] = None,
    ):
        """Initialize the loader.

        Args:
            directory: Directory containing the fixture files.
            models: Optional mapping of fixture stem to model class, for cases
                where the filename does not match the model name.
        """
        self._dir = Path(directory)
        self._models: Dict[str, Any] = dict(models or {})

    async def load_all(self) -> int:
        """Load every fixture file in the directory.

        Files are loaded in sorted order, so a numeric prefix
        (``01_users.json``, ``02_posts.json``) is how you control the order
        when fixtures reference each other. Files whose suffix is not in
        :attr:`SUFFIXES` are skipped.

        Returns:
            The total number of rows inserted.
        """
        count = 0
        for file_path in sorted(self._dir.glob("*")):
            if file_path.suffix not in self.SUFFIXES or not file_path.is_file():
                continue
            count += await self._load_file(file_path)
        return count

    async def load(
        self, name: Annotated[str, Doc("Fixture name without extension.")]
    ) -> int:
        """Load a specific fixture file by name.

        Returns:
            The number of rows inserted.

        Raises:
            FileNotFoundError: If no fixture with that name exists.
        """
        for ext in self.SUFFIXES:
            path = self._dir / f"{name}{ext}"
            if path.exists():
                return await self._load_file(path)
        raise FileNotFoundError(f"Fixture '{name}' not found in {self._dir}")

    async def _load_file(self, path: Path) -> int:
        """Read one fixture file and insert its rows.

        The whole file is inserted inside a transaction, so a row that fails
        validation or violates a constraint leaves the table untouched rather
        than half-populated.

        Args:
            path: The fixture file to read.

        Returns:
            The number of rows inserted.

        Raises:
            LookupError: If the fixture name matches no registered model.
        """
        records = self._parse(path)
        if not records:
            return 0

        model = self._resolve_model(path.stem)

        from tortoise.transactions import in_transaction

        async with in_transaction():
            for record in records:
                await model.create(**record)
        return len(records)

    def _parse(self, path: Path) -> List[Dict[str, Any]]:
        """Decode a fixture file into a list of row dicts.

        Args:
            path: The fixture file to read.

        Returns:
            The rows the file describes. A JSON file holding a single object
            is treated as a one-row fixture.
        """
        content = path.read_text()
        if path.suffix == ".jsonl":
            records = [
                json.loads(line) for line in content.splitlines() if line.strip()
            ]
        else:
            records = json.loads(content)
        if not isinstance(records, list):
            records = [records]
        return records

    def _resolve_model(self, name: str) -> Any:
        """Find the model a fixture file belongs to.

        An explicit entry in the ``models`` mapping always wins. Otherwise the
        filename stem is matched against the registered model names, ignoring
        case and a trailing plural — so ``users.json`` finds ``User`` and
        ``categories.jsonl`` finds ``Category``.

        Args:
            name: The fixture filename without its extension.

        Returns:
            The model class to insert into.

        Raises:
            LookupError: If nothing matches, listing what is registered.
        """
        if name in self._models:
            return self._models[name]

        from tortoise import Tortoise

        registry = {
            model_name.lower(): model
            for app_models in Tortoise.apps.values()
            for model_name, model in app_models.items()
        }

        stem = name.lower()
        candidates = [stem]
        if stem.endswith("ies"):
            candidates.append(stem[:-3] + "y")
        if stem.endswith("es"):
            candidates.append(stem[:-2])
        if stem.endswith("s"):
            candidates.append(stem[:-1])

        for candidate in candidates:
            if candidate in registry:
                return registry[candidate]

        known = ", ".join(sorted(registry)) or "none — has Tortoise been initialised?"
        raise LookupError(
            f"Fixture '{name}' matches no registered model. Known models: {known}. "
            f"Pass FixtureLoader(..., models={{'{name}': YourModel}}) to map it explicitly."
        )


class MigrationHelper:
    """Utility for running aerich migrations programmatically."""

    def __init__(self, app_module: str, *, location: str = "migrations"):
        """Init

        Args:
            app_module: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        self._app = app_module
        self._location = location

    async def init(self) -> None:
        """Initialize migration tracking."""
        cmd = Command(
            tortoise_config={
                "connections": {"default": self._app},
                "apps": {"models": {"models": ["aerich.models"]}},
            },
            app="models",
            location=self._location,
        )
        await cmd.init_db(safe=True)

    async def migrate(self, name: str = "auto") -> None:
        """Generate a migration."""
        cmd = Command(
            tortoise_config={
                "connections": {"default": self._app},
                "apps": {"models": {"models": ["aerich.models"]}},
            },
            app="models",
            location=self._location,
        )
        await cmd.migrate(name=name)

    async def upgrade(self) -> None:
        """Apply pending migrations."""
        cmd = Command(
            tortoise_config={
                "connections": {"default": self._app},
                "apps": {"models": {"models": ["aerich.models"]}},
            },
            app="models",
            location=self._location,
        )
        await cmd.upgrade()

    async def downgrade(self, target: str) -> None:
        """Roll back to *target*."""
        cmd = Command(
            tortoise_config={
                "connections": {"default": self._app},
                "apps": {"models": {"models": ["aerich.models"]}},
            },
            app="models",
            location=self._location,
        )
        await cmd.downgrade(target, delete=False)  # ty: ignore[invalid-argument-type]

    async def history(self) -> list:
        """Show migration history."""
        cmd = Command(
            tortoise_config={
                "connections": {"default": self._app},
                "apps": {"models": {"models": ["aerich.models"]}},
            },
            app="models",
            location=self._location,
        )
        return await cmd.history()
