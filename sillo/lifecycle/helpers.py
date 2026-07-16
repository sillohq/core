from __future__ import annotations

import uuid
from typing import Optional

from sillo.http import Request, Response


def generate_request_id() -> str:
    return str(uuid.uuid4())


def get_request_id_from_header(
    request: Request, header_name: str = "X-Request-ID"
) -> Optional[str]:
    return request.headers.get(header_name)


def set_request_id_header(
    response: Response, request_id: str, header_name: str = "X-Request-ID"
) -> None:
    response.set_header(header_name, request_id, overide=True)


def get_or_generate_request_id(
    request: Request, header_name: str = "X-Request-ID"
) -> str:
    request_id = get_request_id_from_header(request, header_name)
    if not request_id:
        request_id = generate_request_id()
    return request_id


def validate_request_id(request_id: str) -> bool:
    try:
        uuid.UUID(request_id)
        return True
    except (ValueError, TypeError):
        return False


def store_request_id_in_request(
    request: Request, request_id: str, attribute_name: str = "request_id"
) -> None:
    request.state.update({attribute_name: request_id})


def get_request_id_from_request(
    request: Request, attribute_name: str = "request_id"
) -> Optional[str]:
    return getattr(request.state, attribute_name, None)
