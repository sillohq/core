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


async def test_a_driver_without_signing_support_says_so():
    """MemoryDriver has no signer, so it falls through to the base class's
    default signed_url(), which refuses rather than returning a URL that
    would not work."""
    driver = MemoryDriver()
    with pytest.raises(NotImplementedError, match="cannot sign URLs"):
        driver.signed_url("a.txt")


def test_driver_repr():
    driver = MemoryDriver()
    assert repr(driver) == "MemoryDriver(name='memory')"


async def test_collect_raises_when_the_limit_is_exceeded():
    from sillo.storage.base import chunks, collect

    with pytest.raises(ValueError, match="exceeded 3 bytes"):
        await collect(chunks(b"way too much"), limit=3)
