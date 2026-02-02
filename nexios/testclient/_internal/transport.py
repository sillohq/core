from __future__ import annotations

import io
from collections.abc import Sequence
from types import GeneratorType
from typing import Any, cast
from urllib.parse import unquote

import anyio
import httpx

from nexios.testclient._internal.types import ASGI3App, PortalFactoryType
from nexios.testclient._internal.websockets import WebSocketTestSession
from nexios.testclient.exceptions import ASGISpecViolation, UpgradeException
from nexios.types import Message


class TestClientTransport(httpx.BaseTransport):
    encoding: str = "ascii"

    def __init__(
        self,
        app: ASGI3App,
        portal_factory: PortalFactoryType,
        raise_server_exceptions: bool = True,
        root_path: str = "",
        *,
        check_asgi_conformance: bool = True,
        app_state: dict[str, Any],
    ) -> None:
        """
        Initialize the TestClientTransport.

        Args:
            app: The ASGI3App instance.
            portal_factory: The PortalFactoryType instance.
            raise_server_exceptions: Whether to raise server exceptions.
            check_asgi_conformance: Whether to raise errors on ASGI conformance issues
            root_path: The root path.
            app_state: The application state.
        """
        self.app = app
        self.raise_server_exceptions = raise_server_exceptions
        self.check_asgi_conformance = check_asgi_conformance
        self.root_path = root_path
        self.portal_factory = portal_factory
        self.app_state = app_state

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        """
        Handle the HTTP request.

        Args:
            request: The httpx.Request instance.

        Returns:
            The httpx.Response instance.
        """
        scheme, netloc, path, raw_path, query = self._parse_url(request.url)
        host, port, default_port = self._parse_host_and_port(netloc, scheme)
        headers = self._build_headers(request.headers, host, port, default_port)

        if scheme in {"ws", "wss"}:
            session = self._handle_websocket_request(
                request, scheme, path, cast(str, raw_path), query, headers, host, port
            )
            raise UpgradeException(session)

        scope = self._build_http_scope(
            request, scheme, path, cast(str, raw_path), query, headers, host, port
        )
        response = self._process_http_request(scope, request)
        return response

    def _parse_url(
        self, url: httpx.URL
    ) -> tuple[str, str, str, str, str] | tuple[str, str, str, bytes, str]:
        """
        Parse the URL components.

        Args:
            url: The httpx.URL instance.

        Returns:
            A tuple containing the scheme, netloc, path, raw_path, and query components of the URL.
        """
        scheme = url.scheme
        netloc = url.netloc.decode(encoding=self.encoding)
        path = url.path
        raw_path = url.raw_path
        query = url.query.decode(encoding=self.encoding)
        return scheme, netloc, path, raw_path, query

    def _parse_host_and_port(self, netloc: str, scheme: str) -> tuple[str, int, int]:
        """
        Parse the netloc and scheme to extract the host and port.

        Args:
            netloc (str): The network location string, including the host and optional port.
            scheme (str): The scheme of the URL.

        Returns:
            tuple[str, int]: A tuple containing the host and port.

        Raises:
            None

        """
        default_port = {"http": 80, "ws": 80, "https": 443, "wss": 443}[scheme]
        if ":" in netloc:
            host, port_string = netloc.split(":", 1)
            port = int(port_string)
        else:
            host = netloc
            port = default_port
        return host, port, default_port

    def _build_headers(
        self, request_headers: httpx.Headers, host: str, port: int, default_port: int
    ) -> list[tuple[bytes, bytes]]:
        """
        Build the headers for an HTTP request.

        Args:
            request_headers (httpx.Headers): The headers provided in the request.
            host (str): The host of the request.
            port (int): The port of the request.
            default_port (int): The default port to use if no port is specified.

        Returns:
            list[tuple[bytes, bytes]]: The built headers as a list of tuples.

        """
        headers: list[Any] = []
        if "host" in request_headers:
            headers = []
        elif port == default_port:
            headers = [(b"host", host.encode())]
        else:
            headers = [(b"host", (f"{host}:{port}").encode())]
        headers += [
            (key.lower().encode(), value.encode())
            for key, value in request_headers.multi_items()
        ]
        return headers

    def _handle_websocket_request(
        self,
        request: httpx.Request,
        scheme: str,
        path: str,
        raw_path: str,
        query: str,
        headers: list[tuple[bytes, bytes]],
        host: str,
        port: int,
    ) -> WebSocketTestSession:
        """
        Handles a WebSocket request and returns a WebSocketTestSession.

        Args:
            request (httpx.Request): The HTTP request object.
            scheme (str): The scheme of the request (e.g., "http" or "https").
            path (str): The path of the request.
            raw_path (str): The raw path of the request.
            query (str): The query string of the request.
            headers (list[tuple[bytes, bytes]]): The headers of the request.
            host (str): The host of the request.
            port (int): The port of the request.

        Returns:
            WebSocketTestSession: The WebSocketTestSession object.

        """
        subprotocol = request.headers.get("sec-websocket-protocol", None)
        if subprotocol is None:
            subprotocols: Sequence[str] = []
        else:
            subprotocols = [value.strip() for value in subprotocol.split(",")]

        scope = {
            "type": "websocket",
            "path": unquote(path),
            "raw_path": raw_path,
            "root_path": self.root_path,
            "scheme": scheme,
            "query_string": query.encode(),
            "headers": headers,
            "client": None,
            "server": [host, port],
            "subprotocols": subprotocols,
            "state": self.app_state.copy(),
            "extensions": {"websocket.http.response": {}},
        }
        session = WebSocketTestSession(self.app, scope, self.portal_factory)
        return session

    def _build_http_scope(
        self,
        request: httpx.Request,
        scheme: str,
        path: str,
        raw_path: str,
        query: str,
        headers: list[tuple[bytes, bytes]],
        host: str,
        port: int,
    ) -> dict[str, Any]:
        """
        Build the HTTP scope dictionary for the given request.

        Args:
            request (httpx.Request): The HTTP request object.
            scheme (str): The scheme of the request (e.g., "http" or "https").
            path (str): The decoded path of the request.
            raw_path (str): The raw path of the request.
            query (str): The query string of the request.
            headers (list[tuple[bytes, bytes]]): The headers of the request.
            host (str): The host of the request.
            port (int): The port of the request.

        Returns:
            dict[str, Any]: The HTTP scope dictionary.

        """
        scope = {
            "type": "http",
            "http_version": "1.1",
            "method": request.method,
            "path": unquote(path),
            "raw_path": raw_path,
            "root_path": self.root_path,
            "scheme": scheme,
            "query_string": query.encode(),
            "headers": headers,
            "client": None,
            "server": [host, port],
            "extensions": {"http.response.debug": {}},
            "state": self.app_state.copy(),
        }
        return scope

    def _process_http_request(
        self, scope: dict[str, Any], request: httpx.Request
    ) -> httpx.Response:
        """
        Process an HTTP request and return an HTTP response.

        Args:
            scope (dict[str, Any]): The ASGI scope of the request.
            request (httpx.Request): The HTTP request object.

        Returns:
            httpx.Response: The HTTP response object.

        Raises:
            Exception: If an error occurs during processing.

        Notes:
            This method is responsible for processing an incoming HTTP request and generating
            an appropriate HTTP response. It handles the request body, response headers, and
            response body.

            The method uses an async generator function `receive` to receive messages from the
            ASGI application, and an async function `send` to send messages back to the ASGI
            application.

            The method creates a portal using the `portal_factory` method, which is responsible
            for managing the communication between the test client and the ASGI application.

            If an exception occurs during processing and `raise_server_exceptions` is set to
            `True`, the exception is re-raised. Otherwise, if no response has been started, a
            default 500 Internal Server Error response is returned.

            The method returns an `httpx.Response` object representing the processed response.
            If a template and context are provided in the response messages, they are attached
            to the response object.
        """
        request_complete = False
        response_started = False
        response_complete: anyio.Event
        raw_kwargs: dict[str, Any] = {"stream": io.BytesIO()}
        template = None
        context = None

        async def receive() -> Message:
            """
            Receive an HTTP request message from the ASGI application.

            Returns:
            Message: The received message.

            Notes:
            This method is responsible for receiving an HTTP request message from the ASGI application.
            It handles different types of request bodies, including strings, generators, and bytes.

            If the request body is a string, it is encoded as UTF-8 bytes before being returned.

            If the request body is a generator, it sends a chunk of the body using the `send` method.
            The chunk is encoded as UTF-8 bytes before being returned. If there are more chunks to send,
            the message type is set to "http.request" with the "more_body" flag set to True.

            If the request body is None, an empty bytes object is returned.

            If the request body is not a string, generator, or None, it is assumed to be bytes and returned as is.

            Once the request body is received, the method sets the `request_complete` flag to True to indicate
            that the request is complete.

            If the request is complete and the response is not yet complete, a "http.disconnect" message is returned.
            """
            nonlocal request_complete

            if request_complete:
                if not response_complete.is_set():
                    await response_complete.wait()
                return {"type": "http.disconnect"}

            body = request.read()
            if isinstance(cast(str, body), str):
                if self.check_asgi_conformance:
                    raise ASGISpecViolation(
                        "ASGI Spec violation: body must be a bytes string"
                    )
                body_bytes: bytes = body.encode("utf-8")
            elif body is None:
                body_bytes = b""
            elif isinstance(cast(str, body), GeneratorType):
                try:
                    chunk = body.send(None)
                    if isinstance(chunk, str):
                        if self.check_asgi_conformance:
                            raise ASGISpecViolation(
                                "ASGI Spec violation: chunk must be a bytes string"
                            )
                        chunk = chunk.encode("utf-8")
                    return {"type": "http.request", "body": chunk, "more_body": True}
                except StopIteration:
                    request_complete = True
                    return {"type": "http.request", "body": b""}
            else:
                body_bytes = body

            request_complete = True
            return {"type": "http.request", "body": body_bytes}

        async def send(message: Message) -> None:
            """
            Process the messages received from the ASGI application and update the response accordingly.

            Args:
            message (Message): The message received from the ASGI application.

            Raises:
            AssertionError: If the messages are received in an unexpected order.

            Notes:
            This method is responsible for processing the messages received from the ASGI application
            and updating the response object accordingly. It handles messages of type "http.response.start",
            "http.response.body", and "http.response.debug".

            If a "http.response.start" message is received, it updates the status code and headers of the response.

            If a "http.response.body" message is received, it appends the body to the response stream. If the
            message indicates that there is no more body, it sets the response stream as complete.

            If a "http.response.debug" message is received, it updates the template and context of the response.

            If the messages are received in an unexpected order, an AssertionError is raised.
            """
            nonlocal raw_kwargs, response_started, template, context

            if message["type"] == "http.response.start":
                assert not response_started, (
                    'Received multiple "http.response.start" messages.'
                )
                raw_kwargs["status_code"] = message["status"]
                raw_kwargs["headers"] = list(message.get("headers", []))
                response_started = True
            elif message["type"] == "http.response.body":
                assert response_started, (
                    'Received "http.response.body" without "http.response.start".'
                )
                assert not response_complete.is_set(), (
                    'Received "http.response.body" after response completed.'
                )
                body = message.get("body", b"")
                # we allow here all of the types because some servers allow them too
                if self.check_asgi_conformance and not isinstance(
                    body, (bytes, memoryview, bytearray)
                ):
                    raise ASGISpecViolation(
                        "ASGI Spec violation: body must be a bytes string"
                    )
                more_body = message.get("more_body", False)
                if request.method != "HEAD":
                    raw_kwargs["stream"].write(body)
                if not more_body:
                    raw_kwargs["stream"].seek(0)
                    response_complete.set()
            elif message["type"] == "http.response.debug":
                template = message["info"]["template"]
                context = message["info"]["context"]

        try:
            with self.portal_factory() as portal:
                response_complete = portal.call(anyio.Event)
                portal.call(self.app, scope, receive, send)
        except BaseException as exc:
            if self.raise_server_exceptions:
                raise exc

        if not response_started:
            if self.raise_server_exceptions or self.check_asgi_conformance:
                raise ASGISpecViolation("TestClient did not receive any response.")
            raw_kwargs = {
                "status_code": 500,
                "headers": [],
                "stream": io.BytesIO(),
            }

        raw_kwargs["stream"] = httpx.ByteStream(raw_kwargs["stream"].read())
        # we persist headers for testclient for debugging purposes
        # must happen before checking the headers
        raw_kwargs["headers"] = list(raw_kwargs["headers"])
        if self.check_asgi_conformance:
            # the raw headers are bytes
            for header_key, header_value in raw_kwargs["headers"]:
                if not isinstance(header_key, bytes):
                    raise ASGISpecViolation(
                        f'Response header key "{header_key!r}" is not a bytes string.'
                    )
                if b"\n" in header_key:
                    raise ASGISpecViolation(
                        f'Response header key "{header_key!r}" contains a newline.'
                    )
                if not isinstance(header_value, bytes):
                    raise ASGISpecViolation(
                        f'Response header key "{header_key!r}" value ("{header_value!r}") is not a bytes string.'
                    )
                if b"\n" in header_value:
                    raise ASGISpecViolation(
                        f'Response header "{header_key!r}" value ("{header_value!r}") contains a newline.'
                    )

        response = httpx.Response(**raw_kwargs, request=request)
        if template is not None:
            response.template = template
            response.context = context
        return response


class AsyncTestClientTransport(httpx.AsyncBaseTransport):
    encoding: str = "ascii"

    def __init__(
        self,
        app: ASGI3App,
        *,
        raise_server_exceptions: bool = True,
        root_path: str = "",
        check_asgi_conformance: bool = True,
        app_state: dict[str, Any],
    ) -> None:
        self.app = app
        self.raise_server_exceptions = raise_server_exceptions
        self.check_asgi_conformance = check_asgi_conformance
        self.root_path = root_path
        self.app_state = app_state

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        scheme, netloc, path, raw_path, query = self._parse_url(request.url)
        host, port, default_port = self._parse_host_and_port(netloc, scheme)
        headers = self._build_headers(request.headers, host, port, default_port)

        if scheme in {"ws", "wss"}:
            session = await self._handle_websocket_request(
                request, scheme, path, cast(str, raw_path), query, headers, host, port
            )
            raise UpgradeException(session)

        scope = self._build_http_scope(
            request, scheme, path, cast(str, raw_path), query, headers, host, port
        )

        return await self._process_http_request(scope, request)

    def _parse_url(
        self, url: httpx.URL
    ) -> tuple[str, str, str, str, str] | tuple[str, str, str, bytes, str]:
        scheme = url.scheme
        netloc = url.netloc.decode(encoding=self.encoding)
        path = url.path
        raw_path = url.raw_path
        query = url.query.decode(encoding=self.encoding)
        return scheme, netloc, path, raw_path, query

    def _parse_host_and_port(self, netloc: str, scheme: str) -> tuple[str, int, int]:
        default_port = {"http": 80, "ws": 80, "https": 443, "wss": 443}[scheme]
        if ":" in netloc:
            host, port_str = netloc.split(":", 1)
            port = int(port_str)
        else:
            host = netloc
            port = default_port
        return host, port, default_port

    def _build_headers(
        self, request_headers: httpx.Headers, host: str, port: int, default_port: int
    ) -> list[tuple[bytes, bytes]]:
        if "host" in request_headers:
            headers: list[Any] = []
        elif port == default_port:
            headers = [(b"host", host.encode())]
        else:
            headers = [(b"host", f"{host}:{port}".encode())]
        headers += [
            (k.lower().encode(), v.encode()) for k, v in request_headers.multi_items()
        ]
        return headers

    async def _handle_websocket_request(
        self,
        request: httpx.Request,
        scheme: str,
        path: str,
        raw_path: str,
        query: str,
        headers: list[tuple[bytes, bytes]],
        host: str,
        port: int,
    ) -> WebSocketTestSession:
        subprotocol = request.headers.get("sec-websocket-protocol", None)
        subprotocols: Sequence[str] = (
            [v.strip() for v in subprotocol.split(",")] if subprotocol else []
        )
        scope = {
            "type": "websocket",
            "path": unquote(path),
            "raw_path": raw_path,
            "root_path": self.root_path,
            "scheme": scheme,
            "query_string": query.encode(),
            "headers": headers,
            "client": None,
            "server": [host, port],
            "subprotocols": subprotocols,
            "state": self.app_state.copy(),
            "extensions": {"websocket.http.response": {}},
        }
        # WebSocket handling should still use the same test session abstraction
        return WebSocketTestSession(self.app, scope, portal_factory=None)

    def _build_http_scope(
        self,
        request: httpx.Request,
        scheme: str,
        path: str,
        raw_path: str,
        query: str,
        headers: list[tuple[bytes, bytes]],
        host: str,
        port: int,
    ) -> dict[str, Any]:
        return {
            "type": "http",
            "http_version": "1.1",
            "method": request.method,
            "path": unquote(path),
            "raw_path": raw_path,
            "root_path": self.root_path,
            "scheme": scheme,
            "query_string": query.encode(),
            "headers": headers,
            "client": None,
            "server": [host, port],
            "extensions": {"http.response.debug": {}},
            "state": self.app_state.copy(),
        }

    async def _process_http_request(
        self, scope: dict[str, Any], request: httpx.Request
    ) -> httpx.Response:
        request_complete = False
        response_started = False
        response_complete = anyio.Event()
        raw_kwargs: dict[str, Any] = {"stream": io.BytesIO()}
        template = None
        context = None

        async def receive() -> Message:
            nonlocal request_complete
            if request_complete:
                if not response_complete.is_set():
                    await response_complete.wait()
                return {"type": "http.disconnect"}

            body = request.read()

            if isinstance(body, str):  # type: ignore[unreachable]
                if self.check_asgi_conformance:  # type: ignore[unreachable]
                    raise ASGISpecViolation("ASGI Spec violation: body must be bytes")
                body_bytes = body.encode("utf-8")

            elif body is None:
                body_bytes = b""

            elif isinstance(body, GeneratorType):  # type: ignore[unreachable]
                try:  # type: ignore[unreachable]
                    chunk = next(body)
                    if isinstance(chunk, str):
                        if self.check_asgi_conformance:
                            raise ASGISpecViolation(
                                "ASGI Spec violation: chunk must be bytes"
                            )
                        chunk = chunk.encode("utf-8")
                    return {"type": "http.request", "body": chunk, "more_body": True}
                except StopIteration:
                    request_complete = True
                    return {"type": "http.request", "body": b""}
            else:
                body_bytes = body

            request_complete = True
            return {"type": "http.request", "body": body_bytes}

        async def send(message: Message) -> None:
            nonlocal raw_kwargs, response_started, template, context

            if message["type"] == "http.response.start":
                assert not response_started
                raw_kwargs["status_code"] = message["status"]
                raw_kwargs["headers"] = list(message.get("headers", []))
                response_started = True

            elif message["type"] == "http.response.body":
                assert response_started
                body = message.get("body", b"")
                if self.check_asgi_conformance and not isinstance(
                    body, (bytes, memoryview, bytearray)
                ):
                    raise ASGISpecViolation("ASGI Spec violation: body must be bytes")
                if request.method != "HEAD":
                    raw_kwargs["stream"].write(body)
                if not message.get("more_body", False):
                    raw_kwargs["stream"].seek(0)
                    response_complete.set()

            elif message["type"] == "http.response.debug":
                template = message["info"]["template"]
                context = message["info"]["context"]

        # Run the ASGI app natively
        try:
            await self.app(scope, receive, send)
        except BaseException:
            if self.raise_server_exceptions:
                raise
        finally:
            response_complete.set()

        if not response_started:
            if self.raise_server_exceptions or self.check_asgi_conformance:
                raise ASGISpecViolation("TestClient did not receive any response.")
            raw_kwargs.update(
                status_code=500, headers=[], stream=io.BytesIO(b"Internal Server Error")
            )

        raw_kwargs["stream"] = httpx.ByteStream(raw_kwargs["stream"].read())
        raw_kwargs["headers"] = list(raw_kwargs["headers"])

        if self.check_asgi_conformance:
            for key, val in raw_kwargs["headers"]:
                if not isinstance(key, bytes) or not isinstance(val, bytes):
                    raise ASGISpecViolation(
                        "ASGI Spec violation: headers must be bytes"
                    )

        response = httpx.Response(**raw_kwargs, request=request)
        if template is not None:
            response.template = template
            response.context = context
        return response
