import pytest

from nexios import NexiosApp
from nexios.http import Request, Response
from nexios.pagination import (
    AsyncListDataHandler,
    AsyncPaginator,
    CursorPagination,
    LimitOffsetPagination,
    PageNumberPagination,
    PaginationError,
)
from nexios.testclient import TestClient


@pytest.fixture
def test_client(test_client_factory):
    """Create a test client for integration testing"""
    app = NexiosApp()
    with test_client_factory(app) as client:
        yield client, app


class TestPaginationIntegration:
    """Integration tests for pagination with Nexios app and TestClient"""

    async def test_page_number_pagination_integration(self, test_client):
        """Test page number pagination integration with Nexios app"""
        client, app = test_client

        # Sample test data
        test_data = [{"id": i, "name": f"Item {i}"} for i in range(1, 101)]

        @app.get("/items")
        async def get_items(req: Request, res: Response):
            handler = AsyncListDataHandler(test_data)
            pagination = PageNumberPagination()
            base_url = str(req.url)

            try:
                paginator = AsyncPaginator(
                    handler, pagination, base_url, dict(req.query_params)
                )
                result = await paginator.paginate()
                return res.json(result)
            except PaginationError as e:
                return res.json({"error": str(e)}, status_code=400)

        # Test basic pagination
        response = client.get("/items?page=2&page_size=10")
        assert response.status_code == 200
        data = response.json()

        assert len(data["items"]) == 10
        assert data["items"][0]["id"] == 11
        assert data["pagination"]["total_items"] == 100
        assert data["pagination"]["page"] == 2
        assert "next" in data["pagination"]["links"]
        assert "prev" in data["pagination"]["links"]

    async def test_limit_offset_pagination_integration(self, test_client):
        """Test limit offset pagination integration with Nexios app"""
        client, app = test_client

        test_data = [{"id": i, "name": f"Item {i}"} for i in range(1, 101)]

        @app.get("/items-limit-offset")
        async def get_items(req: Request, res: Response):
            handler = AsyncListDataHandler(test_data)
            pagination = LimitOffsetPagination()
            base_url = str(req.url)

            try:
                paginator = AsyncPaginator(
                    handler, pagination, base_url, dict(req.query_params)
                )
                result = await paginator.paginate()
                return res.json(result)
            except PaginationError as e:
                return res.json({"error": str(e)}, status_code=400)

        # Test basic pagination
        response = client.get("/items-limit-offset?limit=15&offset=30")
        assert response.status_code == 200
        data = response.json()

        assert len(data["items"]) == 15
        assert data["items"][0]["id"] == 31
        assert data["pagination"]["total_items"] == 100
        assert data["pagination"]["offset"] == 30
        assert data["pagination"]["limit"] == 15

    async def test_cursor_pagination_integration(self, test_client):
        """Test cursor pagination integration with Nexios app"""
        client, app = test_client

        test_data = [{"id": i, "name": f"Item {i}"} for i in range(1, 101)]

        @app.get("/items-cursor")
        async def get_items(req: Request, res: Response):
            handler = AsyncListDataHandler(test_data)
            pagination = CursorPagination()
            base_url = str(req.url)

            try:
                paginator = AsyncPaginator(
                    handler, pagination, base_url, dict(req.query_params)
                )
                result = await paginator.paginate()
                return res.json(result)
            except PaginationError as e:
                return res.json({"error": str(e)}, status_code=400)

        # Test initial request
        response = client.get("/items-cursor?page_size=10")
        assert response.status_code == 200
        data = response.json()

        assert len(data["items"]) == 10
        assert data["items"][0]["id"] == 1
        assert "next" in data["pagination"]["links"]
        assert "prev" not in data["pagination"]["links"]

        # Test with cursor navigation
        next_cursor = (
            data["pagination"]["links"]["next"].split("cursor=")[1].split("&")[0]
        )
        response = client.get(f"/items-cursor?cursor={next_cursor}&page_size=10")
        assert response.status_code == 200
        data = response.json()

        assert len(data["items"]) == 10
        assert data["items"][0]["id"] == 11
        assert "next" in data["pagination"]["links"]
        assert "prev" in data["pagination"]["links"]

    async def test_pagination_with_filters_integration(self, test_client):
        """Test pagination integration with query filters"""
        client, app = test_client

        # Create filtered data handler
        class FilteredDataHandler(AsyncListDataHandler):
            async def get_total_items(self) -> int:
                return len([item for item in self.data if item["id"] % 2 == 0])

            async def get_items(self, offset: int, limit: int) -> list:
                filtered = [item for item in self.data if item["id"] % 2 == 0]
                return filtered[offset : offset + limit]

        test_data = [{"id": i, "name": f"Item {i}"} for i in range(1, 101)]

        @app.get("/filtered-items")
        async def get_filtered_items(req: Request, res: Response):
            handler = FilteredDataHandler(test_data)
            pagination = PageNumberPagination()
            base_url = str(req.url)

            try:
                paginator = AsyncPaginator(
                    handler, pagination, base_url, dict(req.query_params)
                )
                result = await paginator.paginate()
                return res.json(result)
            except PaginationError as e:
                return res.json({"error": str(e)}, status_code=400)

        response = client.get("/filtered-items?page=2&page_size=10&filter=even")
        assert response.status_code == 200
        data = response.json()

        assert len(data["items"]) == 10
        assert all(item["id"] % 2 == 0 for item in data["items"])
        assert data["pagination"]["total_items"] == 50  # Only even IDs

        # Check that filter is preserved in links
        next_link = data["pagination"]["links"]["next"]
        assert "filter=even" in next_link

    async def test_pagination_error_handling_integration(self, test_client):
        """Test pagination error handling integration"""
        client, app = test_client

        @app.get("/error-test")
        async def error_test(req: Request, res: Response):
            handler = AsyncListDataHandler([])
            pagination = PageNumberPagination()
            base_url = str(req.url)

            try:
                paginator = AsyncPaginator(
                    handler,
                    pagination,
                    base_url,
                    dict(req.query_params),
                    validate_total_items=False,
                )
                result = await paginator.paginate()
                return res.json(result)
            except PaginationError as e:
                return res.json({"error": str(e)}, status_code=400)

        # Test invalid page
        response = client.get("/error-test?page=0")
        assert response.status_code == 400
        assert "Page number must be at least 1" in response.json()["error"]

        # Test invalid page size
        response = client.get("/error-test?page_size=0")
        assert response.status_code == 400
        assert "Page size must be at least 1" in response.json()["error"]

    async def test_pagination_with_custom_metadata_integration(self, test_client):
        """Test pagination integration with custom metadata"""
        client, app = test_client

        class CustomPagination(PageNumberPagination):
            def generate_metadata(self, total_items, items, base_url, request_params):
                metadata = super().generate_metadata(
                    total_items, items, base_url, request_params
                )
                metadata["custom_field"] = "custom_value"
                metadata["request_id"] = request_params.get("request_id", "unknown")
                return metadata

        test_data = [{"id": i, "name": f"Item {i}"} for i in range(1, 101)]

        @app.get("/custom-metadata")
        async def custom_metadata(req: Request, res: Response):
            handler = AsyncListDataHandler(test_data)
            pagination = CustomPagination()
            base_url = str(req.url)

            paginator = AsyncPaginator(
                handler, pagination, base_url, dict(req.query_params)
            )
            result = await paginator.paginate()
            return res.json(result)

        response = client.get("/custom-metadata?page=1&request_id=123")
        assert response.status_code == 200
        data = response.json()

        assert data["pagination"]["custom_field"] == "custom_value"
        assert data["pagination"]["request_id"] == "123"

    async def test_multiple_pagination_endpoints(self, test_client):
        """Test multiple pagination endpoints in same app"""
        client, app = test_client

        test_data = [{"id": i, "name": f"Item {i}"} for i in range(1, 101)]

        @app.get("/items-page")
        async def get_items_page(req: Request, res: Response):
            handler = AsyncListDataHandler(test_data)
            pagination = PageNumberPagination()
            base_url = str(req.url)

            paginator = AsyncPaginator(
                handler, pagination, base_url, dict(req.query_params)
            )
            result = await paginator.paginate()
            return res.json(result)

        @app.get("/items-limit")
        async def get_items_limit(req: Request, res: Response):
            handler = AsyncListDataHandler(test_data)
            pagination = LimitOffsetPagination()
            base_url = str(req.url)

            paginator = AsyncPaginator(
                handler, pagination, base_url, dict(req.query_params)
            )
            result = await paginator.paginate()
            return res.json(result)

        @app.get("/items-cursor")
        async def get_items_cursor(req: Request, res: Response):
            handler = AsyncListDataHandler(test_data)
            pagination = CursorPagination()
            base_url = str(req.url)

            paginator = AsyncPaginator(
                handler, pagination, base_url, dict(req.query_params)
            )
            result = await paginator.paginate()
            return res.json(result)

        # Test page number pagination
        response = client.get("/items-page?page=2&page_size=5")
        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["page"] == 2
        assert len(data["items"]) == 5

        # Test limit offset pagination
        response = client.get("/items-limit?limit=10&offset=20")
        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["offset"] == 20
        assert data["pagination"]["limit"] == 10

        # Test cursor pagination
        response = client.get("/items-cursor?page_size=8")
        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["page_size"] == 8
        assert len(data["items"]) == 8

    async def test_pagination_with_complex_query_params(self, test_client):
        """Test pagination with complex query parameters"""
        client, app = test_client

        test_data = [
            {"id": i, "category": "tech", "tags": ["python", "web"]}
            for i in range(1, 101)
        ]

        @app.get("/complex-items")
        async def get_complex_items(req: Request, res: Response):
            handler = AsyncListDataHandler(test_data)
            pagination = PageNumberPagination()
            base_url = str(req.url)

            paginator = AsyncPaginator(
                handler, pagination, base_url, dict(req.query_params)
            )
            result = await paginator.paginate()
            return res.json(result)

        # Test with multiple query parameters
        response = client.get(
            "/complex-items?page=1&page_size=5&category=tech&sort=name&filter=active&tags=python&tags=web"
        )
        assert response.status_code == 200
        data = response.json()

        assert len(data["items"]) == 5
        assert data["pagination"]["page"] == 1

        # Check that all query params are preserved in links
        next_link = data["pagination"]["links"]["next"]
        assert "category=tech" in next_link
        assert "sort=name" in next_link
        assert "filter=active" in next_link
        assert "tags=python" in next_link
        assert "tags=web" in next_link
        assert "page=2" in next_link


class TestPaginationPerformance:
    """Performance tests for pagination"""
