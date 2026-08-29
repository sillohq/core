from __future__ import annotations

from typing import Any

from sillo.core.http import HttpContext
from sillo.middleware.base import BaseMiddleware

from .helpers import (
    generate_request_id,
    get_or_generate_request_id,
    get_request_id_from_header,
    set_request_id_header,
    store_request_id_in_request,
)


class RequestIdMiddleware(BaseMiddleware):
    """Middleware that manages request ID generation and propagation.

    Automatically assigns a unique request ID to each incoming request,
    either by reading an existing ID from a configurable header or by
    generating a fresh UUID4. The ID is stored on the request state
    object and echoed back in the response header for client-side
    tracing and log correlation.

    Supports forced regeneration (ignoring client-supplied IDs),
    optional response header inclusion, and configurable attribute
    names for request state storage.
    """

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
        """Initialize the RequestIdMiddleware with tracing configuration.

        Configures how request IDs are sourced, stored, and propagated
        through the request/response pipeline. All parameters are
        keyword-only to prevent positional argument misuse.

        Args:
            header_name (str, optional): The HTTP header name used
                for reading and writing the request ID. Defaults to
                ``"X-Request-ID"``.
            force_generate (bool, optional): When ``True``, always
                generate a new UUID4 and ignore any client-supplied
                header value. Defaults to ``False``.
            store_in_request (bool, optional): When ``True``, persist
                the request ID on ``request.state`` for downstream
                access. Defaults to ``True``.
            request_attribute_name (str, optional): The attribute
                name used when storing the ID on ``request.state``.
                Defaults to ``"request_id"``.
            include_in_response (bool, optional): When ``True``, set
                the request ID as a header on the outgoing response.
                Defaults to ``True``.
            **kwargs: Additional keyword arguments forwarded to the
                ``BaseMiddleware`` parent class.

        Returns:
            None.

        Raises:
            None.
        """
        super().__init__(**kwargs)
        self.header_name = header_name
        self.force_generate = force_generate
        self.store_in_request = store_in_request
        self.request_attribute_name = request_attribute_name
        self.include_in_response = include_in_response

    async def dispatch(
        self,
        ctx: HttpContext,
        call_next: Any,
    ) -> Any:
        """Assign a request ID, then guarantee it on the outgoing response.

        Determines the request ID by either forcing a fresh UUID4
        generation or extracting/generating one from the request
        headers. Optionally stores the ID on the request state and
        sets it as a response header before delegating to the next
        middleware or handler in the chain.

        Args:
            ctx (HttpContext): The context to inspect and annotate with a
                request ID.
            call_next (Any): An awaitable callable representing the
                next middleware or route handler in the pipeline.

        Returns:
            Any: The return value of ``call_next()``, typically the
                response produced by downstream handlers.

        Raises:
            None.
        """
        if self.force_generate:
            request_id = generate_request_id()
        else:
            request_id = get_request_id_from_header(ctx, self.header_name)
            if not request_id:
                request_id = get_or_generate_request_id(ctx, self.header_name)
        self.request_id = request_id

        if self.store_in_request:
            store_request_id_in_request(
                ctx, request_id, self.request_attribute_name
            )

        response = await call_next()

        if response is not None and request_id and self.include_in_response:
            if not response.headers.get(self.header_name):
                set_request_id_header(response, request_id, self.header_name)

        return response


def RequestId(
    header_name: str = "X-Request-ID",
    force_generate: bool = False,
    store_in_request: bool = True,
    request_attribute_name: str = "request_id",
    include_in_response: bool = True,
) -> RequestIdMiddleware:
    """Factory function that creates a configured RequestIdMiddleware instance.

    Convenience wrapper around ``RequestIdMiddleware`` that provides a
    cleaner API for registering request ID tracking middleware. Accepts
    the same configuration parameters as the middleware constructor
    and returns a fully initialized instance ready for use.

    Args:
        header_name (str, optional): The HTTP header name for reading
            and writing the request ID. Defaults to
            ``"X-Request-ID"``.
        force_generate (bool, optional): When ``True``, always
            generate a new UUID4 regardless of client headers.
            Defaults to ``False``.
        store_in_request (bool, optional): When ``True``, persist the
            request ID on ``request.state``. Defaults to ``True``.
        request_attribute_name (str, optional): The attribute name
            used on ``request.state`` for storage. Defaults to
            ``"request_id"``.
        include_in_response (bool, optional): When ``True``, include
            the request ID in the response header. Defaults to
            ``True``.

    Returns:
        RequestIdMiddleware: A fully configured middleware instance
            ready to be registered in the middleware pipeline.

    Raises:
        None.
    """
    return RequestIdMiddleware(
        header_name=header_name,
        force_generate=force_generate,
        store_in_request=store_in_request,
        request_attribute_name=request_attribute_name,
        include_in_response=include_in_response,
    )
