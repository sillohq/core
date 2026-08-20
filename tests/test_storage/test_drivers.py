"""Every shipped driver, against the one contract."""

from __future__ import annotations

import pytest

from sillo.storage.drivers import LocalDriver, MemoryDriver

from .contract import DriverContract


class TestMemoryDriver(DriverContract):
    """The fake, which is held to exactly the contract production is."""

    @pytest.fixture
    async def driver(self):
        built = MemoryDriver()
        yield built
        await built.close()


class TestLocalDriver(DriverContract):
    """Files on disk."""

    @pytest.fixture
    async def driver(self, tmp_path):
        built = LocalDriver(tmp_path)
        yield built
        await built.close()
