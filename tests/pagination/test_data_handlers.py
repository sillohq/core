import asyncio
from typing import Any, List

import pytest

from sillo.pagination import (
    AsyncDataHandler,
    AsyncListDataHandler,
    SyncDataHandler,
    SyncListDataHandler,
)


class TestSyncListDataHandler:
    """Test cases for SyncListDataHandler"""

    def test_get_total_items(self):
        """Test getting total items count"""
        data = [{"id": 1}, {"id": 2}, {"id": 3}]
        handler = SyncListDataHandler(data)

        total = handler.get_total_items()

        assert total == 3

    def test_get_total_items_empty_list(self):
        """Test getting total items count for empty list"""
        data = []
        handler = SyncListDataHandler(data)

        total = handler.get_total_items()

        assert total == 0

    def test_get_items_basic_slicing(self):
        """Test getting items with basic slicing"""
        data = [{"id": i} for i in range(1, 101)]  # 100 items
        handler = SyncListDataHandler(data)

        items = handler.get_items(10, 20)  # offset 10, limit 20

        assert len(items) == 20
        assert items[0]["id"] == 11  # 1-based indexing in our test data
        assert items[-1]["id"] == 30

    def test_get_items_partial_slice(self):
        """Test getting items when slice exceeds data length"""
        data = [{"id": 1}, {"id": 2}, {"id": 3}]
        handler = SyncListDataHandler(data)

        items = handler.get_items(2, 5)  # offset 2, limit 5 (only 1 item available)

        assert len(items) == 1
        assert items[0]["id"] == 3

    def test_get_items_beyond_data(self):
        """Test getting items when offset exceeds data length"""
        data = [{"id": 1}, {"id": 2}, {"id": 3}]
        handler = SyncListDataHandler(data)

        items = handler.get_items(10, 5)  # offset 10, limit 5 (no items available)

        assert len(items) == 0

    def test_get_items_zero_limit(self):
        """Test getting items with zero limit"""
        data = [{"id": 1}, {"id": 2}, {"id": 3}]
        handler = SyncListDataHandler(data)

        items = handler.get_items(0, 0)

        assert len(items) == 0

    def test_get_items_large_dataset(self):
        """Test getting items from large dataset"""
        data = [{"id": i} for i in range(1, 10001)]  # 10k items
        handler = SyncListDataHandler(data)

        items = handler.get_items(5000, 100)

        assert len(items) == 100
        assert items[0]["id"] == 5001
        assert items[-1]["id"] == 5100


class TestAsyncListDataHandler:
    """Test cases for AsyncListDataHandler"""

    def test_get_total_items(self):
        """Test getting total items count"""
        data = [{"id": 1}, {"id": 2}, {"id": 3}]
        handler = AsyncListDataHandler(data)

        async def run_test():
            total = await handler.get_total_items()
            assert total == 3

        asyncio.run(run_test())

    def test_get_total_items_empty_list(self):
        """Test getting total items count for empty list"""
        data = []
        handler = AsyncListDataHandler(data)

        async def run_test():
            total = await handler.get_total_items()
            assert total == 0

        asyncio.run(run_test())

    def test_get_items_basic_slicing(self):
        """Test getting items with basic slicing"""
        data = [{"id": i} for i in range(1, 101)]  # 100 items
        handler = AsyncListDataHandler(data)

        async def run_test():
            items = await handler.get_items(10, 20)  # offset 10, limit 20

            assert len(items) == 20
            assert items[0]["id"] == 11  # 1-based indexing in our test data
            assert items[-1]["id"] == 30

        asyncio.run(run_test())

    def test_get_items_partial_slice(self):
        """Test getting items when slice exceeds data length"""
        data = [{"id": 1}, {"id": 2}, {"id": 3}]
        handler = AsyncListDataHandler(data)

        async def run_test():
            items = await handler.get_items(
                2, 5
            )  # offset 2, limit 5 (only 1 item available)

            assert len(items) == 1
            assert items[0]["id"] == 3

        asyncio.run(run_test())

    def test_get_items_beyond_data(self):
        """Test getting items when offset exceeds data length"""
        data = [{"id": 1}, {"id": 2}, {"id": 3}]
        handler = AsyncListDataHandler(data)

        async def run_test():
            items = await handler.get_items(
                10, 5
            )  # offset 10, limit 5 (no items available)

            assert len(items) == 0

        asyncio.run(run_test())

    def test_get_items_zero_limit(self):
        """Test getting items with zero limit"""
        data = [{"id": 1}, {"id": 2}, {"id": 3}]
        handler = AsyncListDataHandler(data)

        async def run_test():
            items = await handler.get_items(0, 0)

            assert len(items) == 0

        asyncio.run(run_test())

    def test_get_items_large_dataset(self):
        """Test getting items from large dataset"""
        data = [{"id": i} for i in range(1, 10001)]  # 10k items
        handler = AsyncListDataHandler(data)

        async def run_test():
            items = await handler.get_items(5000, 100)

            assert len(items) == 100
            assert items[0]["id"] == 5001
            assert items[-1]["id"] == 5100

        asyncio.run(run_test())


class TestCustomDataHandlers:
    """Test cases for custom data handler implementations"""

    def test_sync_custom_handler(self):
        """Test custom sync data handler implementation"""

        class CustomSyncHandler(SyncDataHandler):
            def __init__(self, data):
                self.data = data

            def get_total_items(self) -> int:
                return len(self.data)

            def get_items(self, offset: int, limit: int) -> List[Any]:
                # Custom logic: reverse the data
                reversed_data = list(reversed(self.data))
                return reversed_data[offset : offset + limit]

        data = [{"id": 1}, {"id": 2}, {"id": 3}, {"id": 4}, {"id": 5}]
        handler = CustomSyncHandler(data)

        total = handler.get_total_items()
        assert total == 5

        items = handler.get_items(1, 3)
        assert len(items) == 3
        assert items[0]["id"] == 4  # Reversed order
        assert items[1]["id"] == 3
        assert items[2]["id"] == 2

    def test_async_custom_handler(self):
        """Test custom async data handler implementation"""

        class CustomAsyncHandler(AsyncDataHandler):
            def __init__(self, data):
                self.data = data

            async def get_total_items(self) -> int:
                return len(self.data)

            async def get_items(self, offset: int, limit: int) -> List[Any]:
                # Custom logic: filter even IDs only
                filtered = [item for item in self.data if item["id"] % 2 == 0]
                return filtered[offset : offset + limit]

        data = [{"id": i} for i in range(1, 11)]  # IDs 1-10
        handler = CustomAsyncHandler(data)

        async def run_test():
            total = await handler.get_total_items()
            assert total == 10

            items = await handler.get_items(0, 5)
            assert len(items) == 5
            assert items[0]["id"] == 2  # First even ID
            assert items[1]["id"] == 4
            assert items[2]["id"] == 6
            assert items[3]["id"] == 8
            assert items[4]["id"] == 10

        asyncio.run(run_test())
