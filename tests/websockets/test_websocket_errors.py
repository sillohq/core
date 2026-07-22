"""
Tests for WebSocket error handling middleware
"""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sillo import silloApp
from sillo.exceptions import WebSocketException
from sillo.core.routing import Router
from sillo.testclient import TestClient
from sillo.types import ASGIApp, Receive, Scope, Send
from sillo.websockets.base import WebSocket
from sillo.websockets.errors import (
    WebSocketErrorMiddleware,
    websocket_exception_handler,
)


class TestWebSocketErrorMiddleware:
    """Test WebSocketErrorMiddleware functionality"""

    def test_websocket_scope_passes_through_middleware(self):
        """Test that websocket scope calls are handled by middleware"""
        app = AsyncMock()

        middleware = WebSocketErrorMiddleware(app)

        # Create a websocket scope
        scope: Scope = {
            "type": "websocket",
            "path": "/ws/test",
            "query_string": b"",
            "headers": [],
        }

        receive = AsyncMock()
        send = AsyncMock()

        # Should call the app
        asyncio.run(middleware(scope, receive, send))
        app.assert_called_once_with(scope, receive, send)

    def test_non_websocket_scope_passes_through(self):
        """Test that non-websocket scopes are passed through without modification"""
        app = AsyncMock()

        middleware = WebSocketErrorMiddleware(app)

        # Create a non-websocket scope (HTTP)
        scope: Scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "query_string": b"",
            "headers": [],
        }

        receive = AsyncMock()
        send = AsyncMock()

        # Should call the app directly without middleware processing
        asyncio.run(middleware(scope, receive, send))
        app.assert_called_once_with(scope, receive, send)

    def test_general_exception_handling(self):
        """Test that general exceptions are handled as internal server errors"""

        # Create an app that raises a general exception
        async def failing_app(scope: Scope, receive: Receive, send: Send):
            raise ValueError("Something went wrong")

        middleware = WebSocketErrorMiddleware(failing_app)

        # Create websocket scope
        scope: Scope = {
            "type": "websocket",
            "path": "/ws/test",
            "query_string": b"",
            "headers": [],
        }

        receive = AsyncMock()
        send = AsyncMock()

        # Should handle the exception and close websocket with internal error
        asyncio.run(middleware(scope, receive, send))

        # Verify websocket.close was called with internal server error code
        send.assert_called_once_with(
            {"type": "websocket.close", "code": 1011, "reason": "Internal Server Error"}
        )

    def test_logging_on_websocket_exception(self):
        """Test that WebSocketException is logged"""

        async def failing_app(scope: Scope, receive: Receive, send: Send):
            raise WebSocketException(code=1008, reason="Test error")

        middleware = WebSocketErrorMiddleware(failing_app)

        scope: Scope = {
            "type": "websocket",
            "path": "/ws/test",
            "query_string": b"",
            "headers": [],
        }

        receive = AsyncMock()
        send = AsyncMock()

        with patch("sillo.websockets.errors.logger") as mock_logger:
            asyncio.run(middleware(scope, receive, send))

            # Verify error was logged
            mock_logger.error.assert_called_once()
            log_call = mock_logger.error.call_args[0][0]
            assert "WebSocket error:" in log_call

    def test_logging_on_general_exception(self):
        """Test that general exceptions are logged"""

        async def failing_app(scope: Scope, receive: Receive, send: Send):
            raise RuntimeError("Unexpected error")

        middleware = WebSocketErrorMiddleware(failing_app)

        scope: Scope = {
            "type": "websocket",
            "path": "/ws/test",
            "query_string": b"",
            "headers": [],
        }

        receive = AsyncMock()
        send = AsyncMock()

        with patch("sillo.websockets.errors.logger") as mock_logger:
            asyncio.run(middleware(scope, receive, send))

            # Verify error was logged
            mock_logger.error.assert_called_once()
            log_call = mock_logger.error.call_args[0][0]
            assert "Unexpected error:" in log_call


class TestWebSocketErrorIntegration:
    """Integration tests for websocket error handling"""

    def test_websocket_route_with_exception(
        self, test_client_factory: pytest.FixtureRequest
    ):
        """Test websocket route that raises WebSocketException"""
        app = silloApp()

        @app.ws_route("/ws/error")
        async def error_endpoint(websocket: WebSocket):
            raise WebSocketException(code=1008, reason="Policy violation")

        with test_client_factory(app) as client:
            # WebSocket connection should be rejected/closed due to exception
            with pytest.raises(Exception):  # Connection should fail
                with client.websocket_connect("/ws/error"):
                    pass  # This should not be reached

    def test_websocket_route_with_general_exception(
        self, test_client_factory: pytest.FixtureRequest
    ):
        """Test websocket route that raises general exception"""
        app = silloApp()

        @app.ws_route("/ws/general-error")
        async def general_error_endpoint(websocket: WebSocket):
            raise ValueError("Something went wrong")

        with test_client_factory(app) as client:
            # WebSocket connection should be closed with internal error
            with pytest.raises(Exception):  # Connection should fail
                with client.websocket_connect("/ws/general-error"):
                    pass  # This should not be reached

    def test_websocket_route_normal_operation(self, test_client_factory):
        """Test that normal websocket operation still works"""
        app = silloApp()

        @app.ws_route("/ws/normal")
        async def normal_endpoint(websocket: WebSocket):
            await websocket.accept()
            data = await websocket.receive_text()
            await websocket.send_text(f"Echo: {data}")
            await websocket.close()

        with test_client_factory(app) as client:
            with client.websocket_connect("/ws/normal") as websocket:
                websocket.send_text("Hello")
                response = websocket.receive_text()
                assert response == "Echo: Hello"

    def test_router_with_error_middleware(self, test_client_factory):
        """Test that router properly applies error middleware"""
        router = Router(prefix="/api")

        @router.ws_route("/error")
        async def router_error_endpoint(websocket: WebSocket):
            raise WebSocketException(code=1009, reason="Router error")

        app = silloApp()
        app.mount_router(router)

        with test_client_factory(app) as client:
            with pytest.raises(Exception):
                with client.websocket_connect("/api/error"):
                    pass  # Should not be reached
