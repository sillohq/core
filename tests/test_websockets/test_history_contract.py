"""
The ``BaseHistoryManager`` contract.

The abstract base defines the three methods every backend must provide;
these check that the contract is enforced and that a hand-written manager
plugs into ``ChannelBox`` in place of the built-in one.
"""

import asyncio

import pytest

from sillo.websockets import (
    BaseHistoryManager,
    ChannelBox,
    InMemoryHistoryManager,
    NoOpHistoryManager,
)
from sillo.websockets.utils import ChannelMessageDC


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def restore_manager():
    original = ChannelBox.HISTORY_MANAGER
    yield
    ChannelBox.HISTORY_MANAGER = original
    _run(ChannelBox.flush_groups())
    _run(ChannelBox.flush_history())


def test_the_base_manager_cannot_be_instantiated():
    with pytest.raises(TypeError):
        BaseHistoryManager()


def test_a_partial_implementation_is_rejected():
    """All three methods are abstract; implementing two is not enough."""

    class Partial(BaseHistoryManager):
        async def save_message(self, group_name, message):
            return None

    with pytest.raises(TypeError):
        Partial()


def test_a_complete_implementation_can_be_instantiated():
    class Complete(BaseHistoryManager):
        async def save_message(self, group_name, message):
            return None

        async def get_history(self, group_name=None):
            return []

        async def flush_history(self, group_name=None):
            return None

    assert isinstance(Complete(), BaseHistoryManager)


def test_the_built_in_managers_satisfy_the_contract():
    assert isinstance(InMemoryHistoryManager(), BaseHistoryManager)
    assert isinstance(NoOpHistoryManager(), BaseHistoryManager)


def test_a_custom_manager_receives_the_messages():
    """Swapping in a durable backend is the point of the abstraction."""
    saved = []

    class Recording(BaseHistoryManager):
        async def save_message(self, group_name, message):
            saved.append((group_name, message))

        async def get_history(self, group_name=None):
            return [m for g, m in saved if group_name in (None, g)]

        async def flush_history(self, group_name=None):
            saved.clear()

    ChannelBox.set_history_manager(Recording())
    _run(ChannelBox.group_send("room", {"n": 1}, save_history=True))

    assert len(saved) == 1
    assert saved[0][0] == "room"


def test_a_custom_manager_is_asked_for_history():
    class Recording(BaseHistoryManager):
        async def save_message(self, group_name, message):
            return None

        async def get_history(self, group_name=None):
            return ["from-the-custom-manager"]

        async def flush_history(self, group_name=None):
            return None

    ChannelBox.set_history_manager(Recording())
    assert _run(ChannelBox.show_history("room")) == ["from-the-custom-manager"]


def test_a_custom_manager_is_asked_to_flush():
    flushed = []

    class Recording(BaseHistoryManager):
        async def save_message(self, group_name, message):
            return None

        async def get_history(self, group_name=None):
            return []

        async def flush_history(self, group_name=None):
            flushed.append(group_name)

    ChannelBox.set_history_manager(Recording())
    _run(ChannelBox.flush_history("room"))
    assert flushed == ["room"]


def test_the_message_record_carries_the_payload():
    message = ChannelMessageDC(payload={"n": 1})
    assert message.payload == {"n": 1}


def test_each_message_record_is_identifiable():
    """Regression: ``uuid`` and ``created`` were plain defaults, evaluated once
    when the module was imported — so every message in history shared one id
    and one timestamp."""
    assert ChannelMessageDC(payload={}).uuid != ChannelMessageDC(payload={}).uuid


def test_message_records_are_timestamped_independently():
    import time

    first = ChannelMessageDC(payload={})
    time.sleep(0.01)
    second = ChannelMessageDC(payload={})
    assert second.created > first.created


def test_a_message_record_is_timestamped():
    assert ChannelMessageDC(payload={}).created
