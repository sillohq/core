from __future__ import annotations

import inspect
from typing import Any, TypedDict, TypeGuard

from sillo.core.helpers.async_helpers import is_async_callable
from sillo.testclient._internal.types import ASGI2App, ASGI3App
from sillo.types import Receive, Scope, Send


def is_asgi3(app: ASGI2App | ASGI3App) -> TypeGuard[ASGI3App]:
    """Is Asgi3"""
    if inspect.isclass(app):
        return hasattr(app, "__await__")
    return is_async_callable(app)


class WrapASGI2:
    """
    Provide an ASGI3 interface onto an ASGI2 app.
    """

    def __init__(self, app) -> None:
        """Init"""
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Call"""
        instance = self.app(scope)
        await instance(receive, send)


class AsyncBackend(TypedDict):
    """Asyncbackend"""

    backend: str
    backend_options: dict[str, Any]
