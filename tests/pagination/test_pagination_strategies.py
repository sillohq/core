import base64
import json
import urllib.parse
from typing import Any, Dict

import pytest

from sillo.pagination import (
    CursorPagination,
    InvalidCursorError,
    InvalidPageError,
    InvalidPageSizeError,
    LimitOffsetPagination,
    LinkBuilder,
    PageNumberPagination,
    PaginationError,
)


class TestLinkBuilder:
    """Test cases for LinkBuilder utility class"""

    def test_build_link_with_pagination_params(self):
        """Test building links with pagination parameters filtered out"""
        base_url = "http://example.com/api/items"
        request_params = {
            "page": "2",
            "page_size": "10",
            "filter": "active",
            "sort": "name",
        }
        pagination_params = ["page", "page_size"]

        link_builder = LinkBuilder(base_url, request_params, pagination_params)

        # Should include non-pagination params and new params
        result = link_builder.build_link({"page": 3, "page_size": 20})
        expected = (
            "http://example.com/api/items?filter=active&sort=name&page=3&page_size=20"
        )
        assert result == expected

    def test_build_link_with_no_pagination_params(self):
        """Test building links when no pagination params exist"""
        base_url = "http://example.com/api/items"
        request_params = {"filter": "active", "sort": "name"}
        pagination_params = ["page", "page_size"]

        link_builder = LinkBuilder(base_url, request_params, pagination_params)

        result = link_builder.build_link({"page": 1})
        expected = "http://example.com/api/items?filter=active&sort=name&page=1"
        assert result == expected

    def test_build_link_with_list_params(self):
        """Test building links with list-type parameters"""
        base_url = "http://example.com/api/items"
        request_params = {"tags": ["python", "web"], "category": "tech"}
        pagination_params = ["tags"]

        link_builder = LinkBuilder(base_url, request_params, pagination_params)

        result = link_builder.build_link({"tags": ["python", "api"], "page": 1})
        expected = (
            "http://example.com/api/items?category=tech&tags=python&tags=api&page=1"
        )
        assert result == expected


class TestPageNumberPagination:
    """Test cases for PageNumberPagination strategy"""

    def test_parse_parameters_defaults(self):
        """Test parsing parameters with default values"""
        pagination = PageNumberPagination()
        params = {}

        page, page_size = pagination.parse_parameters(params)

        assert page == 1
        assert page_size == 20

    def test_parse_parameters_custom_values(self):
        """Test parsing parameters with custom values"""
        pagination = PageNumberPagination()
        params = {"page": "3", "page_size": "50"}

        page, page_size = pagination.parse_parameters(params)

        assert page == 3
        assert page_size == 50

    def test_parse_parameters_max_page_size_enforced(self):
        """Test that max page size is enforced"""
        pagination = PageNumberPagination(max_page_size=100)
        params = {"page": "1", "page_size": "200"}

        page, page_size = pagination.parse_parameters(params)

        assert page == 1
        assert page_size == 100  # Should be capped at max

    def test_parse_parameters_invalid_page(self):
        """Test parsing parameters with invalid page number"""
        pagination = PageNumberPagination()
        params = {"page": "0"}

        with pytest.raises(InvalidPageError, match="Page number must be at least 1"):
            pagination.parse_parameters(params)

    def test_parse_parameters_invalid_page_size(self):
        """Test parsing parameters with invalid page size"""
        pagination = PageNumberPagination()
        params = {"page": "1", "page_size": "0"}

        with pytest.raises(InvalidPageSizeError, match="Page size must be at least 1"):
            pagination.parse_parameters(params)

    def test_parse_parameters_negative_page_size(self):
        """Test parsing parameters with negative page size"""
        pagination = PageNumberPagination()
        params = {"page": "1", "page_size": "-5"}

        with pytest.raises(InvalidPageSizeError, match="Page size must be at least 1"):
            pagination.parse_parameters(params)

    def test_calculate_offset_limit(self):
        """Test offset and limit calculation"""
        pagination = PageNumberPagination()

        offset, limit = pagination.calculate_offset_limit(3, 10)

        assert offset == 20  # (3-1) * 10
        assert limit == 10

    def test_generate_metadata_first_page(self):
        """Test metadata generation for first page"""
        pagination = PageNumberPagination()
        total_items = 100
        items = [{"id": 1}, {"id": 2}]  # Mock items
        base_url = "http://example.com/api/items"
        request_params = {"page": "1", "page_size": "10"}

        metadata = pagination.generate_metadata(
            total_items, items, base_url, request_params
        )

        assert metadata["total_items"] == 100
        assert metadata["total_pages"] == 10
        assert metadata["page"] == 1
        assert metadata["page_size"] == 10
        assert "next" in metadata["links"]
        assert "prev" not in metadata["links"]  # No prev on first page
        assert "first" in metadata["links"]
        assert "last" in metadata["links"]

    def test_generate_metadata_middle_page(self):
        """Test metadata generation for middle page"""
        pagination = PageNumberPagination()
        total_items = 100
        items = [{"id": 21}, {"id": 22}]  # Mock items for page 3
        base_url = "http://example.com/api/items"
        request_params = {"page": "3", "page_size": "10"}

        metadata = pagination.generate_metadata(
            total_items, items, base_url, request_params
        )

        assert metadata["total_items"] == 100
        assert metadata["total_pages"] == 10
        assert metadata["page"] == 3
        assert metadata["page_size"] == 10
        assert "next" in metadata["links"]
        assert "prev" in metadata["links"]
        assert "first" in metadata["links"]
        assert "last" in metadata["links"]

    def test_generate_metadata_last_page(self):
        """Test metadata generation for last page"""
        pagination = PageNumberPagination()
        total_items = 100
        items = [{"id": 91}, {"id": 92}]  # Mock items for page 10
        base_url = "http://example.com/api/items"
        request_params = {"page": "10", "page_size": "10"}

        metadata = pagination.generate_metadata(
            total_items, items, base_url, request_params
        )

        assert metadata["total_items"] == 100
        assert metadata["total_pages"] == 10
        assert metadata["page"] == 10
        assert metadata["page_size"] == 10
        assert "prev" in metadata["links"]
        assert "first" in metadata["links"]
        assert "last" in metadata["links"]

    def test_generate_metadata_with_filters(self):
        """Test metadata generation with additional query parameters"""
        pagination = PageNumberPagination()
        total_items = 100
        items = [{"id": 1}]
        base_url = "http://example.com/api/items"
        request_params = {
            "page": "1",
            "page_size": "10",
            "filter": "active",
            "category": "tech",
        }

        metadata = pagination.generate_metadata(
            total_items, items, base_url, request_params
        )

        # Check that non-pagination params are preserved in links
        next_link = metadata["links"]["next"]
        assert "filter=active" in next_link
        assert "category=tech" in next_link
        assert "page=2" in next_link

    def test_generate_metadata_zero_total_items(self):
        """Test metadata generation with zero total items"""
        pagination = PageNumberPagination()
        total_items = 0
        items = []
        base_url = "http://example.com/api/items"
        request_params = {"page": "1", "page_size": "10"}

        metadata = pagination.generate_metadata(
            total_items, items, base_url, request_params
        )

        assert metadata["total_items"] == 0
        assert metadata["total_pages"] == 0
        assert metadata["page"] == 1
        assert metadata["page_size"] == 10
        assert "next" not in metadata["links"]
        assert "prev" not in metadata["links"]
        assert "first" in metadata["links"]
        assert "last" in metadata["links"]


class TestLimitOffsetPagination:
    """Test cases for LimitOffsetPagination strategy"""

    def test_parse_parameters_defaults(self):
        """Test parsing parameters with default values"""
        pagination = LimitOffsetPagination()
        params = {}

        limit, offset = pagination.parse_parameters(params)

        assert limit == 20
        assert offset == 0

    def test_parse_parameters_custom_values(self):
        """Test parsing parameters with custom values"""
        pagination = LimitOffsetPagination()
        params = {"limit": "50", "offset": "30"}

        limit, offset = pagination.parse_parameters(params)

        assert limit == 50
        assert offset == 30

    def test_parse_parameters_max_limit_enforced(self):
        """Test that max limit is enforced"""
        pagination = LimitOffsetPagination(max_limit=100)
        params = {"limit": "200", "offset": "0"}

        limit, offset = pagination.parse_parameters(params)

        assert limit == 100  # Should be capped at max
        assert offset == 0

    def test_parse_parameters_negative_limit(self):
        """Test parsing parameters with negative limit"""
        pagination = LimitOffsetPagination()
        params = {"limit": "-5", "offset": "0"}

        with pytest.raises(InvalidPageSizeError, match="Limit cannot be negative"):
            pagination.parse_parameters(params)

    def test_parse_parameters_negative_offset(self):
        """Test parsing parameters with negative offset"""
        pagination = LimitOffsetPagination()
        params = {"limit": "10", "offset": "-5"}

        with pytest.raises(InvalidPageError, match="Offset cannot be negative"):
            pagination.parse_parameters(params)

    def test_calculate_offset_limit(self):
        """Test offset and limit calculation"""
        pagination = LimitOffsetPagination()

        offset, limit = pagination.calculate_offset_limit(10, 30)

        assert offset == 30
        assert limit == 10

    def test_generate_metadata_first_page(self):
        """Test metadata generation for first page (offset 0)"""
        pagination = LimitOffsetPagination()
        total_items = 100
        items = [{"id": 1}, {"id": 2}]  # Mock items
        base_url = "http://example.com/api/items"
        request_params = {"limit": "10", "offset": "0"}

        metadata = pagination.generate_metadata(
            total_items, items, base_url, request_params
        )

        assert metadata["total_items"] == 100
        assert metadata["limit"] == 10
        assert metadata["offset"] == 0
        assert metadata["current_page"] == 1
        assert metadata["total_pages"] == 10
        assert "next" in metadata["links"]
        assert "prev" not in metadata["links"]  # No prev on first page
        assert "first" in metadata["links"]
        assert "last" in metadata["links"]

    def test_generate_metadata_middle_page(self):
        """Test metadata generation for middle page"""
        pagination = LimitOffsetPagination()
        total_items = 100
        items = [{"id": 31}, {"id": 32}]  # Mock items for offset 30
        base_url = "http://example.com/api/items"
        request_params = {"limit": "10", "offset": "30"}

        metadata = pagination.generate_metadata(
            total_items, items, base_url, request_params
        )

        assert metadata["total_items"] == 100
        assert metadata["limit"] == 10
        assert metadata["offset"] == 30
        assert metadata["current_page"] == 4  # (30 // 10) + 1
        assert metadata["total_pages"] == 10
        assert "next" in metadata["links"]
        assert "prev" in metadata["links"]
        assert "first" in metadata["links"]
        assert "last" in metadata["links"]

    def test_generate_metadata_last_page(self):
        """Test metadata generation for last page"""
        pagination = LimitOffsetPagination()
        total_items = 100
        items = [{"id": 91}, {"id": 92}]  # Mock items for offset 90
        base_url = "http://example.com/api/items"
        request_params = {"limit": "10", "offset": "90"}

        metadata = pagination.generate_metadata(
            total_items, items, base_url, request_params
        )

        assert metadata["total_items"] == 100
        assert metadata["limit"] == 10
        assert metadata["offset"] == 90
        assert metadata["current_page"] == 10
        assert metadata["total_pages"] == 10
        assert "prev" in metadata["links"]
        assert "first" in metadata["links"]
        assert "last" in metadata["links"]

    def test_generate_metadata_excessive_offset(self):
        """Test metadata generation with offset beyond total items"""
        pagination = LimitOffsetPagination()
        total_items = 100
        items = []  # No items returned
        base_url = "http://example.com/api/items"
        request_params = {"limit": "10", "offset": "150"}

        metadata = pagination.generate_metadata(
            total_items, items, base_url, request_params
        )

        assert metadata["total_items"] == 100
        assert metadata["limit"] == 10
        assert metadata["offset"] == 150
        assert metadata["current_page"] == 16  # (150 // 10) + 1
        assert metadata["total_pages"] == 10
        assert "next" not in metadata["links"]  # No next when beyond total
        assert "prev" in metadata["links"]
        assert "first" in metadata["links"]
        assert "last" in metadata["links"]


class TestCursorPagination:
    """Test cases for CursorPagination strategy"""

    def test_parse_parameters_defaults(self):
        """Test parsing parameters with default values"""
        pagination = CursorPagination()
        params = {}

        cursor, page_size = pagination.parse_parameters(params)

        assert cursor is None
        assert page_size == 20

    def test_parse_parameters_with_cursor(self):
        """Test parsing parameters with cursor"""
        pagination = CursorPagination()
        params = {
            "cursor": "eyJpZCI6MTB9",
            "page_size": "50",
        }  # base64 encoded {"id": 10}

        cursor, page_size = pagination.parse_parameters(params)

        assert cursor == "eyJpZCI6MTB9"
        assert page_size == 50

    def test_parse_parameters_max_page_size_enforced(self):
        """Test that max page size is enforced"""
        pagination = CursorPagination(max_page_size=100)
        params = {"cursor": "eyJpZCI6MTB9", "page_size": "200"}

        cursor, page_size = pagination.parse_parameters(params)

        assert cursor == "eyJpZCI6MTB9"
        assert page_size == 100  # Should be capped at max

    def test_encode_cursor(self):
        """Test cursor encoding"""
        pagination = CursorPagination()

        cursor = pagination.encode_cursor(42)

        # Should be base64 encoded JSON
        decoded = base64.b64decode(cursor).decode("utf-8")
        cursor_data = json.loads(decoded)
        assert cursor_data == {"id": 42}

    def test_encode_cursor_with_custom_field(self):
        """Test cursor encoding with custom sort field"""
        pagination = CursorPagination(sort_field="created_at")

        cursor = pagination.encode_cursor("2023-01-01T00:00:00Z")

        decoded = base64.b64decode(cursor).decode("utf-8")
        cursor_data = json.loads(decoded)
        assert cursor_data == {"created_at": "2023-01-01T00:00:00Z"}

    def test_decode_cursor_valid(self):
        """Test cursor decoding with valid cursor"""
        pagination = CursorPagination()

        # Create a valid cursor
        original_data = {"id": 42}
        encoded_cursor = base64.b64encode(
            json.dumps(original_data).encode("utf-8")
        ).decode("utf-8")

        decoded = pagination.decode_cursor(encoded_cursor)

        assert decoded == {"id": 42}

    def test_decode_cursor_invalid_json(self):
        """Test cursor decoding with invalid JSON"""
        pagination = CursorPagination()

        # Valid base64 but invalid JSON
        invalid_json = base64.b64encode(b"invalid_json").decode("utf-8")

        with pytest.raises(InvalidCursorError, match="Invalid cursor format"):
            pagination.decode_cursor(invalid_json)

    def test_generate_metadata_first_page(self):
        """Test metadata generation for first page (no cursor)"""
        pagination = CursorPagination()
        total_items = 100
        items = [{"id": 1}, {"id": 2}]  # Mock items
        base_url = "http://example.com/api/items"
        request_params = {"page_size": "10"}

        metadata = pagination.generate_metadata(
            total_items, items, base_url, request_params
        )

        assert metadata["total_items"] == 100
        assert metadata["page_size"] == 10
        assert metadata["cursor"] is None
        assert "next" in metadata["links"]
        assert "prev" not in metadata["links"]  # No prev on first page

    def test_generate_metadata_with_cursor(self):
        """Test metadata generation with cursor"""
        pagination = CursorPagination()
        total_items = 100
        items = [{"id": 21}, {"id": 22}]  # Mock items
        base_url = "http://example.com/api/items"
        request_params = {"cursor": "eyJpZCI6MjB9", "page_size": "10"}

        metadata = pagination.generate_metadata(
            total_items, items, base_url, request_params
        )

        assert metadata["total_items"] == 100
        assert metadata["page_size"] == 10
        assert metadata["cursor"] == "eyJpZCI6MjB9"
        assert "next" in metadata["links"]
        assert "prev" in metadata["links"]

    def test_generate_metadata_last_page(self):
        """Test metadata generation for last page (no next cursor)"""
        pagination = CursorPagination()
        total_items = 100
        items = [{"id": 91}]  # Only one item, indicating last page
        base_url = "http://example.com/api/items"
        request_params = {"cursor": "eyJpZCI6OTB9", "page_size": "10"}

        metadata = pagination.generate_metadata(
            total_items, items, base_url, request_params
        )

        assert metadata["total_items"] == 100
        assert metadata["page_size"] == 10
        assert metadata["cursor"] == "eyJpZCI6OTB9"
        assert "prev" in metadata["links"]

    def test_generate_metadata_empty_items(self):
        """Test metadata generation with empty items"""
        pagination = CursorPagination()
        total_items = 100
        items = []
        base_url = "http://example.com/api/items"
        request_params = {"cursor": "eyJpZCI6MTB9", "page_size": "10"}

        metadata = pagination.generate_metadata(
            total_items, items, base_url, request_params
        )

        assert metadata["total_items"] == 100
        assert metadata["page_size"] == 10
        assert metadata["cursor"] == "eyJpZCI6MTB9"
        assert "next" not in metadata["links"]  # No next when no items
        assert "prev" in metadata["links"]
