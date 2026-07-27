"""
Channel groups, message history, and expiry.

``ChannelBox`` holds class-level state shared by the whole process, so every
test here starts from a flushed registry — otherwise a group left behind by
one test would be broadcast to by the next.
"""

import asyncio
import time
from typing import Callable

import pytest

from sillo import silloApp
from sillo.testclient import TestClient
from sillo.websockets import (
    Channel,
    ChannelBox,
    InMemoryHistoryManager,
    NoOpHistoryManager,
    WebSocket,
)
from sillo.websockets.utils import (
    ChannelAddStatusEnum,
    ChannelMessageDC,
    ChannelRemoveStatusEnum,
    GroupSendStatusEnum,
)


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def clean_channel_box():
    """The registry is class state; leaving it dirty leaks across tests."""
    original_manager = ChannelBox.HISTORY_MANAGER
    _run(ChannelBox.flush_groups())
    _run(ChannelBox.flush_history())
    yield
    _run(ChannelBox.flush_groups())
    _run(ChannelBox.flush_history())
    ChannelBox.HISTORY_MANAGER = original_manager


class FakeWebSocket(WebSocket):
    """A websocket that records instead of writing to a socket."""

    def __init__(self):
        super().__init__(
            {"type": "websocket", "path": "/ws", "headers": [], "query_string": b""},
            self._receive_nothing,
            self._send_nothing,
        )
        self.sent = []
        self.closed = False

    async def _receive_nothing(self):
        return {"type": "websocket.connect"}

    async def _send_nothing(self, message):
        return None

    async def send_json(self, data, mode="text"):
        self.sent.append(data)

    async def send_text(self, data):
        self.sent.append(data)

    async def send_bytes(self, data):
        self.sent.append(data)

    async def close(self, code=1000, reason=None):
        self.closed = True


def _channel(payload_type="json", expires=None):
    return Channel(FakeWebSocket(), payload_type=payload_type, expires=expires)


# ── Channel construction ─────────────────────────────────────────────────


def test_a_channel_gets_a_unique_id():
    assert _channel().uuid != _channel().uuid


def test_a_channel_records_its_creation_time():
    assert _channel().created <= time.time()


@pytest.mark.parametrize("payload_type", ["json", "text", "bytes"])
def test_the_supported_payload_types(payload_type):
    assert _channel(payload_type).payload_type == payload_type


def test_an_unknown_payload_type_is_rejected():
    with pytest.raises(AssertionError):
        _channel("morse")


def test_a_non_websocket_is_rejected():
    with pytest.raises(AssertionError):
        Channel("not-a-websocket", payload_type="json")


def test_a_non_integer_expiry_is_rejected():
    with pytest.raises(AssertionError):
        Channel(FakeWebSocket(), payload_type="json", expires="soon")


def test_the_repr_names_the_payload_type():
    assert "payload_type" in repr(_channel())


# ── expiry ───────────────────────────────────────────────────────────────


def test_a_channel_without_an_expiry_never_expires():
    assert _run(_channel().  _is_expired()) is False


def test_a_fresh_channel_has_not_expired():
    assert _run(_channel(expires=60)._is_expired()) is False


def test_a_stale_channel_has_expired():
    channel = _channel(expires=1)
    channel.created = time.time() - 120
    assert _run(channel._is_expired()) is True


# ── groups ───────────────────────────────────────────────────────────────


def test_adding_a_channel_creates_the_group():
    status = _run(ChannelBox.add_channel_to_group(_channel(), "room"))
    assert status == ChannelAddStatusEnum.CHANNEL_ADDED
    assert "room" in _run(ChannelBox.show_groups())


def test_adding_to_an_existing_group_reports_so():
    _run(ChannelBox.add_channel_to_group(_channel(), "room"))
    status = _run(ChannelBox.add_channel_to_group(_channel(), "room"))
    assert status == ChannelAddStatusEnum.CHANNEL_EXIST


def test_a_group_name_is_required():
    with pytest.raises(AssertionError):
        _run(ChannelBox.add_channel_to_group(_channel(), ""))


def test_groups_are_independent():
    _run(ChannelBox.add_channel_to_group(_channel(), "room-a"))
    _run(ChannelBox.add_channel_to_group(_channel(), "room-b"))
    assert set(_run(ChannelBox.show_groups())) == {"room-a", "room-b"}


def test_removing_the_last_channel_removes_the_group():
    channel = _channel()
    _run(ChannelBox.add_channel_to_group(channel, "room"))
    status = _run(ChannelBox.remove_channel_from_group(channel, "room"))
    assert status == ChannelRemoveStatusEnum.GROUP_REMOVED
    assert "room" not in _run(ChannelBox.show_groups())


def test_removing_one_of_several_keeps_the_group():
    first, second = _channel(), _channel()
    _run(ChannelBox.add_channel_to_group(first, "room"))
    _run(ChannelBox.add_channel_to_group(second, "room"))
    status = _run(ChannelBox.remove_channel_from_group(first, "room"))
    assert status == ChannelRemoveStatusEnum.CHANNEL_REMOVED
    assert "room" in _run(ChannelBox.show_groups())


def test_removing_from_an_unknown_group_is_survivable():
    _run(ChannelBox.remove_channel_from_group(_channel(), "no-such-room"))


def test_flushing_clears_every_group():
    _run(ChannelBox.add_channel_to_group(_channel(), "room"))
    _run(ChannelBox.flush_groups())
    assert _run(ChannelBox.show_groups()) == {}


def test_expired_channels_are_reaped_on_removal():
    """Removal is the cleanup point, so a socket that timed out silently does
    not stay in the broadcast list forever.

    Regression: the reaper iterated the very dict it deleted from, so any
    group containing an expired channel raised "dictionary changed size
    during iteration" on the next disconnect."""
    stale = _channel(expires=1)
    stale.created = time.time() - 120
    live = _channel()
    _run(ChannelBox.add_channel_to_group(stale, "room"))
    _run(ChannelBox.add_channel_to_group(live, "room"))

    other = _channel()
    _run(ChannelBox.add_channel_to_group(other, "other"))
    _run(ChannelBox.remove_channel_from_group(other, "other"))

    assert stale not in _run(ChannelBox.show_groups()).get("room", {})


# ── broadcasting ─────────────────────────────────────────────────────────


def test_a_broadcast_reaches_the_group():
    channel = _channel()
    _run(ChannelBox.add_channel_to_group(channel, "room"))
    _run(ChannelBox.group_send("room", {"hello": "world"}))
    assert channel.websocket.sent == [{"hello": "world"}]


def test_a_broadcast_reaches_every_member():
    first, second = _channel(), _channel()
    _run(ChannelBox.add_channel_to_group(first, "room"))
    _run(ChannelBox.add_channel_to_group(second, "room"))
    _run(ChannelBox.group_send("room", {"n": 1}))
    assert first.websocket.sent == second.websocket.sent == [{"n": 1}]


def test_a_broadcast_does_not_leak_between_groups():
    here, elsewhere = _channel(), _channel()
    _run(ChannelBox.add_channel_to_group(here, "room-a"))
    _run(ChannelBox.add_channel_to_group(elsewhere, "room-b"))
    _run(ChannelBox.group_send("room-a", {"n": 1}))
    assert elsewhere.websocket.sent == []


def test_broadcasting_to_an_empty_group_is_survivable():
    assert _run(ChannelBox.group_send("nobody-here", {"n": 1})) is not None


def test_a_group_name_is_required_to_broadcast():
    with pytest.raises(AssertionError):
        _run(ChannelBox.group_send("", {"n": 1}))


def test_a_text_channel_receives_text():
    channel = _channel("text")
    _run(ChannelBox.add_channel_to_group(channel, "room"))
    _run(ChannelBox.group_send("room", "plain message"))
    assert channel.websocket.sent == ["plain message"]


def test_a_bytes_channel_receives_bytes():
    channel = _channel("bytes")
    _run(ChannelBox.add_channel_to_group(channel, "room"))
    _run(ChannelBox.group_send("room", b"binary"))
    assert channel.websocket.sent == [b"binary"]


def test_a_broadcast_refreshes_the_channel_clock():
    channel = _channel(expires=60)
    channel.created = time.time() - 30
    _run(ChannelBox.add_channel_to_group(channel, "room"))
    _run(ChannelBox.group_send("room", {"n": 1}))
    assert time.time() - channel.created < 1


def test_a_send_status_is_reported():
    _run(ChannelBox.add_channel_to_group(_channel(), "room"))
    assert isinstance(_run(ChannelBox.group_send("room", {"n": 1})), GroupSendStatusEnum)


# ── history ──────────────────────────────────────────────────────────────


def test_history_is_off_by_default():
    _run(ChannelBox.add_channel_to_group(_channel(), "room"))
    _run(ChannelBox.group_send("room", {"n": 1}))
    assert _run(ChannelBox.show_history("room")) == []


def test_history_is_kept_when_asked_for():
    _run(ChannelBox.add_channel_to_group(_channel(), "room"))
    _run(ChannelBox.group_send("room", {"n": 1}, save_history=True))
    assert len(_run(ChannelBox.show_history("room"))) == 1


def test_history_accumulates():
    _run(ChannelBox.add_channel_to_group(_channel(), "room"))
    _run(ChannelBox.group_send("room", {"n": 1}, save_history=True))
    _run(ChannelBox.group_send("room", {"n": 2}, save_history=True))
    assert len(_run(ChannelBox.show_history("room"))) == 2


def test_history_without_a_group_returns_everything():
    _run(ChannelBox.add_channel_to_group(_channel(), "room-a"))
    _run(ChannelBox.add_channel_to_group(_channel(), "room-b"))
    _run(ChannelBox.group_send("room-a", {"n": 1}, save_history=True))
    _run(ChannelBox.group_send("room-b", {"n": 2}, save_history=True))
    assert set(_run(ChannelBox.show_history())) == {"room-a", "room-b"}


def test_history_for_an_unknown_group_is_empty():
    assert _run(ChannelBox.show_history("no-such-room")) == []


def test_flushing_one_group_leaves_the_others():
    _run(ChannelBox.add_channel_to_group(_channel(), "room-a"))
    _run(ChannelBox.add_channel_to_group(_channel(), "room-b"))
    _run(ChannelBox.group_send("room-a", {"n": 1}, save_history=True))
    _run(ChannelBox.group_send("room-b", {"n": 2}, save_history=True))
    _run(ChannelBox.flush_history("room-a"))
    assert _run(ChannelBox.show_history("room-a")) == []
    assert len(_run(ChannelBox.show_history("room-b"))) == 1


def test_flushing_everything():
    _run(ChannelBox.add_channel_to_group(_channel(), "room"))
    _run(ChannelBox.group_send("room", {"n": 1}, save_history=True))
    _run(ChannelBox.flush_history())
    assert _run(ChannelBox.show_history()) == {}


def test_flushing_an_unknown_group_is_survivable():
    _run(ChannelBox.flush_history("no-such-room"))


def test_history_is_dropped_once_it_outgrows_its_budget():
    """The cap is there so a chatty group cannot grow without bound."""
    manager = InMemoryHistoryManager(history_size=1)
    for i in range(5):
        _run(manager.save_message("room", ChannelMessageDC(payload={"n": i})))
    assert _run(manager.get_history("room")) == []


def test_a_custom_history_manager_is_used():
    ChannelBox.set_history_manager(NoOpHistoryManager())
    _run(ChannelBox.add_channel_to_group(_channel(), "room"))
    _run(ChannelBox.group_send("room", {"n": 1}, save_history=True))
    assert _run(ChannelBox.show_history("room")) in ([], {})


def test_the_noop_manager_stores_nothing():
    manager = NoOpHistoryManager()
    _run(manager.save_message("room", ChannelMessageDC(payload={"n": 1})))
    assert _run(manager.get_history("room")) in ([], {})


def test_the_noop_manager_can_be_flushed():
    manager = NoOpHistoryManager()
    _run(manager.flush_history("room"))
    _run(manager.flush_history())


def test_the_in_memory_manager_keeps_messages_per_group():
    manager = InMemoryHistoryManager()
    _run(manager.save_message("a", ChannelMessageDC(payload={"n": 1})))
    _run(manager.save_message("b", ChannelMessageDC(payload={"n": 2})))
    assert len(_run(manager.get_history("a"))) == 1
    assert len(_run(manager.get_history("b"))) == 1


def test_the_in_memory_manager_flushes_one_group():
    manager = InMemoryHistoryManager()
    _run(manager.save_message("a", ChannelMessageDC(payload={"n": 1})))
    _run(manager.flush_history("a"))
    assert _run(manager.get_history("a")) == []


# ── shutdown ─────────────────────────────────────────────────────────────


def test_closing_all_connections_closes_each_socket():
    first, second = _channel(), _channel()
    _run(ChannelBox.add_channel_to_group(first, "room-a"))
    _run(ChannelBox.add_channel_to_group(second, "room-b"))
    _run(ChannelBox.close_all_connections())
    assert first.websocket.closed is True
    assert second.websocket.closed is True


def test_closing_all_connections_clears_the_groups():
    _run(ChannelBox.add_channel_to_group(_channel(), "room"))
    _run(ChannelBox.close_all_connections())
    assert _run(ChannelBox.show_groups()) == {}


def test_a_socket_that_fails_to_close_does_not_stop_the_rest():
    """One dead connection must not prevent shutdown of the others."""
    broken, healthy = _channel(), _channel()

    async def explode(code=1000, reason=None):
        raise OSError("socket already gone")

    broken.websocket.close = explode
    _run(ChannelBox.add_channel_to_group(broken, "room"))
    _run(ChannelBox.add_channel_to_group(healthy, "room"))
    _run(ChannelBox.close_all_connections())
    assert healthy.websocket.closed is True


def test_closing_with_no_connections_is_survivable():
    _run(ChannelBox.close_all_connections())
