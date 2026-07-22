from __future__ import annotations

import inspect
from typing import Any, TypedDict

from typing_extensions import TypeGuard

from sillo.testclient._internal.types import ASGI2App, ASGI3App
from sillo.types import Receive, Scope, Send
from sillo.helpers.async_helpers import is_async_callable


def is_asgi3(app: ASGI2App | ASGI3App) -> TypeGuard[ASGI3App]:
    """Is Asgi3

        Args:
            app: [description]

        Returns:
            [description]

        Raises:
            [description]
    """
    if inspect.isclass(app):
        return hasattr(app, "__await__")
    return is_async_callable(app)


class WrapASGI2:
    """
    Provide an ASGI3 interface onto an ASGI2 app.
    """

    def __init__(self, app) -> None:
        """Init

            Args:
                app: [description]

            Returns:
                [description]

            Raises:
                [description]
        """
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Call

            Args:
                scope: [description]
                receive: [description]
                send: [description]

            Returns:
                [description]

            Raises:
                [description]
        """
        instance = self.app(scope)
        await instance(receive, send)


class AsyncBackend(TypedDict):
    """Asyncbackend

        Returns:
            [description]

        Raises:
            [description]
    """
    backend: str
    backend_options: dict[str, Any]
