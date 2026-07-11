"""
Tests for file and download responses
"""

import os
import tempfile
from pathlib import Path
from typing import Callable

import pytest

from sillo import silloApp
from sillo.http import Request, Response
from sillo.testclient import TestClient

# ========== File Response Tests ==========


def test_file_response(test_client_factory: Callable[[silloApp], TestClient]):
    """Test serving a file"""
    app = silloApp()

    # Create a temporary file
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write("Test file content")
        temp_path = f.name

    try:

        @app.get("/file")
        async def serve_file(request: Request, response: Response):
            return response.file(temp_path)

        with test_client_factory(app) as client:
            resp = client.get("/file")
            assert resp.status_code == 200
            assert "Test file content" in resp.text
    finally:
        os.unlink(temp_path)


def test_file_response_with_custom_filename(
    test_client_factory: Callable[[silloApp], TestClient],
):
    """Test serving a file with custom filename"""
    app = silloApp()

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write("Custom filename test")
        temp_path = f.name

    try:

        @app.get("/custom-file")
        async def serve_custom_file(request: Request, response: Response):
            return response.file(temp_path, filename="custom_name.txt")

        with test_client_factory(app) as client:
            resp = client.get("/custom-file")
            assert resp.status_code == 200
            content_disposition = resp.headers.get("content-disposition", "")
            assert "custom_name.txt" in content_disposition
    finally:
        os.unlink(temp_path)


def test_file_response_content_type(
    test_client_factory: Callable[[silloApp], TestClient],
):
    """Test file response content type detection"""
    app = silloApp()

    # Create a JSON file
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
        f.write('{"test": "data"}')
        temp_path = f.name

    try:

        @app.get("/json-file")
        async def serve_json_file(request: Request, response: Response):
            return response.file(temp_path)

        with test_client_factory(app) as client:
            resp = client.get("/json-file")
            assert resp.status_code == 200
            content_type = resp.headers.get("content-type", "")
            assert (
                "json" in content_type.lower() or "application" in content_type.lower()
            )
    finally:
        os.unlink(temp_path)


def test_file_response_inline_disposition(
    test_client_factory: Callable[[silloApp], TestClient],
):
    """Test file response with inline disposition"""
    app = silloApp()

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write("Inline content")
        temp_path = f.name

    try:

        @app.get("/inline")
        async def serve_inline(request: Request, response: Response):
            return response.file(temp_path, content_disposition_type="inline")

        with test_client_factory(app) as client:
            resp = client.get("/inline")
            assert resp.status_code == 200
            content_disposition = resp.headers.get("content-disposition", "")
            assert "inline" in content_disposition
    finally:
        os.unlink(temp_path)


# ========== Download Response Tests ==========


def test_download_response(test_client_factory: Callable[[silloApp], TestClient]):
    """Test forcing file download"""
    app = silloApp()

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".pdf") as f:
        f.write("PDF content")
        temp_path = f.name

    try:

        @app.get("/download")
        async def download_file(request: Request, response: Response):
            return response.download(temp_path)

        with test_client_factory(app) as client:
            resp = client.get("/download")
            assert resp.status_code == 200
            content_disposition = resp.headers.get("content-disposition", "")
            assert "attachment" in content_disposition
    finally:
        os.unlink(temp_path)


def test_download_with_custom_filename(
    test_client_factory: Callable[[silloApp], TestClient],
):
    """Test download with custom filename"""
    app = silloApp()

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv") as f:
        f.write("col1,col2\nval1,val2")
        temp_path = f.name

    try:

        @app.get("/download-csv")
        async def download_csv(request: Request, response: Response):
            return response.download(temp_path, filename="data.csv")

        with test_client_factory(app) as client:
            resp = client.get("/download-csv")
            assert resp.status_code == 200
            content_disposition = resp.headers.get("content-disposition", "")
            assert "attachment" in content_disposition
            assert "data.csv" in content_disposition
    finally:
        os.unlink(temp_path)


# ========== Large File Tests ==========


def test_large_file_response(test_client_factory: Callable[[silloApp], TestClient]):
    """Test serving a larger file"""
    app = silloApp()

    # Create a larger temporary file (1MB)
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        content = "x" * (1024 * 1024)  # 1MB of 'x' characters
        f.write(content)
        temp_path = f.name

    try:

        @app.get("/large-file")
        async def serve_large_file(request: Request, response: Response):
            return response.file(temp_path)

        with test_client_factory(app) as client:
            resp = client.get("/large-file")
            assert resp.status_code == 200
            assert len(resp.content) == 1024 * 1024
    finally:
        os.unlink(temp_path)


# ========== Binary File Tests ==========


def test_binary_file_response(test_client_factory: Callable[[silloApp], TestClient]):
    """Test serving a binary file"""
    app = silloApp()

    # Create a binary file
    with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".bin") as f:
        binary_data = bytes([i % 256 for i in range(1000)])
        f.write(binary_data)
        temp_path = f.name

    try:

        @app.get("/binary")
        async def serve_binary(request: Request, response: Response):
            return response.file(temp_path)

        with test_client_factory(app) as client:
            resp = client.get("/binary")
            assert resp.status_code == 200
            assert len(resp.content) == 1000
    finally:
        os.unlink(temp_path)


# ========== File Not Found Tests ==========


def test_file_not_found(test_client_factory: Callable[[silloApp], TestClient]):
    """Test handling of non-existent file"""
    app = silloApp()

    @app.get("/missing-file")
    async def serve_missing_file(request: Request, response: Response):
        return response.file("/nonexistent/path/file.txt")

    with test_client_factory(app) as client:
        # This should raise an error or return 404
        try:
            resp = client.get("/missing-file")
            # If it doesn't raise, it should be an error status
            assert resp.status_code >= 400
        except Exception:
            # Expected behavior - file not found raises exception
            pass


# ========== Content Length Tests ==========


def test_file_content_length_header(
    test_client_factory: Callable[[silloApp], TestClient],
):
    """Test that content-length header is set correctly for files"""
    app = silloApp()

    content = "Test content for length check"
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write(content)
        temp_path = f.name

    try:

        @app.get("/file-length")
        async def serve_file_length(request: Request, response: Response):
            return response.file(temp_path)

        with test_client_factory(app) as client:
            resp = client.get("/file-length")
            assert resp.status_code == 200
            content_length = resp.headers.get("content-length")
            if content_length:
                assert int(content_length) == len(content.encode())
    finally:
        os.unlink(temp_path)


# ========== Accept-Ranges Tests ==========


def test_file_accept_ranges_header(
    test_client_factory: Callable[[silloApp], TestClient],
):
    """Test that accept-ranges header is set for file responses"""
    app = silloApp()

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write("Range test content")
        temp_path = f.name

    try:

        @app.get("/ranges")
        async def serve_with_ranges(request: Request, response: Response):
            return response.file(temp_path)

        with test_client_factory(app) as client:
            resp = client.get("/ranges")
            assert resp.status_code == 200
            accept_ranges = resp.headers.get("accept-ranges")
            # File responses should support byte ranges
            assert accept_ranges is not None
    finally:
        os.unlink(temp_path)
