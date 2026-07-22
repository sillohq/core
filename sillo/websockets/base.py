import enum
import json
import typing
from typing import AsyncIterator, Iterable, Optional

from sillo.core.http.request import HTTPConnection

Scope = typing.MutableMapping[str, typing.Any]
Message = typing.MutableMapping[str, typing.Any]

Receive = typing.Callable[[], typing.Awaitable[Message]]
Send = typing.Callable[[Message], typing.Awaitable[None]]


class WebSocketState(enum.Enum):
    """Websocketstate

    Returns:
        [description]

    Raises:
        [description]
    """

    CONNECTING = 0
    CONNECTED = 1
    DISCONNECTED = 2
    RESPONSE = 3


class WebSocketDisconnect(Exception):
    """Websocketdisconnect

    Returns:
        [description]

    Raises:
        [description]
    """

    def __init__(self, code: int = 1000, reason: Optional[str] = None) -> None:
        """Init

        Args:
            code: [description]
            reason: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        self.code = code
        self.reason = reason or ""


class WebSocket(HTTPConnection):
    """Websocket

    Returns:
        [description]

    Raises:
        [description]
    """

    def __init__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Init

        Args:
            scope: [description]
            receive: [description]
            send: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        super().__init__(scope, receive)
        assert scope["type"] == "websocket"
        self._receive = receive
        self._send = send
        self.client_state = WebSocketState.CONNECTING
        self.application_state = WebSocketState.CONNECTING

    async def receive(self) -> Message:
        """
        Receive ASGI websocket messages, ensuring valid state transitions.
        """
        if self.client_state == WebSocketState.CONNECTING:
            message = await self._receive()
            message_type = message["type"]
            if message_type != "websocket.connect":
                raise RuntimeError(
                    f'Expected ASGI message "websocket.connect", but got {message_type!r}'
                )
            self.client_state = WebSocketState.CONNECTED
            return message
        elif self.client_state == WebSocketState.CONNECTED:
            message = await self._receive()
            message_type = message["type"]
            if message_type not in {"websocket.receive", "websocket.disconnect"}:
                raise RuntimeError(
                    f'Expected ASGI message "websocket.receive" or "websocket.disconnect", but got {message_type!r}'
                )
            if message_type == "websocket.disconnect":
                self.client_state = WebSocketState.DISCONNECTED
            return message
        else:
            raise RuntimeError(
                'Cannot call "receive" once a disconnect message has been received.'
            )

    async def send(self, message: Message) -> None:
        """
        Send ASGI websocket messages, ensuring valid state transitions.
        """
        if self.application_state == WebSocketState.CONNECTING:
            message_type = message["type"]
            if message_type not in {
                "websocket.accept",
                "websocket.close",
                "websocket.http.response.start",
            }:
                raise RuntimeError(
                    'Expected ASGI message "websocket.accept", "websocket.close" or "websocket.http.response.start", '
                    f"but got {message_type!r}"
                )
            if message_type == "websocket.close":
                self.application_state = WebSocketState.DISCONNECTED
            elif message_type == "websocket.http.response.start":
                self.application_state = WebSocketState.RESPONSE
            else:
                self.application_state = WebSocketState.CONNECTED
            await self._send(message)
        elif self.application_state == WebSocketState.CONNECTED:
            message_type = message["type"]
            if message_type not in {"websocket.send", "websocket.close"}:
                raise RuntimeError(
                    f'Expected ASGI message "websocket.send" or "websocket.close", but got {message_type!r}'
                )
            if message_type == "websocket.close":
                self.application_state = WebSocketState.DISCONNECTED
            try:
                await self._send(message)
            except OSError:
                self.application_state = WebSocketState.DISCONNECTED
                raise WebSocketDisconnect(code=1006)
        elif self.application_state == WebSocketState.RESPONSE:
            message_type = message["type"]
            if message_type != "websocket.http.response.body":
                raise RuntimeError(
                    f'Expected ASGI message "websocket.http.response.body", but got {message_type!r}'
                )
            if not message.get("more_body", False):
                self.application_state = WebSocketState.DISCONNECTED
            await self._send(message)
        else:
            raise RuntimeError('Cannot call "send" once a close message has been sent.')

    async def accept(
        self,
        subprotocol: Optional[str] = None,
        headers: Optional[Iterable[tuple[bytes, bytes]]] = None,
    ) -> None:
        """Accept

        Args:
            subprotocol: [description]
            headers: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        headers = headers or []

        if self.client_state == WebSocketState.CONNECTING:
            # If we haven't yet seen the 'connect' message, then wait for it first.
            await self.receive()
        await self.send(
            {"type": "websocket.accept", "subprotocol": subprotocol, "headers": headers}
        )

    def _raise_on_disconnect(self, message: Message) -> None:
        """Raise On Disconnect

        Args:
            message: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        if message["type"] == "websocket.disconnect":
            raise WebSocketDisconnect(message["code"], message.get("reason"))

    async def receive_text(self) -> str:
        """Receive Text

        Returns:
            [description]

        Raises:
            [description]
        """
        if self.application_state != WebSocketState.CONNECTED:
            raise RuntimeError(
                'WebSocket is not connected. Need to call "accept" first.'
            )
        message = await self.receive()
        self._raise_on_disconnect(message)
        return typing.cast(str, message["text"])

    async def receive_bytes(self) -> bytes:
        """Receive Bytes

        Returns:
            [description]

        Raises:
            [description]
        """
        if self.application_state != WebSocketState.CONNECTED:
            raise RuntimeError(
                'WebSocket is not connected. Need to call "accept" first.'
            )
        message = await self.receive()
        self._raise_on_disconnect(message)
        return typing.cast(bytes, message["bytes"])

    async def receive_json(self, mode: str = "text") -> typing.Any:
        """Receive Json

        Args:
            mode: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        if mode not in {"text", "binary"}:
            raise RuntimeError('The "mode" argument should be "text" or "binary".')
        if self.application_state != WebSocketState.CONNECTED:
            raise RuntimeError(
                'WebSocket is not connected. Need to call "accept" first.'
            )
        message = await self.receive()
        self._raise_on_disconnect(message)

        if mode == "text":
            text = message["text"]
        else:
            text = message["bytes"].decode("utf-8")

        return json.loads(text)

    async def iter_text(self) -> AsyncIterator[str]:
        """Iter Text

        Returns:
            [description]

        Raises:
            [description]
        """
        try:
            while True:
                yield await self.receive_text()
        except WebSocketDisconnect:
            pass

    async def iter_bytes(self) -> AsyncIterator[bytes]:
        """Iter Bytes

        Returns:
            [description]

        Raises:
            [description]
        """
        try:
            while True:
                yield await self.receive_bytes()
        except WebSocketDisconnect:
            pass

    async def iter_json(self) -> AsyncIterator[typing.Any]:
        """Iter Json

        Returns:
            [description]

        Raises:
            [description]
        """
        try:
            while True:
                yield await self.receive_json()
        except WebSocketDisconnect:
            pass

    async def send_text(self, data: str) -> None:
        """Send Text

        Args:
            data: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        await self.send({"type": "websocket.send", "text": data})

    async def send_bytes(self, data: bytes) -> None:
        """Send Bytes

        Args:
            data: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        await self.send({"type": "websocket.send", "bytes": data})

    async def send_json(self, data: typing.Any, mode: str = "text") -> None:
        """Send Json

        Args:
            data: [description]
            mode: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        if mode not in {"text", "binary"}:
            raise RuntimeError('The "mode" argument should be "text" or "binary".')
        text = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
        if mode == "text":
            await self.send({"type": "websocket.send", "text": text})
        else:
            await self.send({"type": "websocket.send", "bytes": text.encode("utf-8")})

    async def close(self, code: int = 1000, reason: Optional[str] = None) -> None:
        """Close

        Args:
            code: [description]
            reason: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        await self.send(
            {"type": "websocket.close", "code": code, "reason": reason or ""}
        )

    def is_connected(self) -> bool:
        """Is Connected

        Returns:
            [description]

        Raises:
            [description]
        """
        return (
            self.client_state == WebSocketState.CONNECTED
            and self.application_state == WebSocketState.CONNECTED
        )
