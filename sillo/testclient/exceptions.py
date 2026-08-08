from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ._internal.websockets import WebSocketTestSession


class UpgradeException(Exception):
    """Upgradeexception"""

    def __init__(self, session: WebSocketTestSession) -> None:
        """Init"""
        self.session = session


class ASGISpecViolation(Exception): ...
