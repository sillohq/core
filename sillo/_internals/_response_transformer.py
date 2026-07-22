from __future__ import annotations

import typing

from sillo.encoding import jsonable_encoder
from sillo.http.response import BaseResponse, Responder, JSONResponse


def serialize_response(func_result: typing.Any) -> BaseResponse:
    """Convert an arbitrary handler return value into a proper HTTP response.

    Examines the type of the value returned by a route handler and wraps it in
    an appropriate response object. If the value is already a response object
    (``BaseResponse`` or ``Responder``), it is returned unchanged. String
    values are wrapped in a plain-text ``BaseResponse``. All other values are
    first encoded to a JSON-safe representation using ``jsonable_encoder``
    and then wrapped in a ``JSONResponse``.

    This function serves as the bridge between route handler return values and
    the ASGI response protocol, allowing handlers to return plain Python
    objects without manually constructing response instances.

    Args:
        func_result: The value returned by a route handler. Can be a
            ``BaseResponse``, ``Responder``, string, or any JSON-serializable
            Python object including dicts, lists, and dataclass instances.

    Returns:
        A ``BaseResponse`` subclass instance ready to be sent through the ASGI
        send interface. Returns the original object if it is already a
        response, a plain-text response for strings, or a JSON response for
        all other types.
    """
    if isinstance(func_result, (BaseResponse, Responder)):
        return func_result
    encoded = jsonable_encoder(func_result)
    if isinstance(encoded, str):
        return BaseResponse(body=encoded, content_type="text/plain")
    return JSONResponse(content=encoded)
