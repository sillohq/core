"""
sillo.db.manager — Database connection lifecycle manager.

Handles Tortoise ORM initialization, connection pooling, and lifespan
hooks.  Designed to be registered once via :func:`setup_db` and accessed
from ``app.state["db"]``.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from tortoise import Tortoise, connections

from .types import DatabaseConfig

logger = logging.getLogger("sillo.db.manager")


class DatabaseManager:
    """Manages Tortoise ORM lifecycle for a sillo application.

    Usage::

        db = DatabaseManager(config)
        await db.init()
        # ... run app ...
        await db.shutdown()
    """

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._initialized = False

    async def init(self) -> None:
        """Initialize Tortoise ORM with the configured backend."""
        if self._initialized:
            return

        tortoise_config = self._build_tortoise_config()
        await Tortoise.init(config=tortoise_config)
        self._initialized = True
        logger.info("Database connected — backend=%s", self.config.backend.value)

    async def shutdown(self) -> None:
        """Close all connections gracefully."""
        if not self._initialized:
            return
        await connections.close_all()
        self._initialized = False
        logger.info("Database connections closed")

    async def health(self) -> bool:
        """Ping the database to verify connectivity."""
        try:
            conn = connections.get("default")
            await conn.execute_query("SELECT 1")
            return True
        except Exception:
            return False

    def _build_tortoise_config(self) -> dict:
        cfg = self.config
        conn_extra: Dict[str, Any] = {}
        if cfg.ssl:
            conn_extra.update({
                "ssl": True,
                "ssl_ca": cfg.ssl_ca,
                "ssl_cert": cfg.ssl_cert,
                "ssl_key": cfg.ssl_key,
            })

        return {
            "connections": {
                "default": {
                    "engine": f"tortoise.backends.{cfg.backend.value}",
                    "credentials": {
                        "database": cfg.url,
                        **conn_extra,
                    },
                }
            },
            "apps": {
                "default": {
                    "models": ["__main__"],
                    "default_connection": "default",
                }
            },
            "timezone": cfg.timezone,
        }

    def register_models(self, *modules: str) -> None:
        """Register additional model modules post-init.

        Call before :meth:`init` or re-init after.
        """
        overridden = Tortoise._inited
        if overridden:
            tortoise_config = Tortoise._config or {}
        else:
            tortoise_config = self._build_tortoise_config()

        apps = tortoise_config.setdefault("apps", {})
        default_app = apps.setdefault("default", {})
        existing = set(default_app.get("models", []))
        existing.update(modules)
        default_app["models"] = list(existing)

        if overridden:
            Tortoise._config = tortoise_config


def setup_db(app, config: DatabaseConfig) -> DatabaseManager:
    """Wire a DatabaseManager into the sillo application lifecycle.

    Stores the manager in ``app.state["db"]`` and registers startup/shutdown
    hooks so connections are opened before the first request and closed after
    the last.

    Usage::

        from sillo.db import setup_db, DatabaseConfig
        app = silloApp()
        setup_db(app, DatabaseConfig.sqlite("myapp.db"))
    """
    if "db" in app.state:
        return app.state["db"]

    manager = DatabaseManager(config)
    app.state["db"] = manager
    app.on_startup(manager.init)
    app.on_shutdown(manager.shutdown)
    return manager


def get_db(request) -> DatabaseManager:
    """Retrieve the DatabaseManager from the current request state.

    Usage in a handler::

        db = get_db(request)
        if await db.health():
            ...
    """
    manager = request.app.state.get("db")
    if manager is None:
        raise RuntimeError("Database not initialized. Call setup_db(app, config).")
    return manager
