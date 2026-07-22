import traceback

from sillo.exceptions import WebSocketException
from sillo.logging import getLogger
from sillo.types import ASGIApp, Receive, Scope, Send
from sillo.websockets import WebSocket

logger = getLogger("sillo")


async def websocket_exception_handler(
    websocket: WebSocket, exc: WebSocketException
) -> None:
    """Websocket Exception Handler

    Args:
        websocket: [description]
        exc: [description]

    Returns:
        [description]

    Raises:
        [description]
    """
    error = traceback.format_exc()
    logger.error(f"WebSocket error: {error}")
    await websocket.close(code=exc.code, reason=str(exc))


class WebSocketErrorMiddleware:
    """Websocketerrormiddleware

    Returns:
        [description]

    Raises:
        [description]
    """

    def __init__(self, app: ASGIApp):
        """Init

        Args:
            app: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
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
        if scope["type"] == "websocket":
            websocket = WebSocket(scope, receive, send)
            try:
                await self.app(scope, receive, send)
            except WebSocketException as exc:
                await websocket_exception_handler(websocket, exc)
            except Exception:
                error = traceback.format_exc()
                logger.error(f"Unexpected error: {error}")
                await websocket.close(code=1011, reason="Internal Server Error")
        else:
            await self.app(scope, receive, send)
