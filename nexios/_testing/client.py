import typing
from typing import TYPE_CHECKING, Any, AsyncIterable, Dict, Iterable, Union

import httpx

from .transport import (
    NexiosAsyncTransport,
)

if TYPE_CHECKING:
    from nexios.application import NexiosApp

_RequestData = typing.Mapping[str, typing.Union[str, typing.Iterable[str], bytes]]


class Client(httpx.AsyncClient):
    __test__ = False

    def __init__(
        self,
        app: "NexiosApp",
        root_path: str = "",
        client: tuple[str, int] = ("testclient", 5000),
        base_url: str = "http://testserver",
        raise_server_exceptions: bool = True,
        cookies: Union[httpx._types.CookieTypes, None] = None,  # type: ignore
        headers: Union[Dict[str, str], None] = None,
        follow_redirects: bool = True,
        max_retries: int = 3,
        timeout: Union[httpx._types.TimeoutTypes, float] = 5.0,  # type: ignore
        log_requests: bool = False,
        app_state: Dict[str, Any] = {},
        **kwargs: Any,
    ) -> None:
        if headers is None:
            headers = {}
        headers.setdefault("user-agent", "testclient")
        transport = NexiosAsyncTransport(
            app=app,
            app_state=app_state,
            raise_app_exceptions=raise_server_exceptions,
            root_path=root_path,
            client=client,
        )
        super().__init__(
            base_url=base_url,
            headers=headers,
            follow_redirects=follow_redirects,
            cookies=cookies,
            timeout=timeout,
            transport=transport,
            **kwargs,
        )

        self.max_retries = max_retries
        self.log_requests = log_requests

    async def handle_request(
        self,
        method: str,
        url: httpx._types.URLTypes,  # type: ignore
        *,
        content: Union[str, bytes, Iterable[bytes], AsyncIterable[bytes], None] = None,  # type: ignore
        data: Union[_RequestData, None] = None,
        files: Union[httpx._types.RequestFiles, None] = None,  # type: ignore
        json: typing.Any = None,
        params: Union[httpx._types.QueryParamTypes, None] = None,  # type: ignore
        headers: Union[httpx._types.HeaderTypes, None] = None,  # type: ignore
        cookies: Union[httpx._types.CookieTypes, None] = None,  # type: ignore
        auth: Union[
            httpx._types.AuthTypes, httpx._client.UseClientDefault
        ] = httpx._client.USE_CLIENT_DEFAULT,  # type: ignore
        follow_redirects: Union[
            bool, httpx._client.UseClientDefault
        ] = httpx._client.USE_CLIENT_DEFAULT,  # type: ignore
        timeout: Union[
            httpx._types.TimeoutTypes, httpx._client.UseClientDefault
        ] = httpx._client.USE_CLIENT_DEFAULT,  # type: ignore
        extensions: Union[Dict[str, typing.Any], None] = None,
    ) -> httpx.Response:
        if cookies:
            self.cookies.update(cookies)

        response = await super().request(
            method,
            url,
            content=content,
            data=data,
            files=files,
            json=json,
            params=params,
            headers=headers,
            auth=auth,
            follow_redirects=follow_redirects,
            timeout=timeout,
            extensions=extensions,
        )
        return response

    async def get(
        self,
        url: httpx._types.URLTypes,
        *,
        params: Union[httpx._types.QueryParamTypes, None] = None,  # type: ignore
        headers: Union[httpx._types.HeaderTypes, None] = None,  # type: ignore
        cookies: Union[httpx._types.CookieTypes, None] = None,  # type: ignore
        auth: Union[
            httpx._types.AuthTypes, httpx._client.UseClientDefault
        ] = httpx._client.USE_CLIENT_DEFAULT,  # type: ignore
        follow_redirects: Union[
            bool, httpx._client.UseClientDefault
        ] = httpx._client.USE_CLIENT_DEFAULT,  # type: ignore
        timeout: Union[
            httpx._types.TimeoutTypes, httpx._client.UseClientDefault
        ] = httpx._client.USE_CLIENT_DEFAULT,  # type: ignore
        extensions: Union[Dict[str, typing.Any], None] = None,
    ) -> httpx.Response:
        return await self.handle_request(
            "GET",
            url,
            params=params,
            headers=headers,
            cookies=cookies,
            auth=auth,
            follow_redirects=follow_redirects,
            timeout=timeout,
            extensions=extensions,
        )

    async def post(
        self,
        url: httpx._types.URLTypes,
        *,
        content: Union[httpx._types.RequestContent, None] = None,
        data: Union[_RequestData, None] = None,
        files: Union[httpx._types.RequestFiles, None] = None,
        json: typing.Any = None,
        params: Union[httpx._types.QueryParamTypes, None] = None,
        headers: Union[httpx._types.HeaderTypes, None] = None,
        cookies: Union[httpx._types.CookieTypes, None] = None,
        auth: Union[
            httpx._types.AuthTypes, httpx._client.UseClientDefault
        ] = httpx._client.USE_CLIENT_DEFAULT,
        follow_redirects: Union[
            bool, httpx._client.UseClientDefault
        ] = httpx._client.USE_CLIENT_DEFAULT,
        timeout: Union[
            httpx._types.TimeoutTypes, httpx._client.UseClientDefault
        ] = httpx._client.USE_CLIENT_DEFAULT,
        extensions: Union[Dict[str, typing.Any], None] = None,
    ) -> httpx.Response:
        return await self.handle_request(
            "POST",
            url,
            content=content,
            data=data,
            files=files,
            json=json,
            params=params,
            headers=headers,
            auth=auth,
            follow_redirects=follow_redirects,
            timeout=timeout,
            extensions=extensions,
        )

    async def __aenter__(self) -> "Client":
        await super().__aenter__()
        return self

    async def __aexit__(self, *args: typing.Any) -> None:
        await super().__aexit__(*args)
