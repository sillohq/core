"""
Removing channels from groups.

Every outcome is reported through the return value rather than raised — a
disconnect racing a cleanup is ordinary, not exceptional. The case guarded
here is removing a channel that is not in a non-empty group, which used to
fall through both branches and raise ``UnboundLocalError``.
"""

import asyncio

import pytest

from sillo.websockets import Channel, ChannelBox, WebSocketContext
from sillo.websockets.utils import ChannelRemoveStatusEnum


def _run(coro):
    return asyncio.run(coro)


class FakeWebSocket(WebSocketContext):
    def __init__(self):
        super().__init__(
            {"type": "websocket", "path": "/ws", "headers": [], "query_string": b""},
            self._receive_nothing,
            self._send_nothing,
        )

    async def _receive_nothing(self):
        return {"type": "websocket.connect"}

    async def _send_nothing(self, message):
        return None


@pytest.fixture(autouse=True)
def clean_channel_box():
    _run(ChannelBox.flush_groups())
    yield
    _run(ChannelBox.flush_groups())


def _channel():
    return Channel(FakeWebSocket(), payload_type="json", expires=None)


def test_removing_a_channel_from_a_shared_group():
    keep, drop = _channel(), _channel()
    _run(ChannelBox.add_channel_to_group(keep, "room"))
    _run(ChannelBox.add_channel_to_group(drop, "room"))

    status = _run(ChannelBox.remove_channel_from_group(drop, "room"))

    assert status == ChannelRemoveStatusEnum.CHANNEL_REMOVED
    assert "room" in _run(ChannelBox.show_groups())


def test_removing_a_channel_that_is_not_in_a_populated_group():
    """The regression: this raised UnboundLocalError instead of returning."""
    member, stranger = _channel(), _channel()
    _run(ChannelBox.add_channel_to_group(member, "room"))

    status = _run(ChannelBox.remove_channel_from_group(stranger, "room"))

    assert status == ChannelRemoveStatusEnum.CHANNEL_DOES_NOT_EXIST
    assert "room" in _run(ChannelBox.show_groups())


def test_removing_the_same_channel_twice_is_safe():
    """A double disconnect is a race, not an error."""
    keep, drop = _channel(), _channel()
    _run(ChannelBox.add_channel_to_group(keep, "room"))
    _run(ChannelBox.add_channel_to_group(drop, "room"))
    _run(ChannelBox.remove_channel_from_group(drop, "room"))

    status = _run(ChannelBox.remove_channel_from_group(drop, "room"))

    assert status == ChannelRemoveStatusEnum.CHANNEL_DOES_NOT_EXIST


def test_removing_the_last_channel_discards_the_group():
    channel = _channel()
    _run(ChannelBox.add_channel_to_group(channel, "room"))

    status = _run(ChannelBox.remove_channel_from_group(channel, "room"))

    assert status == ChannelRemoveStatusEnum.GROUP_REMOVED
    assert "room" not in _run(ChannelBox.show_groups())


def test_removing_from_a_group_that_never_existed():
    status = _run(ChannelBox.remove_channel_from_group(_channel(), "nonexistent"))

    assert status == ChannelRemoveStatusEnum.GROUP_DOES_NOT_EXIST


def test_removing_from_a_group_that_was_already_discarded():
    channel = _channel()
    _run(ChannelBox.add_channel_to_group(channel, "room"))
    _run(ChannelBox.remove_channel_from_group(channel, "room"))

    status = _run(ChannelBox.remove_channel_from_group(channel, "room"))

    assert status == ChannelRemoveStatusEnum.GROUP_DOES_NOT_EXIST


def test_removal_leaves_other_groups_alone():
    channel = _channel()
    _run(ChannelBox.add_channel_to_group(channel, "room-a"))
    _run(ChannelBox.add_channel_to_group(channel, "room-b"))

    _run(ChannelBox.remove_channel_from_group(channel, "room-a"))

    assert set(_run(ChannelBox.show_groups())) == {"room-b"}
