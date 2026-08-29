"""
Tests for WebSocketContext consumers functionality
"""

from typing import Any, Callable

import pytest

from sillo import SilloApp
from sillo.core.routing import Router
from sillo.testclient import TestClient
from sillo.websockets import WebSocketContext, WebSocketConsumer


class EchoConsumer(WebSocketConsumer):
    """Simple echo consumer"""

    encoding = "text"

    async def on_receive(self, websocket: WebSocketContext, data: Any) -> None:
        await websocket.send_text(f"Echo: {data}")


class JsonConsumer(WebSocketConsumer):
    """JSON consumer"""

    encoding = "json"

    async def on_receive(self, websocket: WebSocketContext, data: Any) -> None:
        await websocket.send_json({"received": data, "type": "json"})


class BytesConsumer(WebSocketConsumer):
    """Bytes consumer"""

    encoding = "bytes"

    async def on_receive(self, websocket: WebSocketContext, data: Any) -> None:
        await websocket.send_bytes(b"Received: " + data)


class CounterConsumer(WebSocketConsumer):
    """Consumer that counts messages"""

    encoding = "text"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.count = 0

    async def on_receive(self, websocket: WebSocketContext, data: Any) -> None:
        self.count += 1
        await websocket.send_text(f"Message #{self.count}: {data}")


class StatefulConsumer(WebSocketConsumer):
    """Consumer with connection state"""

    encoding = "json"

    async def on_connect(self, websocket: WebSocketContext) -> None:
        await websocket.accept()
        await websocket.send_json({"status": "connected", "message": "Welcome"})

    async def on_receive(self, websocket: WebSocketContext, data: Any) -> None:
        if data.get("action") == "ping":
            await websocket.send_json({"response": "pong"})
        elif data.get("action") == "echo":
            await websocket.send_json({"response": data.get("message")})

    async def on_disconnect(self, websocket: WebSocketContext, close_code: int) -> None:
        # Cleanup logic here
        pass


def test_echo_consumer(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test basic echo consumer"""
    app = SilloApp()

    route = EchoConsumer.as_route("/ws/echo")
    app.add_ws_route(route)

    with test_client_factory(app) as client:
        with client.websocket_connect("/ws/echo") as websocket:
            websocket.send_text("Hello Consumer")
            data = websocket.receive_text()
            assert data == "Echo: Hello Consumer"


def test_json_consumer(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test JSON consumer"""
    app = SilloApp()

    route = JsonConsumer.as_route("/ws/json")
    app.add_ws_route(route)

    with test_client_factory(app) as client:
        with client.websocket_connect("/ws/json") as websocket:
            websocket.send_json({"message": "test", "value": 42})
            response = websocket.receive_json()
            assert response["type"] == "json"
            assert response["received"]["message"] == "test"
            assert response["received"]["value"] == 42


def test_bytes_consumer(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test bytes consumer"""
    app = SilloApp()

    route = BytesConsumer.as_route("/ws/bytes")
    app.add_ws_route(route)

    with test_client_factory(app) as client:
        with client.websocket_connect("/ws/bytes") as websocket:
            websocket.send_bytes(b"binary data")
            response = websocket.receive_bytes()
            assert response == b"Received: binary data"


def test_counter_consumer(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test consumer with state"""
    app = SilloApp()

    route = CounterConsumer.as_route("/ws/counter")
    app.add_ws_route(route)

    with test_client_factory(app) as client:
        with client.websocket_connect("/ws/counter") as websocket:
            websocket.send_text("First")
            assert websocket.receive_text() == "Message #1: First"

            websocket.send_text("Second")
            assert websocket.receive_text() == "Message #2: Second"

            websocket.send_text("Third")
            assert websocket.receive_text() == "Message #3: Third"


def test_stateful_consumer(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test consumer with connection lifecycle"""
    app = SilloApp()

    route = StatefulConsumer.as_route("/ws/stateful")
    app.add_ws_route(route)

    with test_client_factory(app) as client:
        with client.websocket_connect("/ws/stateful") as websocket:
            # Check connection message
            welcome = websocket.receive_json()
            assert welcome["status"] == "connected"
            assert welcome["message"] == "Welcome"

            # Test ping
            websocket.send_json({"action": "ping"})
            response = websocket.receive_json()
            assert response["response"] == "pong"

            # Test echo
            websocket.send_json({"action": "echo", "message": "Hello"})
            response = websocket.receive_json()
            assert response["response"] == "Hello"


def test_consumer_with_router(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test consumer mounted on router"""
    app = SilloApp()
    router = Router(prefix="/api")

    route = EchoConsumer.as_route("/echo")
    router.add_ws_route(route)

    app.mount_router(router)

    with test_client_factory(app) as client:
        with client.websocket_connect("/api/echo") as websocket:
            websocket.send_text("Router Consumer")
            data = websocket.receive_text()
            assert data == "Echo: Router Consumer"


def test_multiple_consumers(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test multiple consumers on different routes"""
    app = SilloApp()

    echo_route = EchoConsumer.as_route("/ws/echo")
    json_route = JsonConsumer.as_route("/ws/json")

    app.add_ws_route(echo_route)
    app.add_ws_route(json_route)

    with test_client_factory(app) as client:
        # Test echo consumer
        with client.websocket_connect("/ws/echo") as websocket:
            websocket.send_text("Echo test")
            assert websocket.receive_text() == "Echo: Echo test"

        # Test JSON consumer
        with client.websocket_connect("/ws/json") as websocket:
            websocket.send_json({"test": "data"})
            response = websocket.receive_json()
            assert response["type"] == "json"
            assert response["received"]["test"] == "data"


def test_consumer_with_path_parameters(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test consumer with path parameters"""
    app = SilloApp()

    class RoomConsumer(WebSocketConsumer):
        encoding = "json"

        async def on_connect(self, websocket: WebSocketContext) -> None:
            await websocket.accept()
            # Access path params from websocket scope
            room_id = websocket.path_params.get("room_id")
            await websocket.send_json({"room": room_id, "status": "joined"})

        async def on_receive(self, websocket: WebSocketContext, data: Any) -> None:
            room_id = websocket.path_params.get("room_id")
            await websocket.send_json({"room": room_id, "message": data})

    route = RoomConsumer.as_route("/ws/room/{room_id}")
    app.add_ws_route(route)

    with test_client_factory(app) as client:
        with client.websocket_connect("/ws/room/lobby") as websocket:
            join_msg = websocket.receive_json()
            assert join_msg["room"] == "lobby"
            assert join_msg["status"] == "joined"

            websocket.send_json({"text": "Hello room"})
            response = websocket.receive_json()
            assert response["room"] == "lobby"
            assert response["message"]["text"] == "Hello room"


def test_consumer_isolation(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test that consumer instances are isolated"""
    app = SilloApp()

    route = CounterConsumer.as_route("/ws/counter")
    app.add_ws_route(route)

    with test_client_factory(app) as client:
        # First connection
        with client.websocket_connect("/ws/counter") as websocket1:
            websocket1.send_text("First connection")
            assert websocket1.receive_text() == "Message #1: First connection"

        # Second connection should have its own counter
        with client.websocket_connect("/ws/counter") as websocket2:
            websocket2.send_text("Second connection")
            assert websocket2.receive_text() == "Message #1: Second connection"
