from __future__ import annotations

import typing

from sillo.encoding import jsonable_encoder
from sillo.http.response import BaseResponse, Responder, JSONResponse


def serialize_response(func_result: typing.Any) -> BaseResponse:
    if isinstance(func_result, (BaseResponse, Responder)):
        return func_result
    encoded = jsonable_encoder(func_result)
    if isinstance(encoded, str):
        return BaseResponse(body=encoded, content_type="text/plain")
    return JSONResponse(content=encoded)
