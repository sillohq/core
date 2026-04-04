from __future__ import annotations

import contextlib
import json
import queue
import typing
from concurrent.futures import Future
from functools import cached_property

import anyio
import anyio.from_thread  # noqa
from anyio.abc import TaskGroup

from nexios.testclient._internal.types import ASGI3App
from nexios.types import Message, Scope
from nexios.websockets import WebSocketDisconnect

try:
    import httpx
except ModuleNotFoundError:  # pragma: no cover
    raise RuntimeError(
        "The nexios.testclient module requires the httpx package to be installed.\n"
        "You can install this with:\n"
        "    $ pip install httpx\n"
    ) from None


class WebSocketDenialResponse(
    httpx.Response,
    WebSocketDisconnect,
):
    """
    A special case of `WebSocketDisconnect`, raised in the `TestClient` if the
    `WebSocket` is closed before being accepted with a `send_denial_response()`.
    """

    ...


class WebSocketTestSession:
    """
    Represents a test session for a WebSocket connection.
    """

    def __init__(
        self,
        app: ASGI3App,
        scope: Scope,
        portal_factory,
    ) -> None:
        """
        Initialize the WebSocketTestSession.

        Args:
            app (ASGI3App): The ASGI3 application.
            scope (Scope): The ASGI scope.
            portal_factory (PortalFactoryType): The portal factory.
        """
        self.app = app
        self.scope = scope
        self.accepted_subprotocol = None
        self.portal_factory = portal_factory
        self._receive_queue: queue.Queue[Message] = queue.Queue()
        self._send_queue: queue.Queue[Message | BaseException] = queue.Queue()
        self.extra_headers = None

    def __enter__(self) -> WebSocketTestSession:
        """
        Enter the WebSocketTestSession context.

        Returns:
            WebSocketTestSession: The WebSocketTestSession object.
        """
        self.exit_stack = contextlib.ExitStack()
        self.portal = self.exit_stack.enter_context(self.portal_factory())

        try:
            _: Future[None] = self.portal.start_task_soon(self._run)
            self.send({"type": "websocket.connect"})
            message = self.receive()
            self._raise_on_close(message)
        except Exception:
            self.exit_stack.close()
            raise
        self.accepted_subprotocol = message.get("subprotocol", None)
        self.extra_headers = message.get("headers", None)
        return self

    @cached_property
    def should_close(self) -> anyio.Event:
        """
        Get the should_close event.

        Returns:
            anyio.Event: The should_close event.
        """
        return anyio.Event()

    async def _notify_close(self) -> None:
        """
        Notify the WebSocketTestSession to close.
        """
        self.should_close.set()

    def __exit__(self, *args: typing.Any) -> None:
        """
        Exit the WebSocketTestSession context.
        """
        try:
            self.close(1000)
        finally:
            self.portal.start_task_soon(self._notify_close)
            self.exit_stack.close()
        while not self._send_queue.empty():
            message = self._send_queue.get()
            if isinstance(message, BaseException):
                raise message

    async def _run(self) -> None:
        """
        Run the WebSocket session in a sub-thread.
        """

        async def run_app(tg: TaskGroup) -> None:
            try:
                await self.app(self.scope, self._asgi_receive, self._asgi_send)
            except anyio.get_cancelled_exc_class():
                ...
            except BaseException as exc:
                self._send_queue.put(exc)
                raise
            finally:
                tg.cancel_scope.cancel()

        async with anyio.create_task_group() as tg:
            tg.start_soon(run_app, tg)
            await self.should_close.wait()
            tg.cancel_scope.cancel()

    async def _asgi_receive(self) -> Message:
        """
        Receive a message from the WebSocketTestSession.

        Returns:
            Message: The received message.
        """
        while self._receive_queue.empty():
            await anyio.sleep(0)
        return self._receive_queue.get()

    async def _asgi_send(self, message: Message) -> None:
        """
        Send a message to the WebSocketTestSession.

        Args:
            message (Message): The message to send.
        """
        self._send_queue.put(message)

    def _raise_on_close(self, message: Message) -> None:
        """
        Raise a WebSocketDisconnect or WebSocketDenialResponse if the WebSocket is closed.

        Args:
            message (Message): The received message.
        """
        if message["type"] == "websocket.close":
            raise WebSocketDisconnect(
                code=message.get("code", 1000), reason=message.get("reason", "")
            )
        elif message["type"] == "websocket.http.response.start":
            status_code: int = message["status"]
            headers: list[tuple[bytes, bytes]] = message["headers"]
            body: list[bytes] = []
            while True:
                message = self.receive()
                assert message["type"] == "websocket.http.response.body"
                body.append(message["body"])
                if not message.get("more_body", False):
                    break
            raise WebSocketDenialResponse(
                status_code=status_code,
                headers=headers,
                content=b"".join(body),
            )

    def send(self, message: Message) -> None:
        """
        Send a message to the WebSocketTestSession.

        Args:
            message (Message): The message to send.
        """
        self._receive_queue.put(message)

    def send_text(self, data: str) -> None:
        """
        Send text data to the WebSocketTestSession.

        Args:
            data (str): The text data to send.
        """
        self.send({"type": "websocket.receive", "text": data})

    def send_bytes(self, data: bytes) -> None:
        """
        Send binary data to the WebSocketTestSession.

        Args:
            data (bytes): The binary data to send.
        """
        self.send({"type": "websocket.receive", "bytes": data})

    def send_json(
        self, data: typing.Any, mode: typing.Literal["text", "binary"] = "text"
    ) -> None:
        """
        Send JSON data to the WebSocketTestSession.

        Args:
            data (typing.Any): The JSON data to send.
            mode (typing.Literal["text", "binary"], optional): The mode of sending. Defaults to "text".
        """
        text = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
        if mode == "text":
            self.send({"type": "websocket.receive", "text": text})
        else:
            self.send({"type": "websocket.receive", "bytes": text.encode("utf-8")})

    def close(self, code: int = 1000, reason: str | None = None) -> None:
        """
        Close the WebSocketTestSession.

        Args:
            code (int, optional): The close code. Defaults to 1000.
            reason (str | None, optional): The close reason. Defaults to None.
        """
        self.send({"type": "websocket.disconnect", "code": code, "reason": reason})

    def receive(self) -> Message:
        """
        Receive a message from the WebSocketTestSession.

        Returns:
            Message: The received message.
        """
        message = self._send_queue.get()
        if isinstance(message, BaseException):
            raise message
        return message

    def receive_text(self) -> str:
        """
        Receive text data from the WebSocketTestSession.

        Returns:
            str: The received text data.
        """
        message = self.receive()
        self._raise_on_close(message)
        return typing.cast(str, message["text"])

    def receive_bytes(self) -> bytes:
        """
        Receive binary data from the WebSocketTestSession.

        Returns:
            bytes: The received binary data.
        """
        message = self.receive()
        self._raise_on_close(message)
        return typing.cast(bytes, message["bytes"])

    def receive_json(
        self, mode: typing.Literal["text", "binary"] = "text"
    ) -> typing.Any:
        """
        Receive JSON data from the WebSocketTestSession.

        Args:
            mode (typing.Literal["text", "binary"], optional): The mode of receiving. Defaults to "text".

        Returns:
            typing.Any: The received JSON data.
        """
        message = self.receive()
        self._raise_on_close(message)
        if mode == "text":
            text = message["text"]
        else:
            text = message["bytes"].decode("utf-8")
        return json.loads(text)
