import traceback

from sillo.exceptions import WebSocketException
from sillo.logging import getLogger
from sillo.types import ASGIApp, Receive, Scope, Send
from sillo.websockets import WebSocket

logger = getLogger("sillo")


async def websocket_exception_handler(
    websocket: WebSocket, exc: WebSocketException
) -> None:
    error = traceback.format_exc()
    logger.error(f"WebSocket error: {error}")
    await websocket.close(code=exc.code, reason=str(exc))


class WebSocketErrorMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
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
