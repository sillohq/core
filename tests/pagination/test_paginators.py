from typing import Any, Dict

import pytest

from sillo.pagination import (
    AsyncListDataHandler,
    AsyncPaginator,
    CursorPagination,
    InvalidPageError,
    InvalidPageSizeError,
    LimitOffsetPagination,
    PageNumberPagination,
    SyncListDataHandler,
    SyncPaginator,
)


class TestSyncPaginator:
    """Test cases for SyncPaginator"""

    def test_paginate_basic_page_number(self):
        """Test basic pagination with page number strategy"""
        data = [{"id": i} for i in range(1, 101)]  # 100 items
        handler = SyncListDataHandler(data)
        pagination = PageNumberPagination(default_page=10)
        base_url = "http://example.com/api/items"
        request_params = {"page": "2", "page_size": "10"}

        paginator = SyncPaginator(handler, pagination, base_url, request_params)

        result = paginator.paginate()

        assert "items" in result
        assert "pagination" in result
        assert len(result["items"]) == 10
        assert result["items"][0]["id"] == 11  # Second page starts at 11
        assert result["pagination"]["total_items"] == 100
        assert result["pagination"]["page"] == 2
        assert result["pagination"]["total_pages"] == 10

    def test_paginate_basic_limit_offset(self):
        """Test basic pagination with limit offset strategy"""
        data = [{"id": i} for i in range(1, 101)]  # 100 items
        handler = SyncListDataHandler(data)
        pagination = LimitOffsetPagination(default_limit=15)
        base_url = "http://example.com/api/items"
        request_params = {"limit": "15", "offset": "30"}

        paginator = SyncPaginator(handler, pagination, base_url, request_params)

        result = paginator.paginate()

        assert "items" in result
        assert "pagination" in result
        assert len(result["items"]) == 15
        assert result["items"][0]["id"] == 31  # Offset 30, first item is 31
        assert result["pagination"]["total_items"] == 100
        assert result["pagination"]["offset"] == 30
        assert result["pagination"]["limit"] == 15

    def test_paginate_basic_cursor(self):
        """Test basic pagination with cursor strategy"""
        data = [{"id": i} for i in range(1, 101)]  # 100 items
        handler = SyncListDataHandler(data)
        pagination = CursorPagination(default_page_size=10)
        base_url = "http://example.com/api/items"
        request_params = {"page_size": "10"}

        paginator = SyncPaginator(handler, pagination, base_url, request_params)

        result = paginator.paginate()

        assert "items" in result
        assert "pagination" in result
        assert len(result["items"]) == 10
        assert result["items"][0]["id"] == 1  # First page
        assert result["pagination"]["total_items"] == 100
        assert result["pagination"]["cursor"] is None  # No cursor for first page
        assert "next" in result["pagination"]["links"]
        assert "prev" not in result["pagination"]["links"]

    def test_paginate_with_cursor_navigation(self):
        """Test pagination with cursor navigation"""
        data = [{"id": i} for i in range(1, 101)]  # 100 items
        handler = SyncListDataHandler(data)
        pagination = CursorPagination(default_page_size=10)
        base_url = "http://example.com/api/items"

        # First, get the first page to extract cursor
        first_paginator = SyncPaginator(
            handler, pagination, base_url, {"page_size": "10"}
        )
        first_result = first_paginator.paginate()

        # Extract cursor from first page
        next_cursor = (
            first_result["pagination"]["links"]["next"]
            .split("cursor=")[1]
            .split("&")[0]
        )
        print("next_cursor:", next_cursor)
        # Use cursor for second page
        request_params = {"cursor": next_cursor, "page_size": "10"}
        second_paginator = SyncPaginator(handler, pagination, base_url, request_params)
        second_result = second_paginator.paginate()
        print("second_result:", second_result)
        assert len(second_result["items"]) == 10
        # assert second_result["items"][1]["id"] == 11  # Second page starts at 11
        assert second_result["pagination"]["cursor"] == next_cursor
        assert "next" in second_result["pagination"]["links"]
        assert "prev" in second_result["pagination"]["links"]

    def test_paginate_empty_data(self):
        """Test pagination with empty data"""
        data = []
        handler = SyncListDataHandler(data)
        pagination = PageNumberPagination()
        base_url = "http://example.com/api/items"
        request_params = {"page": "1", "page_size": "10"}

        paginator = SyncPaginator(handler, pagination, base_url, request_params)

        result = paginator.paginate()

        assert result["items"] == []
        assert result["pagination"]["total_items"] == 0
        assert result["pagination"]["total_pages"] == 0

    def test_paginate_single_item(self):
        """Test pagination with single item"""
        data = [{"id": 1}]
        handler = SyncListDataHandler(data)
        pagination = PageNumberPagination()
        base_url = "http://example.com/api/items"
        request_params = {"page": "1", "page_size": "10"}

        paginator = SyncPaginator(handler, pagination, base_url, request_params)

        result = paginator.paginate()

        assert len(result["items"]) == 1
        assert result["items"][0]["id"] == 1
        assert result["pagination"]["total_items"] == 1
        assert result["pagination"]["total_pages"] == 1

    def test_paginate_invalid_offset_exceeds_total(self):
        """Test pagination when offset exceeds total items"""
        data = [{"id": 1}, {"id": 2}]
        handler = SyncListDataHandler(data)
        pagination = LimitOffsetPagination()
        base_url = "http://example.com/api/items"
        request_params = {"limit": "10", "offset": "10"}

        paginator = SyncPaginator(handler, pagination, base_url, request_params)

        # Should return empty items but valid metadata
        with pytest.raises(InvalidPageError):
            paginator.paginate()

    def test_paginate_invalid_offset_exceeds_total_with_validation(self):
        """Test pagination when offset exceeds total items with validation enabled"""
        data = [{"id": 1}, {"id": 2}]
        handler = SyncListDataHandler(data)
        pagination = LimitOffsetPagination()
        base_url = "http://example.com/api/items"
        request_params = {"limit": "10", "offset": "10"}

        paginator = SyncPaginator(
            handler, pagination, base_url, request_params, validate_total_items=True
        )

        # Should raise error when validation is enabled and offset exceeds total
        with pytest.raises(
            InvalidPageError, match="Requested offset exceeds total items"
        ):
            paginator.paginate()

    def test_paginate_with_filters_preserved(self):
        """Test pagination with query filters preserved in links"""
        data = [{"id": i} for i in range(1, 101)]  # 100 items
        handler = SyncListDataHandler(data)
        pagination = PageNumberPagination()
        base_url = "http://example.com/api/items"
        request_params = {
            "page": "2",
            "page_size": "10",
            "filter": "active",
            "category": "tech",
        }

        paginator = SyncPaginator(handler, pagination, base_url, request_params)

        result = paginator.paginate()

        # Check that filters are preserved in links
        next_link = result["pagination"]["links"]["next"]
        assert "filter=active" in next_link
        assert "category=tech" in next_link
        assert "page=3" in next_link

        prev_link = result["pagination"]["links"]["prev"]
        assert "filter=active" in prev_link
        assert "category=tech" in prev_link
        assert "page=1" in prev_link


class TestAsyncPaginator:
    """Test cases for AsyncPaginator"""

    def test_paginate_basic_page_number(self):
        """Test basic async pagination with page number strategy"""
        data = [{"id": i} for i in range(1, 101)]  # 100 items
        handler = AsyncListDataHandler(data)
        pagination = PageNumberPagination(default_page_size=10)
        base_url = "http://example.com/api/items"
        request_params = {"page": "2", "page_size": "10"}

        import asyncio

        async def run_test():
            paginator = AsyncPaginator(handler, pagination, base_url, request_params)
            result = await paginator.paginate()

            assert "items" in result
            assert "pagination" in result
            assert len(result["items"]) == 10
            assert result["items"][0]["id"] == 11  # Second page starts at 11
            assert result["pagination"]["total_items"] == 100
            assert result["pagination"]["page"] == 2
            assert result["pagination"]["total_pages"] == 10

        asyncio.run(run_test())

    def test_paginate_basic_limit_offset(self):
        """Test basic async pagination with limit offset strategy"""
        data = [{"id": i} for i in range(1, 101)]  # 100 items
        handler = AsyncListDataHandler(data)
        pagination = LimitOffsetPagination(default_limit=15)
        base_url = "http://example.com/api/items"
        request_params = {"limit": "15", "offset": "30"}

        import asyncio

        async def run_test():
            paginator = AsyncPaginator(handler, pagination, base_url, request_params)
            result = await paginator.paginate()

            assert "items" in result
            assert "pagination" in result
            assert len(result["items"]) == 15
            assert result["items"][0]["id"] == 31  # Offset 30, first item is 31
            assert result["pagination"]["total_items"] == 100
            assert result["pagination"]["offset"] == 30
            assert result["pagination"]["limit"] == 15

        asyncio.run(run_test())

    def test_paginate_basic_cursor(self):
        """Test basic async pagination with cursor strategy"""
        data = [{"id": i} for i in range(1, 101)]  # 100 items
        handler = AsyncListDataHandler(data)
        pagination = CursorPagination(default_page_size=10)
        base_url = "http://example.com/api/items"
        request_params = {"page_size": "10"}

        import asyncio

        async def run_test():
            paginator = AsyncPaginator(handler, pagination, base_url, request_params)
            result = await paginator.paginate()

            assert "items" in result
            assert "pagination" in result
            assert len(result["items"]) == 10
            assert result["items"][0]["id"] == 1  # First page
            assert result["pagination"]["total_items"] == 100
            assert result["pagination"]["cursor"] is None  # No cursor for first page
            assert "next" in result["pagination"]["links"]
            assert "prev" not in result["pagination"]["links"]

        asyncio.run(run_test())

    def test_paginate_empty_data(self):
        """Test async pagination with empty data"""
        data = []
        handler = AsyncListDataHandler(data)
        pagination = PageNumberPagination()
        base_url = "http://example.com/api/items"
        request_params = {"page": "1", "page_size": "10"}

        import asyncio

        async def run_test():
            paginator = AsyncPaginator(handler, pagination, base_url, request_params)
            result = await paginator.paginate()

            assert result["items"] == []
            assert result["pagination"]["total_items"] == 0
            assert result["pagination"]["total_pages"] == 0

        asyncio.run(run_test())

    def test_paginate_single_item(self):
        """Test async pagination with single item"""
        data = [{"id": 1}]
        handler = AsyncListDataHandler(data)
        pagination = PageNumberPagination()
        base_url = "http://example.com/api/items"
        request_params = {"page": "1", "page_size": "10"}

        import asyncio

        async def run_test():
            paginator = AsyncPaginator(handler, pagination, base_url, request_params)
            result = await paginator.paginate()

            assert len(result["items"]) == 1
            assert result["items"][0]["id"] == 1
            assert result["pagination"]["total_items"] == 1
            assert result["pagination"]["total_pages"] == 1

        asyncio.run(run_test())

    def test_paginate_invalid_offset_exceeds_total(self):
        """Test async pagination when offset exceeds total items"""
        data = [{"id": 1}, {"id": 2}]
        handler = AsyncListDataHandler(data)
        pagination = LimitOffsetPagination()
        base_url = "http://example.com/api/items"
        request_params = {"limit": "10", "offset": "10"}

        import asyncio

        async def run_test():
            paginator = AsyncPaginator(handler, pagination, base_url, request_params)
            with pytest.raises(InvalidPageError):
                await paginator.paginate()

        asyncio.run(run_test())

    def test_paginate_invalid_offset_exceeds_total_with_validation(self):
        """Test async pagination when offset exceeds total items with validation enabled"""
        data = [{"id": 1}, {"id": 2}]
        handler = AsyncListDataHandler(data)
        pagination = LimitOffsetPagination()
        base_url = "http://example.com/api/items"
        request_params = {"limit": "10", "offset": "10"}

        import asyncio

        async def run_test():
            paginator = AsyncPaginator(
                handler, pagination, base_url, request_params, validate_total_items=True
            )

            # Should raise error when validation is enabled and offset exceeds total
            with pytest.raises(
                InvalidPageError, match="Requested offset exceeds total items"
            ):
                await paginator.paginate()

        asyncio.run(run_test())

    def test_paginate_with_cursor_navigation(self):
        """Test async pagination with cursor navigation"""
        data = [{"id": i} for i in range(1, 101)]  # 100 items
        handler = AsyncListDataHandler(data)
        pagination = CursorPagination(default_page_size=10)
        base_url = "http://example.com/api/items"

        import asyncio

        async def run_test():
            # First, get the first page to extract cursor
            first_paginator = AsyncPaginator(
                handler, pagination, base_url, {"page_size": "10"}
            )
            first_result = await first_paginator.paginate()

            # Extract cursor from first page
            next_cursor = (
                first_result["pagination"]["links"]["next"]
                .split("cursor=")[1]
                .split("&")[0]
            )
            print("Next cursor:", next_cursor, first_result)
            # Use cursor for second page
            request_params = {"cursor": next_cursor, "page_size": "10"}
            second_paginator = AsyncPaginator(
                handler, pagination, base_url, request_params
            )
            second_result = await second_paginator.paginate()

            assert len(second_result["items"]) == 10
            assert second_result["items"][0]["id"] == 11  # Second page starts at 11
            assert second_result["pagination"]["cursor"] == next_cursor
            assert "next" in second_result["pagination"]["links"]
            assert "prev" in second_result["pagination"]["links"]

        asyncio.run(run_test())
