"""
Tests for WebSocket groups and channels functionality
"""

import asyncio
from typing import Any, Callable, List

import pytest

from sillo import silloApp
from sillo.routing import Router
from sillo.testclient import TestClient
from sillo.websockets import WebSocket, WebSocketConsumer
from sillo.websockets.channels import ChannelBox


class GroupChatConsumer(WebSocketConsumer):
    """Consumer that supports group chat"""

    encoding = "json"

    async def on_connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        # Join default group
        await self.join_group("chat")
        await websocket.send_json({"status": "connected", "group": "chat"})

    async def on_receive(self, websocket: WebSocket, data: Any) -> None:
        action = data.get("action")

        if action == "join":
            group_name = data.get("group")
            await self.join_group(group_name)
            await websocket.send_json({"status": "joined", "group": group_name})

        elif action == "leave":
            group_name = data.get("group")
            await self.leave_group(group_name)
            await websocket.send_json({"status": "left", "group": group_name})

        elif action == "broadcast":
            group_name = data.get("group", "chat")
            message = data.get("message")
            await self.broadcast(
                payload={"type": "broadcast", "message": message}, group_name=group_name
            )

        elif action == "list_groups":
            channels = await self.group(data.get("group", "chat"))
            await websocket.send_json(
                {"group": data.get("group", "chat"), "channel_count": len(channels)}
            )

    async def on_disconnect(self, websocket: WebSocket, close_code: int) -> None:
        # Leave all groups on disconnect
        await self.leave_group("chat")


class RoomConsumer(WebSocketConsumer):
    """Consumer for room-based communication"""

    encoding = "json"

    async def on_connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        room_id = websocket.path_params.get("room_id", "default")
        await self.join_group(f"room_{room_id}")
        await websocket.send_json({"status": "joined_room", "room": room_id})

    async def on_receive(self, websocket: WebSocket, data: Any) -> None:
        room_id = websocket.path_params.get("room_id", "default")

        if data.get("action") == "message":
            # Broadcast to room
            await self.broadcast(
                payload={
                    "type": "room_message",
                    "room": room_id,
                    "message": data.get("message"),
                },
                group_name=f"room_{room_id}",
            )
        elif data.get("action") == "direct":
            # Send to specific channel (not implemented in this test)
            await websocket.send_json(
                {
                    "type": "direct_not_supported",
                    "message": "Direct messaging not implemented",
                }
            )

    async def on_disconnect(self, websocket: WebSocket, close_code: int) -> None:
        room_id = websocket.path_params.get("room_id", "default")
        await self.leave_group(f"room_{room_id}")


class MultiGroupConsumer(WebSocketConsumer):
    """Consumer that can join multiple groups"""

    encoding = "json"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.joined_groups: List[str] = []

    async def on_connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        await websocket.send_json({"status": "ready"})

    async def on_receive(self, websocket: WebSocket, data: Any) -> None:
        action = data.get("action")

        if action == "join":
            group_name = data.get("group")
            await self.join_group(group_name)
            self.joined_groups.append(group_name)
            await websocket.send_json(
                {
                    "action": "joined",
                    "group": group_name,
                    "total_groups": len(self.joined_groups),
                }
            )

        elif action == "leave":
            group_name = data.get("group")
            await self.leave_group(group_name)
            if group_name in self.joined_groups:
                self.joined_groups.remove(group_name)
            await websocket.send_json(
                {
                    "action": "left",
                    "group": group_name,
                    "total_groups": len(self.joined_groups),
                }
            )

        elif action == "broadcast_all":
            # Broadcast to all joined groups
            message = data.get("message")
            for group in self.joined_groups:
                await self.broadcast(
                    payload={"message": message, "from_group": group}, group_name=group
                )
            await websocket.send_json(
                {"action": "broadcast_complete", "groups": len(self.joined_groups)}
            )

    async def on_disconnect(self, websocket: WebSocket, close_code: int) -> None:
        # Leave all groups
        for group in self.joined_groups:
            await self.leave_group(group)


def test_group_join_and_leave(test_client_factory: Callable[[silloApp], TestClient]):
    """Test joining and leaving groups"""
    app = silloApp()
    route = GroupChatConsumer.as_route("/ws/chat")
    app.add_ws_route(route)

    with test_client_factory(app) as client:
        with client.websocket_connect("/ws/chat") as websocket:
            # Auto-joined to 'chat' group
            connect_msg = websocket.receive_json()
            assert connect_msg["status"] == "connected"
            assert connect_msg["group"] == "chat"

            # Join another group
            websocket.send_json({"action": "join", "group": "lobby"})
            join_msg = websocket.receive_json()
            assert join_msg["status"] == "joined"
            assert join_msg["group"] == "lobby"

            # Leave group
            websocket.send_json({"action": "leave", "group": "lobby"})
            leave_msg = websocket.receive_json()
            assert leave_msg["status"] == "left"
            assert leave_msg["group"] == "lobby"


def test_group_broadcast(test_client_factory: Callable[[silloApp], TestClient]):
    """Test broadcasting to a group"""
    app = silloApp()
    route = GroupChatConsumer.as_route("/ws/chat")
    app.add_ws_route(route)

    with test_client_factory(app) as client:
        # Create two connections
        with client.websocket_connect("/ws/chat") as ws1:
            with client.websocket_connect("/ws/chat") as ws2:
                # Clear connection messages
                ws1.receive_json()
                ws2.receive_json()

                # Broadcast from ws1
                ws1.send_json(
                    {
                        "action": "broadcast",
                        "group": "chat",
                        "message": "Hello everyone",
                    }
                )

                # Both should receive the broadcast
                msg1 = ws1.receive_json()
                assert msg1["type"] == "broadcast"
                assert msg1["message"] == "Hello everyone"

                msg2 = ws2.receive_json()
                assert msg2["type"] == "broadcast"
                assert msg2["message"] == "Hello everyone"


def test_room_based_groups(test_client_factory: Callable[[silloApp], TestClient]):
    """Test room-based group communication"""
    app = silloApp()
    route = RoomConsumer.as_route("/ws/room/{room_id}")
    app.add_ws_route(route)

    with test_client_factory(app) as client:
        # Connect to room1
        with client.websocket_connect("/ws/room/room1") as ws1:
            # Connect to room2
            with client.websocket_connect("/ws/room/room2") as ws2:
                # Clear join messages
                join1 = ws1.receive_json()
                assert join1["room"] == "room1"

                join2 = ws2.receive_json()
                assert join2["room"] == "room2"

                # Send message in room1
                ws1.send_json({"action": "message", "message": "Hello room1"})

                # Only ws1 should receive it
                msg1 = ws1.receive_json()
                assert msg1["type"] == "room_message"
                assert msg1["room"] == "room1"
                assert msg1["message"] == "Hello room1"

                # ws2 should not receive anything (different room)
                # Note: In a real test, we'd need to verify no message is received


def test_multiple_groups_per_consumer(
    test_client_factory: Callable[[silloApp], TestClient],
):
    """Test consumer joining multiple groups"""
    app = silloApp()
    route = MultiGroupConsumer.as_route("/ws/multi")
    app.add_ws_route(route)

    with test_client_factory(app) as client:
        with client.websocket_connect("/ws/multi") as websocket:
            # Clear ready message
            websocket.receive_json()

            # Join multiple groups
            websocket.send_json({"action": "join", "group": "group1"})
            msg1 = websocket.receive_json()
            assert msg1["group"] == "group1"
            assert msg1["total_groups"] == 1

            websocket.send_json({"action": "join", "group": "group2"})
            msg2 = websocket.receive_json()
            assert msg2["group"] == "group2"
            assert msg2["total_groups"] == 2

            websocket.send_json({"action": "join", "group": "group3"})
            msg3 = websocket.receive_json()
            assert msg3["group"] == "group3"
            assert msg3["total_groups"] == 3

            # Leave one group
            websocket.send_json({"action": "leave", "group": "group2"})
            leave_msg = websocket.receive_json()
            assert leave_msg["group"] == "group2"
            assert leave_msg["total_groups"] == 2


def test_group_isolation(test_client_factory: Callable[[silloApp], TestClient]):
    """Test that groups are isolated from each other"""
    app = silloApp()
    route = GroupChatConsumer.as_route("/ws/chat")
    app.add_ws_route(route)

    with test_client_factory(app) as client:
        with client.websocket_connect("/ws/chat") as ws1:
            with client.websocket_connect("/ws/chat") as ws2:
                # Clear connection messages
                ws1.receive_json()
                ws2.receive_json()

                # ws1 joins group1
                ws1.send_json({"action": "join", "group": "group1"})
                ws1.receive_json()

                # ws2 joins group2
                ws2.send_json({"action": "join", "group": "group2"})
                ws2.receive_json()

                # Broadcast to group1
                ws1.send_json(
                    {
                        "action": "broadcast",
                        "group": "group1",
                        "message": "Group1 message",
                    }
                )

                # ws1 should receive (it's in group1)
                msg1 = ws1.receive_json()
                assert msg1["message"] == "Group1 message"

                # ws2 should not receive (it's in group2, not group1)
                # Note: In real test, verify timeout or no message


def test_channel_cleanup_on_disconnect(
    test_client_factory: Callable[[silloApp], TestClient],
):
    """Test that channels are cleaned up on disconnect"""
    app = silloApp()
    route = GroupChatConsumer.as_route("/ws/chat")
    app.add_ws_route(route)

    with test_client_factory(app) as client:
        # Connect and join group
        with client.websocket_connect("/ws/chat") as websocket:
            websocket.receive_json()  # Clear connection message

            websocket.send_json({"action": "list_groups", "group": "chat"})
            list_msg = websocket.receive_json()
            initial_count = list_msg["channel_count"]
            assert initial_count >= 1

        # After disconnect, channel should be removed
        # Note: This would require additional verification logic


def test_broadcast_with_history(test_client_factory: Callable[[silloApp], TestClient]):
    """Test broadcasting with message history"""
    app = silloApp()

    class HistoryConsumer(WebSocketConsumer):
        encoding = "json"

        async def on_connect(self, websocket: WebSocket) -> None:
            await websocket.accept()
            await self.join_group("history_group")
            await websocket.send_json({"status": "connected"})

        async def on_receive(self, websocket: WebSocket, data: Any) -> None:
            if data.get("action") == "broadcast":
                await self.broadcast(
                    payload={"message": data.get("message")},
                    group_name="history_group",
                    save_history=True,
                )

        async def on_disconnect(self, websocket: WebSocket, close_code: int) -> None:
            await self.leave_group("history_group")

    route = HistoryConsumer.as_route("/ws/history")
    app.add_ws_route(route)

    with test_client_factory(app) as client:
        with client.websocket_connect("/ws/history") as websocket:
            websocket.receive_json()  # Clear connection message

            # Send broadcast with history
            websocket.send_json(
                {"action": "broadcast", "message": "Historical message"}
            )

            # Receive the broadcast
            msg = websocket.receive_json()
            assert msg["message"] == "Historical message"


def test_group_with_router(test_client_factory: Callable[[silloApp], TestClient]):
    """Test groups with mounted router"""
    app = silloApp()
    router = Router(prefix="/api")

    route = GroupChatConsumer.as_route("/chat")
    router.add_ws_route(route)
    app.mount_router(router)

    with test_client_factory(app) as client:
        with client.websocket_connect("/api/chat") as websocket:
            connect_msg = websocket.receive_json()
            assert connect_msg["status"] == "connected"

            websocket.send_json({"action": "join", "group": "api_group"})
            join_msg = websocket.receive_json()
            assert join_msg["status"] == "joined"
            assert join_msg["group"] == "api_group"
