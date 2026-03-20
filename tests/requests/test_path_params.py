"""
Tests for request path parameters
"""

from typing import Callable

import pytest

from nexios import NexiosApp
from nexios.http import Request, Response
from nexios.testclient import TestClient

# ========== Path Parameters Tests ==========


def test_request_path_params_single(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test single path parameter"""
    app = NexiosApp()

    @app.get("/users/{user_id}")
    async def handler(request: Request, response: Response, user_id: str):
        return response.json({"user_id": user_id})

    with test_client_factory(app) as client:
        resp = client.get("/users/123")
        assert resp.status_code == 200
        assert resp.json()["user_id"] == "123"


def test_request_path_params_multiple(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test multiple path parameters"""
    app = NexiosApp()

    @app.get("/users/{user_id}/posts/{post_id}")
    async def handler(request: Request, response: Response, user_id: str, post_id: str):
        return response.json({"user_id": user_id, "post_id": post_id})

    with test_client_factory(app) as client:
        resp = client.get("/users/456/posts/789")
        data = resp.json()
        assert data["user_id"] == "456"
        assert data["post_id"] == "789"


def test_request_path_params_numeric(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test path parameters with numeric values"""
    app = NexiosApp()

    @app.get("/products/{product_id}")
    async def handler(request: Request, response: Response, product_id: str):
        return response.json(
            {
                "product_id": product_id,
                "product_id_int": int(product_id) if product_id else None,
            }
        )

    with test_client_factory(app) as client:
        resp = client.get("/products/999")
        data = resp.json()
        assert data["product_id"] == "999"
        assert data["product_id_int"] == 999


def test_request_path_params_with_special_chars(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test path parameters with special characters"""
    app = NexiosApp()

    @app.get("/files/{filename}")
    async def handler(request: Request, response: Response, filename: str):
        return response.json({"filename": filename})

    with test_client_factory(app) as client:
        resp = client.get("/files/document.pdf")
        assert resp.json()["filename"] == "document.pdf"


def test_request_path_params_uuid_like(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test path parameters with UUID-like values"""
    app = NexiosApp()

    @app.get("/resources/{resource_id}")
    async def handler(request: Request, response: Response, resource_id: str):
        return response.json({"resource_id": resource_id})

    with test_client_factory(app) as client:
        uuid = "550e8400-e29b-41d4-a716-446655440000"
        resp = client.get(f"/resources/{uuid}")
        assert resp.json()["resource_id"] == uuid


def test_request_path_params_with_hyphens(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test path parameters with hyphens"""
    app = NexiosApp()

    @app.get("/posts/{post_slug}")
    async def handler(request: Request, response: Response, post_slug: str):
        return response.json({"post_slug": post_slug})

    with test_client_factory(app) as client:
        resp = client.get("/posts/my-awesome-post")
        assert resp.json()["post_slug"] == "my-awesome-post"


def test_request_path_params_with_underscores(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test path parameters with underscores"""
    app = NexiosApp()

    @app.get("/files/{file_name}")
    async def handler(request: Request, response: Response, file_name: str):
        return response.json({"file_name": file_name})

    with test_client_factory(app) as client:
        resp = client.get("/files/my_file_name")
        assert resp.json()["file_name"] == "my_file_name"


def test_request_path_params_nested_resources(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test path parameters for nested resources"""
    app = NexiosApp()

    @app.get("/users/{user_id}/posts/{post_id}/comments/{comment_id}")
    async def handler(
        request: Request,
        response: Response,
        user_id: str,
        post_id: str,
        comment_id: str,
    ):
        return response.json(
            {
                "user_id": user_id,
                "post_id": post_id,
                "comment_id": comment_id,
            }
        )

    with test_client_factory(app) as client:
        resp = client.get("/users/1/posts/2/comments/3")
        data = resp.json()
        assert data["user_id"] == "1"
        assert data["post_id"] == "2"
        assert data["comment_id"] == "3"
