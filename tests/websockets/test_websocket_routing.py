"""
Tests for WebSocket routing functionality
"""

from typing import Callable

import pytest

from sillo import silloApp
from sillo.routing import Router
from sillo.testclient import TestClient
from sillo.websockets import WebSocket


def test_basic_websocket_route(test_client_factory: Callable[[silloApp], TestClient]):
    """Test basic WebSocket route"""
    app = silloApp()

    @app.ws_route("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        data = await websocket.receive_text()
        await websocket.send_text(f"Echo: {data}")
        await websocket.close()

    with test_client_factory(app) as client:
        with client.websocket_connect("/ws") as websocket:
            websocket.send_text("Hello")
            data = websocket.receive_text()
            assert data == "Echo: Hello"


def test_websocket_json_communication(
    test_client_factory: Callable[[silloApp], TestClient],
):
    """Test WebSocket JSON message exchange"""
    app = silloApp()

    @app.ws_route("/ws/json")
    async def websocket_json(websocket: WebSocket):
        await websocket.accept()
        data = await websocket.receive_json()
        await websocket.send_json({"received": data, "status": "ok"})
        await websocket.close()

    with test_client_factory(app) as client:
        with client.websocket_connect("/ws/json") as websocket:
            websocket.send_json({"message": "test", "value": 42})
            response = websocket.receive_json()
            assert response["status"] == "ok"
            assert response["received"]["message"] == "test"
            assert response["received"]["value"] == 42


def test_websocket_bytes_communication(
    test_client_factory: Callable[[silloApp], TestClient],
):
    """Test WebSocket binary message exchange"""
    app = silloApp()

    @app.ws_route("/ws/bytes")
    async def websocket_bytes(websocket: WebSocket):
        await websocket.accept()
        data = await websocket.receive_bytes()
        await websocket.send_bytes(b"Received: " + data)
        await websocket.close()

    with test_client_factory(app) as client:
        with client.websocket_connect("/ws/bytes") as websocket:
            websocket.send_bytes(b"binary data")
            response = websocket.receive_bytes()
            assert response == b"Received: binary data"


def test_websocket_with_path_parameters(
    test_client_factory: Callable[[silloApp], TestClient],
):
    """Test WebSocket route with path parameters"""
    app = silloApp()

    @app.ws_route("/ws/room/{room_id}")
    async def websocket_room(websocket: WebSocket):
        room_id = websocket.path_params["room_id"]
        await websocket.accept()
        await websocket.send_json({"room": room_id, "status": "connected"})
        await websocket.close()

    with test_client_factory(app) as client:
        with client.websocket_connect("/ws/room/lobby") as websocket:
            data = websocket.receive_json()
            assert data["room"] == "lobby"
            assert data["status"] == "connected"


def test_websocket_multiple_messages(
    test_client_factory: Callable[[silloApp], TestClient],
):
    """Test WebSocket with multiple message exchanges"""
    app = silloApp()

    @app.ws_route("/ws/chat")
    async def websocket_chat(websocket: WebSocket):
        await websocket.accept()
        for i in range(3):
            data = await websocket.receive_text()
            await websocket.send_text(f"Message {i + 1}: {data}")
        await websocket.close()

    with test_client_factory(app) as client:
        with client.websocket_connect("/ws/chat") as websocket:
            websocket.send_text("First")
            assert websocket.receive_text() == "Message 1: First"

            websocket.send_text("Second")
            assert websocket.receive_text() == "Message 2: Second"

            websocket.send_text("Third")
            assert websocket.receive_text() == "Message 3: Third"


def test_websocket_router_mounting(
    test_client_factory: Callable[[silloApp], TestClient],
):
    """Test WebSocket router mounting"""
    app = silloApp()
    ws_router = Router(prefix="/api/ws")

    @ws_router.ws_route("/echo")
    async def echo_endpoint(websocket: WebSocket):
        await websocket.accept()
        data = await websocket.receive_text()
        await websocket.send_text(f"Router echo: {data}")
        await websocket.close()

    app.mount_router(ws_router)

    with test_client_factory(app) as client:
        with client.websocket_connect("/api/ws/echo") as websocket:
            websocket.send_text("Hello Router")
            data = websocket.receive_text()
            assert data == "Router echo: Hello Router"


def test_websocket_multiple_routers(
    test_client_factory: Callable[[silloApp], TestClient],
):
    """Test multiple WebSocket routers"""
    app = silloApp()

    chat_router = Router(prefix="/chat")

    @chat_router.ws_route("/room")
    async def chat_room(websocket: WebSocket):
        await websocket.accept()
        await websocket.send_text("Chat room")
        await websocket.close()

    api_router = Router(prefix="/api")

    @api_router.ws_route("/status")
    async def api_status(websocket: WebSocket):
        await websocket.accept()
        await websocket.send_json({"status": "online"})
        await websocket.close()

    app.mount_router(chat_router)
    app.mount_router(api_router)

    with test_client_factory(app) as client:
        with client.websocket_connect("/chat/room") as websocket:
            assert websocket.receive_text() == "Chat room"

        with client.websocket_connect("/api/status") as websocket:
            data = websocket.receive_json()
            assert data["status"] == "online"


def test_websocket_nested_routers(
    test_client_factory: Callable[[silloApp], TestClient],
):
    """Test nested WebSocket routers"""
    app = silloApp()

    inner_router = Router(prefix="/v1")

    @inner_router.ws_route("/endpoint")
    async def inner_endpoint(websocket: WebSocket):
        await websocket.accept()
        await websocket.send_text("Nested endpoint")
        await websocket.close()

    outer_router = Router(prefix="/api")
    outer_router.mount_router(inner_router)

    app.mount_router(outer_router)

    with test_client_factory(app) as client:
        with client.websocket_connect("/api/v1/endpoint") as websocket:
            data = websocket.receive_text()
            assert data == "Nested endpoint"


def test_websocket_with_query_parameters(
    test_client_factory: Callable[[silloApp], TestClient],
):
    """Test WebSocket with query parameters"""
    app = silloApp()

    @app.ws_route("/ws/query")
    async def websocket_query(websocket: WebSocket):
        await websocket.accept()
        query_params = dict(websocket.query_params)
        await websocket.send_json(query_params)
        await websocket.close()

    with test_client_factory(app) as client:
        with client.websocket_connect("/ws/query?name=test&value=123") as websocket:
            data = websocket.receive_json()
            assert data["name"] == "test"
            assert data["value"] == "123"


def test_websocket_isolation(test_client_factory: Callable[[silloApp], TestClient]):
    """Test that WebSocket routes are isolated"""
    app = silloApp()

    router1 = Router(prefix="/ws1")

    @router1.ws_route("/test")
    async def ws1_test(websocket: WebSocket):
        await websocket.accept()
        await websocket.send_text("Router 1")
        await websocket.close()

    router2 = Router(prefix="/ws2")

    @router2.ws_route("/test")
    async def ws2_test(websocket: WebSocket):
        await websocket.accept()
        await websocket.send_text("Router 2")
        await websocket.close()

    app.mount_router(router1)
    app.mount_router(router2)

    with test_client_factory(app) as client:
        with client.websocket_connect("/ws1/test") as websocket:
            assert websocket.receive_text() == "Router 1"

        with client.websocket_connect("/ws2/test") as websocket:
            assert websocket.receive_text() == "Router 2"
