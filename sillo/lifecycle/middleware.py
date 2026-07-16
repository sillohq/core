from __future__ import annotations

from typing import Any

from sillo.http import Request, Response
from sillo.middleware.base import BaseMiddleware

from .helpers import (
    generate_request_id,
    get_or_generate_request_id,
    get_request_id_from_header,
    set_request_id_header,
    store_request_id_in_request,
)


class RequestIdMiddleware(BaseMiddleware):
    def __init__(
        self,
        *,
        header_name: str = "X-Request-ID",
        force_generate: bool = False,
        store_in_request: bool = True,
        request_attribute_name: str = "request_id",
        include_in_response: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.header_name = header_name
        self.force_generate = force_generate
        self.store_in_request = store_in_request
        self.request_attribute_name = request_attribute_name
        self.include_in_response = include_in_response

    async def process_request(
        self,
        request: Request,
        response: Response,
        call_next: Any,
    ) -> Any:
        response.empty()
        if self.force_generate:
            request_id = generate_request_id()
        else:
            request_id = get_request_id_from_header(request, self.header_name)
            if not request_id:
                request_id = get_or_generate_request_id(request, self.header_name)
        self.request_id = request_id

        if self.store_in_request:
            store_request_id_in_request(
                request, request_id, self.request_attribute_name
            )

        if self.include_in_response:
            set_request_id_header(response, request_id, self.header_name)

        return await call_next()

    async def process_response(
        self,
        request: Request,
        response: Response,
    ) -> Any:
        request_id = self.request_id

        if request_id and self.include_in_response:
            existing_header = response.headers.get(self.header_name)
            if not existing_header:
                set_request_id_header(response, request_id, self.header_name)

        return response


def RequestId(
    header_name: str = "X-Request-ID",
    force_generate: bool = False,
    store_in_request: bool = True,
    request_attribute_name: str = "request_id",
    include_in_response: bool = True,
) -> RequestIdMiddleware:
    return RequestIdMiddleware(
        header_name=header_name,
        force_generate=force_generate,
        store_in_request=store_in_request,
        request_attribute_name=request_attribute_name,
        include_in_response=include_in_response,
    )
