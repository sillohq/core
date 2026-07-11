from __future__ import annotations

import http
import typing


class HTTPException(Exception):
    def __init__(
        self,
        status_code: int,
        detail: typing.Optional[typing.Any] = None,
        headers: typing.Dict[str, typing.Any] = {},
    ) -> None:
        super().__init__(detail or http.HTTPStatus(status_code).phrase)
        self.status_code = status_code
        self.detail = self.args[0]
        self.headers = headers

    def __str__(self) -> str:
        return f"HTTP {self.status_code}: {self.detail}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.status_code}, {self.detail!r})"


class NotFoundException(HTTPException):
    def __init__(
        self,
        detail: typing.Optional[str] = None,
        headers: typing.Dict[str, typing.Any] = {},
    ) -> None:
        super().__init__(status_code=404, detail=detail or "Not Found", headers=headers)


class WebSocketException(Exception):
    def __init__(self, code: int, reason: typing.Optional[str] = None) -> None:
        super().__init__(reason or "")
        self.code = code
        self.reason = self.args[0]

    def __str__(self) -> str:
        return f"WebSocket {self.code}: {self.reason}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.code}, {self.reason!r})"
