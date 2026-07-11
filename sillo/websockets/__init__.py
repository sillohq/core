import typing

from .base import WebSocket, WebSocketDisconnect
from .channels import Channel, ChannelBox
from .consumers import WebSocketConsumer
from .history import BaseHistoryManager, InMemoryHistoryManager, NoOpHistoryManager

Scope = typing.MutableMapping[str, typing.Any]
Message = typing.MutableMapping[str, typing.Any]

Receive = typing.Callable[[], typing.Awaitable[Message]]
Send = typing.Callable[[Message], typing.Awaitable[None]]


__all__ = [
    "WebSocket",
    "Channel",
    "ChannelBox",
    "WebSocketConsumer",
    "WebSocketDisconnect",
    "BaseHistoryManager",
    "InMemoryHistoryManager",
    "NoOpHistoryManager",
]
