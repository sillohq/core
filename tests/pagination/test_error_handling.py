import pytest

from sillo.pagination import (
    AsyncListDataHandler,
    AsyncPaginator,
    CursorPagination,
    InvalidCursorError,
    InvalidPageError,
    InvalidPageSizeError,
    LimitOffsetPagination,
    PageNumberPagination,
    PaginationError,
    SyncListDataHandler,
    SyncPaginator,
)


class TestPaginationErrorHandling:
    """Test cases for pagination error handling"""

    def test_page_number_pagination_invalid_page(self):
        """Test page number pagination with invalid page number"""
        pagination = PageNumberPagination()
        request_params = {"page": "0", "page_size": "10"}

        with pytest.raises(InvalidPageError) as exc_info:
            pagination.parse_parameters(request_params)

        assert "Page number must be at least 1" in str(exc_info.value)

    def test_page_number_pagination_invalid_page_size(self):
        """Test page number pagination with invalid page size"""
        pagination = PageNumberPagination()
        request_params = {"page": "1", "page_size": "0"}

        with pytest.raises(InvalidPageSizeError) as exc_info:
            pagination.parse_parameters(request_params)

        assert "Page size must be at least 1" in str(exc_info.value)

    def test_page_number_pagination_negative_page_size(self):
        """Test page number pagination with negative page size"""
        pagination = PageNumberPagination()
        request_params = {"page": "1", "page_size": "-5"}

        with pytest.raises(InvalidPageSizeError) as exc_info:
            pagination.parse_parameters(request_params)

        assert "Page size must be at least 1" in str(exc_info.value)

    def test_limit_offset_pagination_negative_limit(self):
        """Test limit offset pagination with negative limit"""
        pagination = LimitOffsetPagination()
        request_params = {"limit": "-5", "offset": "0"}

        with pytest.raises(InvalidPageSizeError) as exc_info:
            pagination.parse_parameters(request_params)

        assert "Limit cannot be negative" in str(exc_info.value)

    def test_limit_offset_pagination_negative_offset(self):
        """Test limit offset pagination with negative offset"""
        pagination = LimitOffsetPagination()
        request_params = {"limit": "10", "offset": "-5"}

        with pytest.raises(InvalidPageError) as exc_info:
            pagination.parse_parameters(request_params)

        assert "Offset cannot be negative" in str(exc_info.value)

    def test_cursor_pagination_invalid_json_cursor(self):
        """Test cursor pagination with invalid JSON in cursor"""
        import base64

        # Valid base64 but invalid JSON
        invalid_json = base64.b64encode(b"invalid_json").decode("utf-8")
        pagination = CursorPagination()

        with pytest.raises(InvalidCursorError) as exc_info:
            pagination.decode_cursor(invalid_json)

        assert "Invalid cursor format" in str(exc_info.value)

    def test_sync_paginator_invalid_offset_exceeds_total(self):
        """Test sync paginator with offset exceeding total items and validation enabled"""
        data = [{"id": 1}, {"id": 2}]
        handler = SyncListDataHandler(data)
        pagination = LimitOffsetPagination()
        base_url = "http://example.com/api/items"
        request_params = {"limit": "10", "offset": "10"}

        paginator = SyncPaginator(
            handler, pagination, base_url, request_params, validate_total_items=True
        )

        with pytest.raises(InvalidPageError) as exc_info:
            paginator.paginate()

        assert "Requested offset exceeds total items" in str(exc_info.value)

    def test_async_paginator_invalid_offset_exceeds_total(self):
        """Test async paginator with offset exceeding total items and validation enabled"""
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

            with pytest.raises(InvalidPageError) as exc_info:
                await paginator.paginate()

            assert "Requested offset exceeds total items" in str(exc_info.value)

        asyncio.run(run_test())

    def test_sync_paginator_no_error_when_validation_disabled(self):
        """Test sync paginator doesn't error when validation is disabled"""
        data = [{"id": 1}, {"id": 2}]
        handler = SyncListDataHandler(data)
        pagination = LimitOffsetPagination()
        base_url = "http://example.com/api/items"
        request_params = {"limit": "10", "offset": "10"}

        paginator = SyncPaginator(
            handler, pagination, base_url, request_params, validate_total_items=False
        )

        # Should not raise error when validation is disabled
        result = paginator.paginate()
        assert result["items"] == []
        assert result["pagination"]["total_items"] == 2

    def test_async_paginator_no_error_when_validation_disabled(self):
        """Test async paginator doesn't error when validation is disabled"""
        data = [{"id": 1}, {"id": 2}]
        handler = AsyncListDataHandler(data)
        pagination = LimitOffsetPagination()
        base_url = "http://example.com/api/items"
        request_params = {"limit": "10", "offset": "10"}

        import asyncio

        async def run_test():
            paginator = AsyncPaginator(
                handler,
                pagination,
                base_url,
                request_params,
                validate_total_items=False,
            )

            # Should not raise error when validation is disabled
            result = await paginator.paginate()
            assert result["items"] == []
            assert result["pagination"]["total_items"] == 2

        asyncio.run(run_test())

    def test_pagination_error_hierarchy(self):
        """Test that pagination errors inherit from base PaginationError"""
        # Test InvalidPageError
        with pytest.raises(PaginationError):
            raise InvalidPageError("test")

        # Test InvalidPageSizeError
        with pytest.raises(PaginationError):
            raise InvalidPageSizeError("test")

        # Test InvalidCursorError
        with pytest.raises(PaginationError):
            raise InvalidCursorError("test")

    def test_error_messages_are_preserved(self):
        """Test that custom error messages are preserved"""
        custom_message = "Custom error message"

        with pytest.raises(InvalidPageError) as exc_info:
            raise InvalidPageError(custom_message)

        assert str(exc_info.value) == custom_message


class TestEdgeCaseErrors:
    """Test cases for edge case error conditions"""

    def test_page_number_pagination_very_large_page(self):
        """Test page number pagination with very large page number"""
        pagination = PageNumberPagination()
        request_params = {"page": "999999", "page_size": "10"}

        # Should not raise error for large but valid page numbers
        page, page_size = pagination.parse_parameters(request_params)
        assert page == 999999
        assert page_size == 10

    def test_limit_offset_pagination_very_large_offset(self):
        """Test limit offset pagination with very large offset"""
        pagination = LimitOffsetPagination()
        request_params = {"limit": "10", "offset": "999999"}

        # Should not raise error for large but valid offsets
        limit, offset = pagination.parse_parameters(request_params)
        assert limit == 10
        assert offset == 999999

    def test_cursor_pagination_empty_cursor(self):
        """Test cursor pagination with empty cursor string"""
        pagination = CursorPagination()
        request_params = {"cursor": "", "page_size": "10"}

        # Empty cursor should be treated as None (first page)
        cursor, page_size = pagination.parse_parameters(request_params)
        assert cursor == ""
        assert page_size == 10

    def test_cursor_pagination_whitespace_cursor(self):
        """Test cursor pagination with whitespace-only cursor"""
        pagination = CursorPagination()
        request_params = {"cursor": "   ", "page_size": "10"}

        cursor, page_size = pagination.parse_parameters(request_params)
        assert cursor == "   "
        assert page_size == 10


class TestErrorPropagation:
    """Test cases for error propagation through pagination layers"""

    def test_error_in_strategy_propagates_to_paginator(self):
        """Test that errors in strategy are properly propagated to paginator"""
        data = [{"id": 1}]
        handler = SyncListDataHandler(data)

        # Create a strategy that will raise an error
        class ErrorStrategy(PageNumberPagination):
            def parse_parameters(self, request_params):
                raise InvalidPageSizeError("Custom strategy error")

        pagination = ErrorStrategy()
        base_url = "http://example.com/api/items"
        request_params = {"page": "1", "page_size": "10"}

        paginator = SyncPaginator(handler, pagination, base_url, request_params)

        with pytest.raises(InvalidPageSizeError) as exc_info:
            paginator.paginate()

        assert "Custom strategy error" in str(exc_info.value)

    def test_error_in_handler_propagates_to_paginator(self):
        """Test that errors in data handler are properly propagated"""

        class ErrorHandler(SyncListDataHandler):
            def get_total_items(self):
                raise RuntimeError("Database connection failed")

        data = []
        handler = ErrorHandler(data)
        pagination = PageNumberPagination()
        base_url = "http://example.com/api/items"
        request_params = {"page": "1", "page_size": "10"}

        paginator = SyncPaginator(handler, pagination, base_url, request_params)

        # Handler errors should propagate up
        with pytest.raises(RuntimeError) as exc_info:
            paginator.paginate()

        assert "Database connection failed" in str(exc_info.value)

    def test_async_error_propagation(self):
        """Test error propagation in async context"""

        class ErrorAsyncHandler(AsyncListDataHandler):
            async def get_total_items(self):
                raise RuntimeError("Async database connection failed")

        data = []
        handler = ErrorAsyncHandler(data)
        pagination = PageNumberPagination()
        base_url = "http://example.com/api/items"
        request_params = {"page": "1", "page_size": "10"}

        import asyncio

        async def run_test():
            paginator = AsyncPaginator(handler, pagination, base_url, request_params)

            # Handler errors should propagate up
            with pytest.raises(RuntimeError) as exc_info:
                await paginator.paginate()

            assert "Async database connection failed" in str(exc_info.value)

        asyncio.run(run_test())
