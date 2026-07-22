from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ._internal.websockets import WebSocketTestSession


class UpgradeException(Exception):
    """Upgradeexception

    Returns:
        [description]

    Raises:
        [description]
    """

    def __init__(self, session: WebSocketTestSession) -> None:
        """Init

        Args:
            session: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        self.session = session


class ASGISpecViolation(Exception): ...
