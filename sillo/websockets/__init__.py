"""WebSocket connections.

The socket itself and the errors it can raise. Rooms, presence, broadcast and
message history are not here — they live in `sillo-wire`, which installs
separately and imports as :mod:`sillo.wire`::

    pip install sillo-wire

Keeping them apart is a dependency direction rather than a size decision: the
room layer needs a socket, a socket needs nothing from the room layer, and
fan-out is the part that grows a backend.
"""

import typing

from . import status
from .base import WebSocketContext, WebSocketDisconnect

Scope = typing.MutableMapping[str, typing.Any]
Message = typing.MutableMapping[str, typing.Any]

Receive = typing.Callable[[], typing.Awaitable[Message]]
Send = typing.Callable[[Message], typing.Awaitable[None]]


__all__ = [
    "WebSocketContext",
    "WebSocketDisconnect",
    "status",
]
