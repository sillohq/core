from __future__ import annotations

import contextlib
import math
from collections.abc import Generator, MutableMapping, Sequence
from concurrent.futures import Future
from types import TracebackType
from typing import Any, Literal, cast
from urllib.parse import urljoin

import anyio
import anyio.from_thread
import httpx
from anyio.abc import BlockingPortal, ObjectReceiveStream, ObjectSendStream, TaskStatus
from anyio.streams.stapled import StapledObjectStream
from httpx._client import UseClientDefault
from httpx._types import (
    AuthTypes,
    CookieTypes,
    HeaderTypes,
    QueryParamTypes,
    RequestContent,
    RequestExtensions,
    RequestFiles,
    TimeoutTypes,
    URLTypes,
)

from nexios.testclient._internal.inputs import RequestInputsDefaultValues
from nexios.testclient._internal.transport import TestClientTransport
from nexios.testclient._internal.types import ASGI2App, RequestData
from nexios.testclient._internal.utils import AsyncBackend, WrapASGI2, is_asgi3
from nexios.testclient._internal.websockets import WebSocketTestSession
from nexios.testclient.exceptions import UpgradeException
from nexios.types import ASGIApp

try:
    import httpx

except ModuleNotFoundError:  # pragma: no cover
    raise RuntimeError(
        "The nexios.testclient module requires the httpx package to be installed.\n"
        "You can install this with:\n"
        "    $ pip install httpx\n"
    ) from None


class TestClient(httpx.Client):
    """
    A test client for making HTTP requests to an ASGI application.

    Args:
        app (ASGIApp): The ASGI application to test.
        base_url (str, optional): The base URL for the requests. Defaults to "http://testserver".
        raise_server_exceptions (bool, optional): Whether to raise exceptions for server errors. Defaults to True.
        root_path (str, optional): The root path for the requests. Defaults to "".
        backend (Literal["asyncio", "trio"], optional): The async backend to use. Defaults to "asyncio".
        backend_options (dict[str, Any] | None, optional): Options for the async backend. Defaults to None.
        cookies (httpx._types.CookieTypes | None, optional): Cookies to include in the requests. Defaults to None.
        headers (dict[str, str] | None, optional): Headers to include in the requests. Defaults to None.
        follow_redirects (bool, optional): Whether to follow redirects. Defaults to True.
        check_asgi_conformance (bool, optional): Whether to check the asgi conformance. Defaults to True.
    """

    __test__ = False
    task: Future[None]
    portal: BlockingPortal | None = None

    def __init__(
        self,
        app: ASGIApp,
        base_url: str = "http://testserver",
        raise_server_exceptions: bool = True,
        root_path: str = "",
        backend: Literal["asyncio", "trio"] = "asyncio",
        backend_options: dict[str, Any] | None = None,
        cookies: CookieTypes | None = None,
        headers: HeaderTypes | None = None,
        follow_redirects: bool = True,
        check_asgi_conformance: bool = True,
    ) -> None:
        self.async_backend = AsyncBackend(
            backend=backend, backend_options=backend_options or {}
        )
        if is_asgi3(app):
            asgi_app = app
        else:
            asgi2_app = cast(ASGI2App, app)
            asgi_app = WrapASGI2(asgi2_app)
        self.app = asgi_app
        self.app_state: dict[str, Any] = {}
        transport = TestClientTransport(
            app=self.app,
            portal_factory=self._portal_factory,
            raise_server_exceptions=raise_server_exceptions,
            root_path=root_path,
            app_state=self.app_state,
            check_asgi_conformance=check_asgi_conformance,
        )
        if headers is None:
            headers = {}
        cast(dict[str, str], headers).setdefault("user-agent", "testclient")
        super().__init__(
            base_url=base_url,
            headers=headers,
            transport=transport,
            follow_redirects=follow_redirects,
            cookies=cookies,
        )

    @contextlib.contextmanager
    def _portal_factory(self) -> Generator[BlockingPortal, None, None]:
        """
        Context manager that creates a blocking portal for handling async tasks.

        Yields:
            anyio.abc.BlockingPortal: The blocking portal.
        """
        if self.portal is not None:
            yield self.portal
        else:
            with anyio.from_thread.start_blocking_portal(
                **self.async_backend
            ) as portal:
                yield portal

    def request(
        self,
        method: str,
        url: URLTypes,
        *,
        content: RequestContent | None = None,
        data: RequestData | None = None,
        files: RequestFiles | None = None,
        json: Any | None = None,
        params: QueryParamTypes | None = None,
        headers: HeaderTypes | None = None,
        cookies: CookieTypes | None = None,
        auth: (
            AuthTypes | httpx._client.UseClientDefault | None
        ) = httpx._client.USE_CLIENT_DEFAULT,
        follow_redirects: bool | UseClientDefault = UseClientDefault,
        timeout: (
            TimeoutTypes | httpx._client.UseClientDefault | None
        ) = httpx._client.USE_CLIENT_DEFAULT,
        extensions: RequestExtensions | None = None,
        stream: bool = False,
    ) -> httpx.Response:
        """
        Sends an HTTP request.

        Args:
            method (str): The HTTP method.
            url (URLTypes): The URL to send the request to.
            content (RequestContent | None, optional): The request content. Defaults to None.
            data (RequestData | None, optional): The request data. Defaults to None.
            files (RequestFiles | None, optional): The request files. Defaults to None.
            json (Any, optional): The request JSON. Defaults to None.
            params (QueryParamTypes | None, optional): The request query parameters. Defaults to None.
            headers (HeaderTypes | None, optional): The request headers. Defaults to None.
            cookies (CookieTypes | None, optional): The request cookies. Defaults to None.
            auth (AuthTypes | httpx._client.UseClientDefault, optional): The request authentication. Defaults to httpx._client.USE_CLIENT_DEFAULT.
            follow_redirects (bool | None, optional): Whether to follow redirects. Defaults to None.
            timeout (TimeoutTypes | httpx._client.UseClientDefault, optional): The request timeout. Defaults to httpx._client.USE_CLIENT_DEFAULT.
            extensions (dict[str, Any] | None, optional): The request extensions. Defaults to None.

        Returns:
            httpx.Response: The HTTP response.
        """
        url = self._merge_url(url)
        redirect: bool | httpx._client.UseClientDefault = (
            httpx._client.USE_CLIENT_DEFAULT
        )
        if follow_redirects is not None:
            redirect = follow_redirects

        if stream:
            # Return an open streaming response context.
            # Open a streaming context and return the httpx.Response (not Request)
            return self.stream(
                method=method,
                url=url,
                content=content,
                data=data,
                files=files,
                json=json,
                params=params,
                headers=headers,
                cookies=cookies,
                auth=auth,
                timeout=timeout,
                extensions=extensions,
                follow_redirects=follow_redirects,
            ).__enter__()

        return super().request(
            method,
            url,
            content=content,
            data=data,
            files=files,
            json=json,
            params=params,
            headers=headers,
            cookies=cookies,
            auth=auth,
            follow_redirects=redirect,
            timeout=timeout,
            extensions=extensions,
        )

    def _process_request(
        self, method: str, url: URLTypes, **kwargs: Any
    ) -> httpx.Response:
        """*args: Any
        Processes the request.

        Args:
            method (str): The string method to request from.
            url (URLTypes): The URL to send the request to.
            **kwargs (RequestInputs): The request inputs.

        Returns:
            httpx.Request: The HTTP request.
        """
        if not kwargs:
            kwargs = RequestInputsDefaultValues
        else:
            remaining_kwargs = {
                k: v for k, v in RequestInputsDefaultValues.items() if k not in kwargs
            }
            kwargs.update(remaining_kwargs)

        return self.request(
            method=method,
            url=url,
            **kwargs,  # ty: ignore[invalid-argument-type]
        )

    def get(
        self,
        url: URLTypes,
        **kwargs: Any,
    ) -> httpx.Response:
        return self._process_request(method="GET", url=url, **kwargs)

    def head(
        self,
        url: URLTypes,
        **kwargs: Any,
    ) -> httpx.Response:
        return self._process_request(method="HEAD", url=url, **kwargs)

    def post(
        self,
        url: URLTypes,
        **kwargs: Any,
    ) -> httpx.Response:
        return self._process_request(method="POST", url=url, **kwargs)

    def put(
        self,
        url: URLTypes,
        **kwargs: Any,
    ) -> httpx.Response:
        return self._process_request(method="PUT", url=url, **kwargs)

    def patch(
        self,
        url: URLTypes,
        **kwargs: Any,
    ) -> httpx.Response:
        return self._process_request(method="PATCH", url=url, **kwargs)

    def delete(
        self,
        url: URLTypes,
        **kwargs: Any,
    ) -> httpx.Response:
        return self._process_request(method="DELETE", url=url, **kwargs)

    def options(
        self,
        url: URLTypes,
        **kwargs: Any,
    ) -> httpx.Response:
        return self._process_request(method="OPTIONS", url=url, **kwargs)

    def websocket_connect(
        self,
        url: str,
        subprotocols: Sequence[str] | None = None,
        **kwargs: Any,
    ) -> WebSocketTestSession:
        """
        Establishes a WebSocket connection.

        Args:
            url (str): The WebSocket URL.
            subprotocols (Sequence[str] | None, optional): The WebSocket subprotocols. Defaults to None.
            **kwargs (Any): Additional keyword arguments.

        Returns:
            WebSocketTestSession: The WebSocket session.
        """
        url = urljoin("ws://testserver", url)
        headers = self._prepare_websocket_headers(subprotocols, **kwargs)
        kwargs["headers"] = headers
        try:
            super().request("GET", url, **kwargs)
        except UpgradeException as exc:
            session = exc.session
        else:
            raise RuntimeError("Expected WebSocket upgrade")

        return session

    def _prepare_websocket_headers(
        self,
        subprotocols: Sequence[str] | None = None,
        **kwargs: dict[str, Any],
    ) -> dict[str, str]:
        """
        Prepare the headers for a WebSocket connection.

        Args:
            subprotocols (Sequence[str] | None, optional): The WebSocket subprotocols. Defaults to None.
            **kwargs (dict[str, Any]): Additional keyword arguments.

        Returns:
            dict[str, str]: The prepared headers.
        """
        headers = kwargs.get("headers", {})
        headers.setdefault("connection", "upgrade")
        headers.setdefault("sec-websocket-key", "testserver==")
        headers.setdefault("sec-websocket-version", "13")
        if subprotocols is not None:
            headers.setdefault("sec-websocket-protocol", ", ".join(subprotocols))
        kwargs["headers"] = headers
        return headers

    def __enter__(self) -> TestClient:
        """
        Enters the context manager.

        Returns:
            TestClient: The test client.
        """
        with contextlib.ExitStack() as stack:
            self.portal = portal = stack.enter_context(
                anyio.from_thread.start_blocking_portal(**self.async_backend)
            )

            @stack.callback
            def reset_portal() -> None:
                self.portal = None

            send1: ObjectSendStream[MutableMapping[str, Any] | None]
            receive1: ObjectReceiveStream[MutableMapping[str, Any] | None]
            send2: ObjectSendStream[MutableMapping[str, Any]]
            receive2: ObjectReceiveStream[MutableMapping[str, Any]]
            send1, receive1 = anyio.create_memory_object_stream(math.inf)
            send2, receive2 = anyio.create_memory_object_stream(math.inf)
            self.stream_send = StapledObjectStream(send1, receive1)
            self.stream_receive = StapledObjectStream(send2, receive2)
            self.task = portal.start_task_soon(self.lifespan)
            portal.call(self.wait_startup)

            @stack.callback
            def wait_shutdown() -> None:
                portal.call(self.wait_shutdown)

            self.exit_stack = stack.pop_all()

        return self

    async def __aenter__(self) -> TestClient:
        """
        Enter the test client in an asynchronous context.

        Allows:
            async with create_client(...) as client:
                response = await client.get("/")
        """
        # Use a native AnyIO TaskGroup instead of blocking portals
        self._tg = anyio.create_task_group()
        await self._tg.__aenter__()  # manually enter group

        # setup streams (same as sync path)
        send1, receive1 = anyio.create_memory_object_stream(math.inf)
        send2, receive2 = anyio.create_memory_object_stream(math.inf)
        self.stream_send = StapledObjectStream(send1, receive1)
        self.stream_receive = StapledObjectStream(send2, receive2)

        # Run the lifespan coroutine as a background task
        self.task = await self._tg.start(self._lifespan_runner)
        await self.wait_startup()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None = None,
        exc_value: BaseException | None = None,
        traceback: TracebackType | None = None,
    ) -> None:
        """
        Exits the context manager.
        """
        self.exit_stack.close()

    async def __aexit__(self, *args: Any) -> None:
        """
        Exit the asynchronous context, performing a graceful shutdown.
        """
        await self.wait_shutdown()
        await self._tg.__aexit__(None, None, None)

    async def _lifespan_runner(
        self, *, task_status: TaskStatus = anyio.TASK_STATUS_IGNORED
    ) -> None:
        """Helper task running the ASGI lifespan inside async context."""
        task_status.started()
        await self.lifespan()

    async def lifespan(self) -> None:
        """
        Handles the lifespan of the ASGI application.
        """
        scope = {"type": "lifespan", "state": self.app_state}
        try:
            await self.app(scope, self.stream_receive.receive, self.stream_send.send)
        finally:
            with contextlib.suppress(anyio.ClosedResourceError):
                await self.stream_send.send(None)

    async def wait_startup(self) -> None:
        """
        Waits for the ASGI application to start up.
        """
        await self.stream_receive.send({"type": "lifespan.startup"})

        async def receive() -> Any:
            message = await self.stream_send.receive()
            if message is None:
                self.task.result()
            return message

        message = await receive()
        assert message["type"] in (
            "lifespan.startup.complete",
            "lifespan.startup.failed",
        )
        if message["type"] == "lifespan.startup.failed":
            await receive()

    async def wait_shutdown(self) -> None:
        """
        Waits for the ASGI application to shut down.
        """

        async def receive() -> Any:
            message = await self.stream_send.receive()
            if message is None:
                self.task.result()
            return message

        async_mode = hasattr(self, "_tg")

        if async_mode:
            await self.stream_receive.send({"type": "lifespan.shutdown"})
            message = await receive()
            assert message["type"] in (
                "lifespan.shutdown.complete",
                "lifespan.shutdown.failed",
            )
            if message["type"] == "lifespan.shutdown.failed":
                await receive()
        else:
            async with self.stream_send:
                await self.stream_receive.send({"type": "lifespan.shutdown"})
                message = await receive()
                assert message["type"] in (
                    "lifespan.shutdown.complete",
                    "lifespan.shutdown.failed",
                )
                if message["type"] == "lifespan.shutdown.failed":
                    await receive()
