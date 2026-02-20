import io
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import unquote

import anyio
import httpx

ASGIScope = Dict[str, Any]
Message = Dict[str, Any]
HeaderList = List[Tuple[bytes, bytes]]


class WebSocketState(Enum):
    CONNECTING = 0
    CONNECTED = 1
    DISCONNECTED = 2


class WebSocketDisconnect(Exception):
    def __init__(self, code: int = 1000, reason: Optional[str] = None):
        self.code = code
        self.reason = reason
        super().__init__(
            f"WebSocket disconnected with code {code}: {reason or 'No reason provided'}"
        )


class WebSocketConnection:
    def __init__(
        self,
        app: Any,
        scope: ASGIScope,
        raise_app_exceptions: bool = True,
        timeout: float = 5.0,
    ):
        self.app = app
        self.scope = scope
        self.raise_app_exceptions = raise_app_exceptions
        self.timeout = timeout

        # Connection state
        self.state = WebSocketState.CONNECTING
        self.close_code: Optional[int] = None
        self.close_reason: Optional[str] = None
        self.subprotocol: Optional[str] = None

        # Communication channels
        self.receive_channel, self.send_channel = anyio.create_memory_object_stream(
            max_buffer_size=float("inf")
        )
        self.app_channel, self.client_channel = anyio.create_memory_object_stream(
            max_buffer_size=float("inf")
        )

        # Control events
        self.connection_event = anyio.Event()
        self.disconnection_event = anyio.Event()

        # Background task group
        self.task_group = None

    async def run_app(self) -> None:
        """Run the ASGI application to handle the WebSocket connection."""
        try:
            scope = self.scope
            app = self.app  # Store app reference

            # Start the ASGI application
            try:
                await app(scope, self._asgi_receive, self._asgi_send)
            except Exception as exc:
                if self.raise_app_exceptions:
                    await self._handle_disconnect(1011, str(exc))
                    raise
                await self._handle_disconnect(1011, "Internal error")
            else:
                # If we get here, the app completed normally
                if self.state != WebSocketState.DISCONNECTED:
                    await self._handle_disconnect(1000, "Normal closure")
        finally:
            # Ensure we're disconnected
            if self.state != WebSocketState.DISCONNECTED:
                await self._handle_disconnect(1006, "Abnormal closure")

    async def _asgi_receive(self) -> Message:
        """ASGI receive function for the application."""
        if self.state == WebSocketState.CONNECTING:
            message = {"type": "websocket.connect"}
            self.state = WebSocketState.CONNECTED
            return message

        if self.state == WebSocketState.DISCONNECTED:
            return {"type": "websocket.disconnect", "code": self.close_code}

        try:
            async with anyio.move_on_after(self.timeout) as scope:
                async with self.app_channel as receiver:
                    message = await receiver.receive()
                if scope.cancel_called:
                    await self._handle_disconnect(1002, "Receive timeout")
                    return {"type": "websocket.disconnect", "code": 1002}
                return message
        except Exception:
            await self._handle_disconnect(1006, "Connection lost")
            return {"type": "websocket.disconnect", "code": 1006}

    async def _asgi_send(self, message: Message) -> None:
        """ASGI send function for the application."""
        message_type = message["type"]

        try:
            if message_type == "websocket.accept":
                self.subprotocol = message.get("subprotocol")
                async with self.client_channel as sender:
                    await sender.send({"type": "accept"})
                self.connection_event.set()

            elif message_type == "websocket.send":
                async with self.client_channel as sender:
                    await sender.send(
                        {
                            "type": "message",
                            "data": message.get("text") or message.get("bytes"),
                            "is_text": "text" in message,
                        }
                    )

            elif message_type == "websocket.close":
                code = message.get("code", 1000)
                reason = message.get("reason")

                # First notify the client
                async with self.client_channel as sender:
                    await sender.send({"type": "close", "code": code, "reason": reason})

                # Then handle the disconnect
                await self._handle_disconnect(code, reason)
        except Exception as e:
            # If sending fails, ensure we disconnect
            await self._handle_disconnect(1006, str(e))
            raise

    async def _handle_disconnect(self, code: int, reason: Optional[str] = None) -> None:
        """Handle WebSocket disconnection."""
        if self.state == WebSocketState.DISCONNECTED:
            return

        self.state = WebSocketState.DISCONNECTED
        self.close_code = code
        self.close_reason = reason

        # Set the disconnection event first
        self.disconnection_event.set()

        # Then try to clean up the task group
        if self.task_group and self.task_group.cancel_scope:
            await self.task_group.cancel_scope.cancel()

    async def connect(self) -> None:
        """Establish the WebSocket connection."""
        if self.state != WebSocketState.CONNECTING:
            raise RuntimeError("WebSocket is already connected or disconnected")

        async with anyio.create_task_group() as tg:
            self.task_group = tg
            await tg.start(self.run_app)

            timeout_error = False
            try:
                async with anyio.move_on_after(self.timeout) as scope:
                    await self.connection_event.wait()
                    timeout_error = scope.cancel_called

                if timeout_error:
                    await self._handle_disconnect(1006, "Connection timeout")
                    raise RuntimeError("WebSocket connection timed out")

            except Exception as e:
                await self._handle_disconnect(1006, str(e))
                raise

    async def send(self, data: Union[str, bytes]) -> None:
        """Send data through the WebSocket."""
        if self.state != WebSocketState.CONNECTED:
            raise WebSocketDisconnect(
                self.close_code or 1006,
                self.close_reason or "Cannot send on closed connection",
            )

        message = {
            "type": "websocket.receive",
            "text": data if isinstance(data, str) else None,
            "bytes": data if isinstance(data, bytes) else None,
        }

        try:
            timeout_error = False
            async with anyio.move_on_after(self.timeout) as scope:
                async with self.receive_channel as sender:
                    await sender.send(message)
                timeout_error = scope.cancel_called

            if timeout_error:
                await self._handle_disconnect(1002, "Protocol error")
                raise WebSocketDisconnect(1002, "Send timeout")
        except Exception:
            await self._handle_disconnect(1002, "Protocol error")
            raise WebSocketDisconnect(1002, "Send error")

    async def receive(self) -> Union[str, bytes]:
        """Receive data from the WebSocket."""
        if self.state == WebSocketState.DISCONNECTED:
            raise WebSocketDisconnect(
                self.close_code or 1006, self.close_reason or "Connection closed"
            )

        try:
            timeout_error = False
            message = None

            async with anyio.move_on_after(self.timeout) as scope:
                async with self.client_channel as receiver:
                    message = await receiver.receive()
                timeout_error = scope.cancel_called

            if timeout_error or message is None:
                await self._handle_disconnect(1002, "Protocol error")
                raise WebSocketDisconnect(1002, "Receive timeout")

            if message["type"] == "message":
                return message["data"]
            elif message["type"] == "close":
                raise WebSocketDisconnect(message["code"], message["reason"])

        except Exception:
            await self._handle_disconnect(1002, "Protocol error")
            raise WebSocketDisconnect(1002, "Receive error")

    async def close(self, code: int = 1000, reason: Optional[str] = None) -> None:
        """Close the WebSocket connection gracefully."""
        if self.state == WebSocketState.DISCONNECTED:
            return

        await self._handle_disconnect(code, reason)
        await self.disconnection_event.wait()

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


class NexiosAsyncTransport(httpx.AsyncBaseTransport):
    """Custom ASGI transport with full HTTP and WebSocket support."""

    def __init__(
        self,
        app: Any,
        raise_app_exceptions: bool = True,
        root_path: str = "",
        client: Tuple[str, int] = ("testclient", 5000),
        app_state: Optional[Dict[str, Any]] = None,
        websocket_timeout: float = 5.0,
    ):
        self.app = app
        self.raise_app_exceptions = raise_app_exceptions
        self.root_path = root_path
        self.client = client
        self.app_state = app_state or {}
        self.websocket_timeout = websocket_timeout

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Handle the incoming request and route it appropriately."""
        scheme, netloc, path, raw_path, query = self._parse_url(request)
        host, port = self._get_host_port(netloc, scheme)
        headers = self._prepare_headers(request, host, port)

        if scheme in {"ws", "wss"}:
            return await self._handle_websocket(
                request, scheme, path, raw_path, query, headers, host, port
            )
        return await self._handle_http(
            request, scheme, path, raw_path, query, headers, host, port
        )

    async def _handle_websocket(
        self,
        request: httpx.Request,
        scheme: str,
        path: str,
        raw_path: bytes,
        query: str,
        headers: HeaderList,
        host: str,
        port: int,
    ) -> httpx.Response:
        """Handle WebSocket requests."""
        import base64
        import hashlib

        def calculate_accept(key: str) -> str:
            """Calculate Sec-WebSocket-Accept header value according to RFC 6455."""
            GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
            accept = hashlib.sha1((key + GUID).encode()).digest()
            return base64.b64encode(accept).decode()

        # Get the WebSocket key from request headers
        ws_key = None
        for k, v in headers:
            if k.lower() == b"sec-websocket-key":
                ws_key = v.decode()
                break

        if not ws_key:
            return httpx.Response(400, content=b"Missing WebSocket Key")

        # Calculate the accept key
        ws_accept = calculate_accept(ws_key)

        # Build WebSocket scope
        scope = self._build_websocket_scope(
            request, scheme, path, raw_path, query, headers, host, port
        )

        # Create WebSocket connection handler
        websocket = WebSocketConnection(
            app=self.app,
            scope=scope,
            raise_app_exceptions=self.raise_app_exceptions,
            timeout=self.websocket_timeout,
        )

        # Return a 101 Switching Protocols response with proper WebSocket headers
        response_headers = {
            "Upgrade": "websocket",
            "Connection": "Upgrade",
            "Sec-WebSocket-Accept": ws_accept,
        }

        # Add subprotocol if specified
        if "sec-websocket-protocol" in request.headers:
            response_headers["Sec-WebSocket-Protocol"] = request.headers[
                "sec-websocket-protocol"
            ]

        return httpx.Response(
            101,
            headers=response_headers,
            request=request,
            extensions={"websocket": websocket},
        )

    async def _handle_http(
        self,
        request: httpx.Request,
        scheme: str,
        path: str,
        raw_path: bytes,
        query: str,
        headers: HeaderList,
        host: str,
        port: int,
    ) -> httpx.Response:
        """Handle HTTP requests."""
        scope = self._build_http_scope(
            request, scheme, path, raw_path, query, headers, host, port
        )
        return await self._send_http_request(scope, request)

    async def _send_http_request(
        self, scope: ASGIScope, request: httpx.Request
    ) -> httpx.Response:
        """Send HTTP request to ASGI app and return response."""
        request_complete = False
        response_started = False
        response_complete = anyio.Event()
        response_body = io.BytesIO()
        response_headers: List[Tuple[str, str]] = []
        status_code = 500

        async def receive() -> Message:
            nonlocal request_complete
            if request_complete:
                await response_complete.wait()
                return {"type": "http.disconnect"}

            body = await request.aread()
            request_complete = True
            return {"type": "http.request", "body": body}

        async def send(message: Message) -> None:
            nonlocal response_started, status_code, response_headers
            if message["type"] == "http.response.start":
                status_code = message["status"]
                response_headers = [
                    (k.decode(), v.decode()) for k, v in message.get("headers", [])
                ]
                response_started = True
            elif message["type"] == "http.response.body":
                assert response_started, "Received body before response start"
                response_body.write(message.get("body", b""))
                if not message.get("more_body", False):
                    response_body.seek(0)
                    response_complete.set()

        try:
            await self.app(scope, receive, send)
        except BaseException as exc:
            if self.raise_app_exceptions:
                raise exc
            status_code = 500
            response_body = io.BytesIO(b"Internal Server Error")

        if self.raise_app_exceptions and not response_started:
            raise RuntimeError("TestClient did not receive any response.")

        return httpx.Response(
            status_code,
            headers=dict(response_headers),
            content=response_body.read(),
            request=request,
        )

    # Helper methods remain the same as previous implementation
    def _parse_url(self, request: httpx.Request) -> Tuple[str, str, str, bytes, str]:
        return (
            request.url.scheme,
            request.url.netloc.decode("ascii"),
            request.url.path,
            request.url.raw_path,
            request.url.query.decode("ascii"),
        )

    def _get_host_port(self, netloc: str, scheme: str) -> Tuple[str, int]:
        default_ports = {"http": 80, "https": 443, "ws": 80, "wss": 443}
        if ":" in netloc:
            host, port = netloc.split(":", 1)
            return host, int(port)
        return netloc, default_ports.get(scheme, 80)

    def _prepare_headers(
        self, request: httpx.Request, host: str, port: int
    ) -> HeaderList:
        headers = (
            [(b"host", f"{host}:{port}".encode())]
            if "host" not in request.headers
            else []
        )
        headers.extend(
            [
                (key.lower().encode(), value.encode())
                for key, value in request.headers.multi_items()
            ]
        )
        return headers

    def _build_http_scope(
        self,
        request: httpx.Request,
        scheme: str,
        path: str,
        raw_path: bytes,
        query: str,
        headers: HeaderList,
        host: str,
        port: int,
    ) -> ASGIScope:
        return {
            "type": "http",
            "http_version": "1.1",
            "method": request.method,
            "path": unquote(path),
            "raw_path": raw_path.split(b"?", 1)[0],
            "root_path": self.root_path,
            "scheme": scheme,
            "query_string": query.encode(),
            "headers": headers,
            "client": self.client,
            "server": [host, port],
            "state": self.app_state.copy(),
        }

    def _build_websocket_scope(
        self,
        request: httpx.Request,
        scheme: str,
        path: str,
        raw_path: bytes,
        query: str,
        headers: HeaderList,
        host: str,
        port: int,
    ) -> ASGIScope:
        subprotocols = []
        if "sec-websocket-protocol" in request.headers:
            subprotocols = [
                p.strip() for p in request.headers["sec-websocket-protocol"].split(",")
            ]

        return {
            "type": "websocket",
            "path": unquote(path),
            "raw_path": raw_path.split(b"?", 1)[0],
            "root_path": self.root_path,
            "scheme": scheme,
            "query_string": query.encode(),
            "headers": headers,
            "client": self.client,
            "server": [host, port],
            "subprotocols": subprotocols,
            "state": self.app_state.copy(),
            "app": self.app,  # Include app in scope
        }
