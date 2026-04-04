from __future__ import annotations

import typing
from collections.abc import Callable

import anyio

from nexios.types import Receive, Scope, Send

# Define type aliases
ASGIInstance = Callable[[Receive, Send], typing.Awaitable[None]]
ASGI2App = Callable[[Scope], ASGIInstance]
ASGI3App = Callable[[Scope, Receive, Send], typing.Awaitable[None]]
RequestData = typing.Mapping[str, str | typing.Iterable[str]]
PortalFactoryType = typing.Callable[[], typing.ContextManager[anyio.abc.BlockingPortal]]
