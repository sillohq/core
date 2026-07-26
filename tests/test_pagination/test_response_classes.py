import pytest

from sillo.pagination import AsyncPaginatedResponse, PaginatedResponse


class TestPaginatedResponse:
    """Test cases for PaginatedResponse"""

    def test_to_dict_basic(self):
        """Test basic to_dict conversion"""
        data = {
            "items": [{"id": 1}, {"id": 2}],
            "pagination": {
                "total_items": 100,
                "page": 1,
                "page_size": 10,
                "links": {"next": "http://example.com?page=2"},
            },
        }

        response = PaginatedResponse(data)
        result = response.to_dict()

        expected = {
            "data": [{"id": 1}, {"id": 2}],
            "pagination": {
                "total_items": 100,
                "page": 1,
                "page_size": 10,
                "links": {"next": "http://example.com?page=2"},
            },
        }

        assert result == expected

    def test_to_dict_empty_items(self):
        """Test to_dict conversion with empty items"""
        data = {
            "items": [],
            "pagination": {"total_items": 0, "page": 1, "page_size": 10, "links": {}},
        }

        response = PaginatedResponse(data)
        result = response.to_dict()

        expected = {
            "data": [],
            "pagination": {"total_items": 0, "page": 1, "page_size": 10, "links": {}},
        }

        assert result == expected

    def test_to_dict_complex_pagination(self):
        """Test to_dict conversion with complex pagination metadata"""
        data = {
            "items": [{"id": i} for i in range(1, 11)],
            "pagination": {
                "total_items": 1000,
                "total_pages": 100,
                "page": 5,
                "page_size": 10,
                "links": {
                    "first": "http://example.com?page=1",
                    "prev": "http://example.com?page=4",
                    "next": "http://example.com?page=6",
                    "last": "http://example.com?page=100",
                },
            },
        }

        response = PaginatedResponse(data)
        result = response.to_dict()

        expected = {
            "data": [{"id": i} for i in range(1, 11)],
            "pagination": {
                "total_items": 1000,
                "total_pages": 100,
                "page": 5,
                "page_size": 10,
                "links": {
                    "first": "http://example.com?page=1",
                    "prev": "http://example.com?page=4",
                    "next": "http://example.com?page=6",
                    "last": "http://example.com?page=100",
                },
            },
        }

        assert result == expected

    def test_items_property(self):
        """Test items property access"""
        data = {"items": [{"id": 1}, {"id": 2}], "pagination": {"total_items": 100}}

        response = PaginatedResponse(data)

        assert response.items == [{"id": 1}, {"id": 2}]

    def test_metadata_property(self):
        """Test metadata property access"""
        data = {"items": [{"id": 1}], "pagination": {"total_items": 100, "page": 1}}

        response = PaginatedResponse(data)

        assert response.metadata == {"total_items": 100, "page": 1}

    def test_large_dataset(self):
        """Test with large dataset"""
        # Create a large dataset
        items = [{"id": i, "data": f"item_{i}_data"} for i in range(1000)]
        data = {
            "items": items,
            "pagination": {
                "total_items": 50000,
                "page": 1,
                "page_size": 1000,
                "links": {"next": "http://example.com?page=2"},
            },
        }

        response = PaginatedResponse(data)
        result = response.to_dict()

        assert len(result["data"]) == 1000
        assert result["pagination"]["total_items"] == 50000


class TestAsyncPaginatedResponse:
    """Test cases for AsyncPaginatedResponse"""

    def test_to_dict_basic(self):
        """Test basic async to_dict conversion"""
        data = {
            "items": [{"id": 1}, {"id": 2}],
            "pagination": {
                "total_items": 100,
                "page": 1,
                "page_size": 10,
                "links": {"next": "http://example.com?page=2"},
            },
        }

        response = AsyncPaginatedResponse(data)
        result = response.to_dict()

        expected = {
            "data": [{"id": 1}, {"id": 2}],
            "pagination": {
                "total_items": 100,
                "page": 1,
                "page_size": 10,
                "links": {"next": "http://example.com?page=2"},
            },
        }

        assert result == expected

    def test_to_dict_empty_items(self):
        """Test async to_dict conversion with empty items"""
        data = {
            "items": [],
            "pagination": {"total_items": 0, "page": 1, "page_size": 10, "links": {}},
        }

        response = AsyncPaginatedResponse(data)
        result = response.to_dict()

        expected = {
            "data": [],
            "pagination": {"total_items": 0, "page": 1, "page_size": 10, "links": {}},
        }

        assert result == expected

    def test_to_dict_complex_pagination(self):
        """Test async to_dict conversion with complex pagination metadata"""
        data = {
            "items": [{"id": i} for i in range(1, 11)],
            "pagination": {
                "total_items": 1000,
                "total_pages": 100,
                "page": 5,
                "page_size": 10,
                "links": {
                    "first": "http://example.com?page=1",
                    "prev": "http://example.com?page=4",
                    "next": "http://example.com?page=6",
                    "last": "http://example.com?page=100",
                },
            },
        }

        response = AsyncPaginatedResponse(data)
        result = response.to_dict()

        expected = {
            "data": [{"id": i} for i in range(1, 11)],
            "pagination": {
                "total_items": 1000,
                "total_pages": 100,
                "page": 5,
                "page_size": 10,
                "links": {
                    "first": "http://example.com?page=1",
                    "prev": "http://example.com?page=4",
                    "next": "http://example.com?page=6",
                    "last": "http://example.com?page=100",
                },
            },
        }

        assert result == expected

    def test_items_property(self):
        """Test async items property access"""
        data = {"items": [{"id": 1}, {"id": 2}], "pagination": {"total_items": 100}}

        response = AsyncPaginatedResponse(data)

        assert response.items == [{"id": 1}, {"id": 2}]

    def test_metadata_property(self):
        """Test async metadata property access"""
        data = {"items": [{"id": 1}], "pagination": {"total_items": 100, "page": 1}}

        response = AsyncPaginatedResponse(data)

        assert response.metadata == {"total_items": 100, "page": 1}

    def test_large_dataset(self):
        """Test async with large dataset"""
        # Create a large dataset
        items = [{"id": i, "data": f"item_{i}_data"} for i in range(1000)]
        data = {
            "items": items,
            "pagination": {
                "total_items": 50000,
                "page": 1,
                "page_size": 1000,
                "links": {"next": "http://example.com?page=2"},
            },
        }

        response = AsyncPaginatedResponse(data)
        result = response.to_dict()

        assert len(result["data"]) == 1000
        assert result["pagination"]["total_items"] == 50000


class TestResponseConsistency:
    """Test cases for consistency between sync and async responses"""

    def test_sync_async_response_consistency(self):
        """Test that sync and async responses produce identical output"""
        data = {
            "items": [{"id": 1}, {"id": 2}, {"id": 3}],
            "pagination": {
                "total_items": 100,
                "page": 1,
                "page_size": 10,
                "links": {
                    "next": "http://example.com?page=2",
                    "last": "http://example.com?page=10",
                },
            },
        }

        sync_response = PaginatedResponse(data)
        async_response = AsyncPaginatedResponse(data)

        sync_result = sync_response.to_dict()
        async_result = async_response.to_dict()

        # Results should be identical
        assert sync_result == async_result

        # Items and metadata should also be identical
        assert sync_response.items == async_response.items
        assert sync_response.metadata == async_response.metadata

    def test_empty_data_consistency(self):
        """Test consistency with empty data"""
        data = {
            "items": [],
            "pagination": {"total_items": 0, "page": 1, "page_size": 10, "links": {}},
        }

        sync_response = PaginatedResponse(data)
        async_response = AsyncPaginatedResponse(data)

        sync_result = sync_response.to_dict()
        async_result = async_response.to_dict()

        assert sync_result == async_result
