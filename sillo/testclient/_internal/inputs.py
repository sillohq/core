from __future__ import annotations

from typing import Any, TypedDict

import httpx
from httpx._types import (
    AuthTypes,
    CookieTypes,
    HeaderTypes,
    QueryParamTypes,
    RequestContent,
    RequestFiles,
    TimeoutTypes,
)

from sillo.testclient._internal.types import RequestData


class RequestInputs(TypedDict, total=False):
    """Requestinputs

        Returns:
            [description]

        Raises:
            [description]
    """
    content: RequestContent | None
    data: RequestData | None
    files: RequestFiles | None
    json: Any
    params: QueryParamTypes | None
    headers: HeaderTypes | None
    cookies: CookieTypes | None
    follow_redirects: bool | None
    auth: AuthTypes | httpx._client.UseClientDefault
    timeout: TimeoutTypes | httpx._client.UseClientDefault
    extensions: dict[str, Any] | None


RequestInputsDefaultValues = {
    "content": None,
    "data": None,
    "files": None,
    "json": None,
    "params": None,
    "headers": None,
    "cookies": None,
    "follow_redirects": None,
    "auth": httpx._client.USE_CLIENT_DEFAULT,
    "timeout": httpx._client.USE_CLIENT_DEFAULT,
    "extensions": None,
}
