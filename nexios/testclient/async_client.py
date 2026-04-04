from __future__ import annotations

import contextlib
import math
from collections.abc import Sequence
from types import TracebackType
from typing import Any, Literal, cast
from urllib.parse import urljoin

import anyio
import httpx
from anyio.abc import ObjectReceiveStream, ObjectSendStream, TaskStatus
from anyio.streams.stapled import StapledObjectStream
from httpx import USE_CLIENT_DEFAULT
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
from httpx._urls import URL

from nexios.testclient._internal.transport import AsyncTestClientTransport
from nexios.testclient._internal.types import ASGI2App, RequestData
from nexios.testclient._internal.utils import AsyncBackend, WrapASGI2, is_asgi3
from nexios.testclient._internal.websockets import WebSocketTestSession
from nexios.testclient.exceptions import UpgradeException
from nexios.types import ASGIApp


class AsyncTestClient(httpx.AsyncClient):
    __test__ = False

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
            asgi_app = cast(ASGIApp, app)
        else:
            app2 = cast(ASGI2App, app)
            asgi_app = cast(ASGIApp, WrapASGI2(app2))

        self.app = asgi_app
        self.app_state: dict[str, Any] = {}

        transport = AsyncTestClientTransport(
            app=self.app,
            raise_server_exceptions=raise_server_exceptions,
            root_path=root_path,
            app_state=self.app_state,
            check_asgi_conformance=check_asgi_conformance,
        )

        norm_headers: dict[str, str]
        if headers is None:
            norm_headers = {}
        elif isinstance(headers, dict):
            # Ensure string keys/values
            norm_headers = {str(k): str(v) for k, v in headers.items()}
        else:
            # Let httpx normalize first, then materialize to dict[str, str]
            norm_headers = dict(httpx.Headers(headers).items())
        norm_headers.setdefault("user-agent", "testclient")

        super().__init__(
            base_url=base_url,
            headers=headers,
            transport=transport,
            follow_redirects=follow_redirects,
            cookies=cookies,
        )

    async def request(
        self,
        method: str,
        url: URL | str,
        *,
        content: RequestContent | None = None,
        data: RequestData | None = None,
        files: RequestFiles | None = None,
        json: Any | None = None,
        params: QueryParamTypes | None = None,
        headers: HeaderTypes | None = None,
        cookies: CookieTypes | None = None,
        auth: AuthTypes | UseClientDefault | None = USE_CLIENT_DEFAULT,
        follow_redirects: bool | UseClientDefault = USE_CLIENT_DEFAULT,
        timeout: TimeoutTypes | UseClientDefault = USE_CLIENT_DEFAULT,
        extensions: RequestExtensions | None = None,
    ) -> httpx.Response:
        url = self._merge_url(url)
        redirect: bool | UseClientDefault = USE_CLIENT_DEFAULT
        if follow_redirects is not None:
            redirect = follow_redirects

        return await super().request(
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

    async def get(self, url: URLTypes, **kwargs: Any) -> httpx.Response:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: URLTypes, **kwargs: Any) -> httpx.Response:
        return await self.request("POST", url, **kwargs)

    async def put(self, url: URLTypes, **kwargs: Any) -> httpx.Response:
        return await self.request("PUT", url, **kwargs)

    async def patch(self, url: URLTypes, **kwargs: Any) -> httpx.Response:
        return await self.request("PATCH", url, **kwargs)

    async def delete(self, url: URLTypes, **kwargs: Any) -> httpx.Response:
        return await self.request("DELETE", url, **kwargs)

    async def head(self, url: URLTypes, **kwargs: Any) -> httpx.Response:
        return await self.request("HEAD", url, **kwargs)

    async def options(self, url: URLTypes, **kwargs: Any) -> httpx.Response:
        return await self.request("OPTIONS", url, **kwargs)

    async def websocket_connect(
        self,
        url: str,
        subprotocols: Sequence[str] | None = None,
        **kwargs: Any,
    ) -> WebSocketTestSession:
        url = urljoin("ws://testserver", url)
        headers = self._prepare_websocket_headers(subprotocols, **kwargs)
        kwargs["headers"] = headers
        try:
            await super().request("GET", url, **kwargs)
        except UpgradeException as exc:
            return exc.session
        else:
            raise RuntimeError("Expected WebSocket upgrade")

    def _prepare_websocket_headers(
        self,
        subprotocols: Sequence[str] | None = None,
        **kwargs: dict[str, Any],
    ) -> dict[str, str]:
        raw = kwargs.get("headers", {})
        headers: dict[str, str] = (
            dict(httpx.Headers(raw).items())
            if not isinstance(raw, dict)
            else {str(k): str(v) for k, v in raw.items()}
        )
        headers.setdefault("connection", "upgrade")
        headers.setdefault("sec-websocket-key", "testserver==")
        headers.setdefault("sec-websocket-version", "13")
        if subprotocols is not None:
            headers.setdefault("sec-websocket-protocol", ", ".join(subprotocols))
        kwargs["headers"] = headers
        return headers

    async def __aenter__(self) -> AsyncTestClient:
        self._tg = await anyio.create_task_group().__aenter__()
        send1: ObjectSendStream[Any]
        receive1: ObjectReceiveStream[Any]
        send2: ObjectSendStream[Any]
        receive2: ObjectReceiveStream[Any]

        send1, receive1 = anyio.create_memory_object_stream[Any](math.inf)
        send2, receive2 = anyio.create_memory_object_stream[Any](math.inf)
        self.stream_send = StapledObjectStream(send1, receive1)
        self.stream_receive = StapledObjectStream(send2, receive2)
        self.task = await self._tg.start(self._lifespan_runner)
        await self.wait_startup()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None = None,
        exc_value: BaseException | None = None,
        traceback: TracebackType | None = None,
    ) -> None:
        await self.wait_shutdown()
        await self._tg.__aexit__(exc_type, exc_value, traceback)

    async def _lifespan_runner(
        self, *, task_status: TaskStatus = anyio.TASK_STATUS_IGNORED
    ) -> None:
        task_status.started()
        await self.lifespan()

    async def lifespan(self) -> None:
        scope = {"type": "lifespan", "state": self.app_state}
        try:
            await self.app(scope, self.stream_receive.receive, self.stream_send.send)
        finally:
            with contextlib.suppress(anyio.ClosedResourceError):
                await self.stream_send.send(None)

    async def wait_startup(self) -> None:
        await self.stream_receive.send({"type": "lifespan.startup"})

        async def receive() -> Any:
            msg = await self.stream_send.receive()
            if msg is None:
                self.task.result()
            return msg

        msg = await receive()
        assert msg["type"] in ("lifespan.startup.complete", "lifespan.startup.failed")
        if msg["type"] == "lifespan.startup.failed":
            await receive()

    async def wait_shutdown(self) -> None:
        async def receive() -> Any:
            msg = await self.stream_send.receive()
            if msg is None:
                self.task.result()
            return msg

        await self.stream_receive.send({"type": "lifespan.shutdown"})
        msg = await receive()
        assert msg["type"] in ("lifespan.shutdown.complete", "lifespan.shutdown.failed")
        if msg["type"] == "lifespan.shutdown.failed":
            await receive()
