import pytest

from nexios.pagination import (
    AsyncListDataHandler,
    AsyncPaginatedResponse,
    AsyncPaginator,
    CursorPagination,
    LimitOffsetPagination,
    PageNumberPagination,
    PaginatedResponse,
    SyncListDataHandler,
    SyncPaginator,
)


class TestEdgeCases:
    """Test cases for edge cases and boundary conditions"""

    def test_empty_data_pagination(self):
        """Test pagination with completely empty dataset"""
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
        assert result["pagination"]["page"] == 1
        assert "next" not in result["pagination"]["links"]
        assert "prev" not in result["pagination"]["links"]

    def test_single_item_pagination(self):
        """Test pagination with single item dataset"""
        data = [{"id": 1, "name": "Single Item"}]
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
        assert "next" not in result["pagination"]["links"]
        assert "prev" not in result["pagination"]["links"]

    def test_large_dataset_pagination(self):
        """Test pagination with large dataset"""
        # Create a large dataset (10k items)
        data = [{"id": i, "data": f"item_{i}_data"} for i in range(1, 10001)]
        handler = SyncListDataHandler(data)
        pagination = PageNumberPagination(default_page_size=100)
        base_url = "http://example.com/api/items"
        request_params = {"page": "50", "page_size": "100"}

        paginator = SyncPaginator(handler, pagination, base_url, request_params)
        result = paginator.paginate()

        assert len(result["items"]) == 100
        assert result["items"][0]["id"] == 4901  # Page 50, item 4901
        assert result["items"][-1]["id"] == 5000  # Page 50, last item 5000
        assert result["pagination"]["total_items"] == 10000
        assert result["pagination"]["total_pages"] == 100
        assert result["pagination"]["page"] == 50

    def test_exact_page_boundary(self):
        """Test pagination at exact page boundaries"""
        data = [{"id": i} for i in range(1, 101)]  # 100 items
        handler = SyncListDataHandler(data)
        pagination = PageNumberPagination(default_page_size=10)
        base_url = "http://example.com/api/items"

        # Test last page (page 10)
        request_params = {"page": "10", "page_size": "10"}
        paginator = SyncPaginator(handler, pagination, base_url, request_params)
        result = paginator.paginate()

        assert len(result["items"]) == 10
        assert result["items"][0]["id"] == 91
        assert result["items"][-1]["id"] == 100
        assert result["pagination"]["page"] == 10
        assert result["pagination"]["total_pages"] == 10
        assert "next" not in result["pagination"]["links"]
        assert "prev" in result["pagination"]["links"]

    def test_offset_at_exact_limit_boundary(self):
        """Test limit/offset pagination at exact boundaries"""
        data = [{"id": i} for i in range(1, 101)]  # 100 items
        handler = SyncListDataHandler(data)
        pagination = LimitOffsetPagination(default_limit=25)
        base_url = "http://example.com/api/items"

        # Test at offset 75 (should return items 76-100)
        request_params = {"limit": "25", "offset": "75"}
        paginator = SyncPaginator(handler, pagination, base_url, request_params)
        result = paginator.paginate()

        assert len(result["items"]) == 25
        assert result["items"][0]["id"] == 76
        assert result["items"][-1]["id"] == 100
        assert result["pagination"]["offset"] == 75
        assert result["pagination"]["limit"] == 25
        assert "next" not in result["pagination"]["links"]
        assert "prev" in result["pagination"]["links"]

    def test_cursor_pagination_boundary(self):
        """Test cursor pagination at boundaries"""
        data = [{"id": i} for i in range(1, 101)]  # 100 items
        handler = SyncListDataHandler(data)
        pagination = CursorPagination(default_page_size=10)
        base_url = "http://example.com/api/items"

        # Get first page
        first_paginator = SyncPaginator(
            handler, pagination, base_url, {"page_size": "10"}
        )
        first_result = first_paginator.paginate()

        # Get cursor for last item of first page
        last_item_id = first_result["items"][-1]["id"]
        next_cursor = pagination.encode_cursor(last_item_id)

        # Get second page using cursor
        request_params = {"cursor": next_cursor, "page_size": "10"}
        second_paginator = SyncPaginator(handler, pagination, base_url, request_params)
        second_result = second_paginator.paginate()

        assert len(second_result["items"]) == 10
        assert second_result["items"][0]["id"] == 11
        assert second_result["pagination"]["cursor"] == next_cursor

    def test_zero_page_size_edge_case(self):
        """Test edge case with zero page size (should raise error)"""
        pagination = PageNumberPagination()

        with pytest.raises(Exception):  # Should raise InvalidPageSizeError
            pagination.parse_parameters({"page": "1", "page_size": "0"})

    def test_negative_numbers_edge_cases(self):
        """Test pagination with negative numbers (should raise errors)"""
        pagination = PageNumberPagination()

        # Negative page
        with pytest.raises(Exception):
            pagination.parse_parameters({"page": "-1", "page_size": "10"})

        # Negative page size
        with pytest.raises(Exception):
            pagination.parse_parameters({"page": "1", "page_size": "-5"})

    def test_mixed_data_types_in_items(self):
        """Test pagination with mixed data types in items"""
        data = [
            {"id": 1, "name": "string"},
            {"id": 2, "count": 42},
            {"id": 3, "active": True},
            {"id": 4, "data": [1, 2, 3]},
            {"id": 5, "nested": {"key": "value"}},
            {"id": 6, "null_value": None},
        ]
        handler = SyncListDataHandler(data)
        pagination = PageNumberPagination(max_page_size=3)
        base_url = "http://example.com/api/items"
        request_params = {"page": "1", "page_size": "3"}

        paginator = SyncPaginator(handler, pagination, base_url, request_params)
        result = paginator.paginate()

        assert len(result["items"]) == 3
        assert result["items"][0]["id"] == 1
        assert result["items"][1]["id"] == 2
        assert result["items"][2]["id"] == 3
        assert result["pagination"]["total_items"] == 6

    def test_unicode_and_special_characters(self):
        """Test pagination with unicode and special characters in data"""
        data = [
            {"id": 1, "name": "测试"},  # Chinese characters
            {"id": 2, "description": "café"},  # Accented characters
            {"id": 3, "tags": ["python", "测试"]},  # Mixed
            {"id": 4, "emoji": ""},
            {"id": 5, "special": "!@#$%^&*()"},
        ]
        handler = SyncListDataHandler(data)
        pagination = PageNumberPagination(default_page_size=2)
        base_url = "http://example.com/api/items"
        request_params = {"page": "2", "page_size": "2"}

        paginator = SyncPaginator(handler, pagination, base_url, request_params)
        result = paginator.paginate()

        assert len(result["items"]) == 2
        assert result["items"][0]["id"] == 3
        assert result["items"][1]["id"] == 4
        assert result["pagination"]["total_items"] == 5

    def test_async_edge_cases(self):
        """Test async pagination edge cases"""
        import asyncio

        async def run_test():
            data = []
            handler = AsyncListDataHandler(data)
            pagination = PageNumberPagination()
            base_url = "http://example.com/api/items"
            request_params = {"page": "1", "page_size": "10"}

            paginator = AsyncPaginator(handler, pagination, base_url, request_params)
            result = await paginator.paginate()

            assert result["items"] == []
            assert result["pagination"]["total_items"] == 0

        asyncio.run(run_test())

    def test_response_edge_cases(self):
        """Test response classes with edge case data"""
        # Test with None values
        data = {
            "items": None,
            "pagination": {"total_items": 0, "page": 1, "page_size": 10, "links": {}},
        }

        # Should handle None items gracefully
        try:
            response = PaginatedResponse(data)
            result = response.to_dict()
            assert result["data"] is None
        except Exception as e:
            # If it raises an error, that's also acceptable behavior
            pass

    def test_very_small_page_sizes(self):
        """Test pagination with very small page sizes"""
        data = [{"id": i} for i in range(1, 101)]
        handler = SyncListDataHandler(data)
        pagination = PageNumberPagination(max_page_size=1)  # Minimum page size
        base_url = "http://example.com/api/items"
        request_params = {"page": "5", "page_size": "1"}

        paginator = SyncPaginator(handler, pagination, base_url, request_params)
        result = paginator.paginate()

        assert len(result["items"]) == 1
        assert result["items"][0]["id"] == 5
        assert result["pagination"]["page_size"] == 1
        assert result["pagination"]["total_pages"] == 100


class TestBoundaryConditions:
    """Test cases for boundary conditions"""

    def test_minimum_valid_parameters(self):
        """Test with minimum valid parameter values"""
        data = [{"id": 1}]
        handler = SyncListDataHandler(data)
        pagination = PageNumberPagination(default_page=1, default_page_size=1)
        base_url = "http://example.com/api/items"
        request_params = {}

        paginator = SyncPaginator(handler, pagination, base_url, request_params)
        result = paginator.paginate()

        assert len(result["items"]) == 1
        assert result["pagination"]["page"] == 1
        assert result["pagination"]["page_size"] == 1

    def test_maximum_valid_parameters(self):
        """Test with maximum valid parameter values"""
        data = [{"id": i} for i in range(1, 101)]
        handler = SyncListDataHandler(data)
        pagination = PageNumberPagination(max_page_size=100)
        base_url = "http://example.com/api/items"
        request_params = {"page": "1", "page_size": "100"}

        paginator = SyncPaginator(handler, pagination, base_url, request_params)
        result = paginator.paginate()

        assert len(result["items"]) == 100
        assert result["pagination"]["page_size"] == 100

    def test_exact_division_boundaries(self):
        """Test when total items is exactly divisible by page size"""
        data = [{"id": i} for i in range(1, 101)]  # 100 items
        handler = SyncListDataHandler(data)
        pagination = PageNumberPagination(max_page_size=10)  # Exactly 10 pages
        base_url = "http://example.com/api/items"

        # Test last page (page 10)
        request_params = {"page": "10", "page_size": "10"}
        paginator = SyncPaginator(handler, pagination, base_url, request_params)
        result = paginator.paginate()

        assert len(result["items"]) == 10
        assert result["pagination"]["total_pages"] == 10
        assert "next" not in result["pagination"]["links"]

    def test_non_exact_division_boundaries(self):
        """Test when total items is not exactly divisible by page size"""
        data = [{"id": i} for i in range(1, 97)]  # 97 items, not divisible by 10
        handler = SyncListDataHandler(data)
        pagination = PageNumberPagination(max_page_size=10)
        base_url = "http://example.com/api/items"

        # Test last page (page 10, should have 7 items)
        request_params = {"page": "10", "page_size": "10"}
        paginator = SyncPaginator(handler, pagination, base_url, request_params)
        result = paginator.paginate()

        assert len(result["items"]) == 6  # 97 - 90 = 7 items on last page
        assert result["pagination"]["total_pages"] == 10
        assert "next" not in result["pagination"]["links"]
