"""
sillo.record.transactions — Database transaction API with savepoints.

Provides a context-manager-based transaction API and manual begin/commit/rollback.

Usage::

    async with transaction():
        await user.save()
        await order.save()

    async with transaction() as tx:
        await user.save()
        async with tx.savepoint():
            await risky_operation()  # rolled back on failure
        await order.save()
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Annotated, Optional

from tortoise import connections
from typing_extensions import Doc

logger = logging.getLogger("sillo.record.transactions")


@asynccontextmanager
async def transaction(
    connection_name: Annotated[str, Doc("Connection name.")] = "default",
):
    """Execute a block within a database transaction.

    Commits on clean exit, rolls back on exception.

    Usage::

        async with transaction():
            await user.save()
            await order.save()
    """
    conn = connections.get(connection_name)
    try:
        async with conn._in_transaction() as tx:
            yield TransactionContext(conn, tx)
    except Exception:
        logger.exception("Transaction rolled back")
        raise


class TransactionContext:
    """Context for manual transaction management."""

    def __init__(self, conn, tx):
        """Init

        Args:
            conn: [description]
            tx: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        self._conn = conn
        self._tx = tx

    @asynccontextmanager
    async def savepoint(self):
        """Create a nested savepoint. Rolled back on exception."""
        try:
            savepoint_id = await self._conn.execute_insert("SAVEPOINT sp")
            yield
            await self._conn.execute_insert("RELEASE SAVEPOINT sp")
        except Exception:
            await self._conn.execute_insert("ROLLBACK TO SAVEPOINT sp")
            raise


async def begin(connection_name: str = "default") -> None:
    """Manually begin a transaction."""
    conn = connections.get(connection_name)
    await conn.execute_query("BEGIN")


async def commit(connection_name: str = "default") -> None:
    """Manually commit a transaction."""
    conn = connections.get(connection_name)
    await conn.execute_query("COMMIT")


async def rollback(connection_name: str = "default") -> None:
    """Manually rollback a transaction."""
    conn = connections.get(connection_name)
    await conn.execute_query("ROLLBACK")
