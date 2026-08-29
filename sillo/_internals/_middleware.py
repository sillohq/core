from __future__ import annotations

import typing
from collections.abc import AsyncIterable, Callable, Iterator, Mapping, MutableMapping
from typing import Any

import anyio

from sillo.core.helpers.async_helpers import collapse_excgroups
from sillo.core.http.context import ClientDisconnect, HttpContext
from sillo.core.http.response import (
    BaseResponse,
)
from sillo.types import ASGIApp, Message, MiddlewareType, Receive, Scope, Send
from sillo.websockets import WebSocketContext

RequestResponseEndpoint = typing.Callable[[], typing.Awaitable[BaseResponse]]

T = typing.TypeVar("T")

AsyncContentStream = AsyncIterable[str | bytes | memoryview | MutableMapping[str, Any]]

MiddlewareFactory = Callable[..., ASGIApp]


class DefineMiddleware:
    """Container that pairs a middleware factory with its positional and keyword arguments.

    This class acts as a deferred middleware descriptor. It stores the middleware
    class (or factory callable) together with the arguments that should be passed
    when the middleware is instantiated. The application iterates over a list of
    ``DefineMiddleware`` instances to build the middleware stack at startup.

    Attributes:
        cls: The middleware factory or class to be instantiated.
        args: Positional arguments forwarded to the middleware constructor.
        kwargs: Keyword arguments forwarded to the middleware constructor.
    """

    def __init__(
        self,
        cls: MiddlewareFactory,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialise the descriptor with a middleware factory and its arguments.

        Stores the middleware class together with any positional and keyword
        arguments that should be forwarded when the middleware is later
        instantiated by the application stack builder.

        Args:
            cls: A callable that produces an ASGI application when invoked with
                the remaining arguments. Typically a middleware class.
            *args: Positional arguments forwarded to ``cls`` at instantiation.
            **kwargs: Keyword arguments forwarded to ``cls`` at instantiation.
        """
        self.cls = cls
        self.args = args
        self.kwargs = kwargs

    def __iter__(self) -> Iterator[Any]:
        """Yield the middleware components as a three-element tuple.

        Allows the instance to be unpacked into ``(cls, args, kwargs)``, which
        is the format expected by the application's middleware stack builder.

        Returns:
            An iterator over ``(cls, args, kwargs)`` where ``cls`` is the
            middleware factory, ``args`` is a tuple of positional arguments,
            and ``kwargs`` is a dictionary of keyword arguments.
        """
        as_tuple = (self.cls, self.args, self.kwargs)
        return iter(as_tuple)

    def __repr__(self) -> str:
        """Return a developer-friendly string representation of this descriptor.

        The representation includes the middleware class name, all positional
        arguments, and all keyword arguments so that the descriptor can be
        identified at a glance during debugging or logging.

        Returns:
            A string in the form ``DefineMiddleware(MiddlewareName, arg1, ...,
            key=value, ...)`` suitable for debugging output.
        """
        class_name = self.__class__.__name__
        args_strings = [f"{value!r}" for value in self.args]
        option_strings = [f"{key}={value!r}" for key, value in self.kwargs.items()]
        name = getattr(self.cls, "__name__", "")
        args_repr = ", ".join([name] + args_strings + option_strings)
        return f"{class_name}({args_repr})"


class _CachedRequest(HttpContext):
    """A request subclass that caches the body for dispatch-based middleware.

    If the user calls ``HttpContext.body()`` from their dispatch function we cache
    the entire request body in memory and pass that to downstream middleware,
    but if they call ``HttpContext.stream()`` then all we do is send an empty body
    so that downstream things don't hang forever.

    The class manages three internal states for the wrapped receive callable:
    disconnected, consumed-but-not-disconnected, and not-yet-consumed. Each
    state determines how subsequent calls to ``wrapped_receive`` behave when
    communicating with the downstream ASGI application.

    Attributes:
        _wrapped_rcv_disconnected: Whether a disconnect has already been sent
            to the downstream application.
        _wrapped_rcv_consumed: Whether the request body has been fully
            consumed by the dispatch function.
        _wrapped_rc_stream: The async iterator over the raw request body
            chunks, created at initialisation time.
    """

    def __init__(self, scope: Scope, receive: Receive):
        """Initialise the cached request with ASGI scope and receive callable.

        Sets up internal state tracking flags and creates the initial stream
        iterator from the parent ``HttpContext`` class so that body chunks can be
        lazily consumed by the dispatch middleware.

        Args:
            scope: The ASGI connection scope dictionary containing metadata
                about the incoming HTTP request such as headers, path, and
                query string.
            receive: An ASGI receive callable that yields messages from the
                client, used to read the request body incrementally.
        """
        super().__init__(scope, receive)
        self._wrapped_rcv_disconnected = False
        self._wrapped_rcv_consumed = False
        self._wrapped_rc_stream = self.stream()

    async def wrapped_receive(self) -> Message:
        """Return the next ASGI message for the downstream application.

        Manages three internal states to control how request body data is
        forwarded to the downstream ASGI application. When the body has been
        cached via ``body()``, it returns the cached bytes immediately. When
        the stream has been consumed, it returns an empty body. Otherwise it
        reads the next chunk from the underlying stream.

        The method also handles client disconnection by tracking whether a
        disconnect message has already been forwarded, preventing duplicate
        disconnect signals from being sent to the downstream application.

        Returns:
            An ASGI message dictionary. Either an ``http.request`` message
            containing a body chunk with a ``more_body`` flag, or an
            ``http.disconnect`` message when the client has disconnected.

        Raises:
            RuntimeError: If an unexpected message type is received after the
                stream has been consumed and the message is not a disconnect.
        """
        # wrapped_rcv state 1: disconnected
        if self._wrapped_rcv_disconnected:
            # we've already sent a disconnect to the downstream app
            # we don't need to wait to get another one
            # (although most ASGI servers will just keep sending it)
            return {"type": "http.disconnect"}
        # wrapped_rcv state 1: consumed but not yet disconnected
        if self._wrapped_rcv_consumed:
            # since the downstream app has consumed us all that is left
            # is to send it a disconnect
            if self._is_disconnected:
                # the middleware has already seen the disconnect
                # since we know the client is disconnected no need to wait
                # for the message
                self._wrapped_rcv_disconnected = True
                return {"type": "http.disconnect"}
            # we don't know yet if the client is disconnected or not
            # so we'll wait until we get that message
            msg = await self.receive()
            if msg["type"] != "http.disconnect":  # pragma: no cover
                # at this point a disconnect is all that we should be receiving
                # if we get something else, things went wrong somewhere
                raise RuntimeError(f"Unexpected message received: {msg['type']}")
            self._wrapped_rcv_disconnected = True
            return msg

        # wrapped_rcv state 3: not yet consumed
        if getattr(self, "_body", None) is not None:
            # body() was called, we return it even if the client disconnected
            self._wrapped_rcv_consumed = True
            return {
                "type": "http.request",
                "body": self._body,
                "more_body": False,
            }
        elif self._stream_consumed:
            # stream() was called to completion
            # return an empty body so that downstream apps don't hang
            # waiting for a disconnect
            self._wrapped_rcv_consumed = True
            return {
                "type": "http.request",
                "body": b"",
                "more_body": False,
            }
        else:
            # body() was never called and stream() wasn't consumed
            try:
                stream = self.stream()
                chunk = await stream.__anext__()
                self._wrapped_rcv_consumed = self._stream_consumed
                return {
                    "type": "http.request",
                    "body": chunk,
                    "more_body": not self._stream_consumed,
                }
            except ClientDisconnect:
                self._wrapped_rcv_disconnected = True
                return {"type": "http.disconnect"}


class ASGIRequestResponseBridge:
    """Bridges dispatch-style middleware into the ASGI application stack.

    This class wraps an inner ASGI application and a dispatch function that
    follows the request/response middleware pattern. It intercepts HTTP
    requests, creates a cached request object, and uses an in-memory stream
    to shuttle response data between the dispatch function and the inner
    application. Non-HTTP scopes (e.g. websocket, lifespan) are forwarded
    directly to the inner application without interception.

    Attributes:
        app: The inner ASGI application to delegate to.
        dispatch_func: The dispatch middleware function that receives the
            the context and a ``call_next`` callable.
    """

    def __init__(self, app: ASGIApp, dispatch: MiddlewareType) -> None:
        """Initialise the bridge with an inner app and dispatch function.

        Args:
            app: The inner ASGI application that will handle the actual
                request processing after the dispatch middleware runs.
            dispatch: A middleware function conforming to the dispatch
                pattern, accepting ``(ctx, call_next)`` and
                returning an awaitable response.
        """
        self.app = app
        self.dispatch_func = dispatch

    def __str__(self) -> str:
        """Return a string representation of the bridge instance.

        Returns:
            A human-readable string showing the inner app and dispatch
            function references for debugging purposes.
        """
        return f"ASGIRequestResponseBridge({self.app!r}, {self.dispatch_func!r})"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Handle an incoming ASGI connection by bridging dispatch middleware.

        For non-HTTP scopes the call is forwarded directly to the inner app.
        For HTTP scopes, a ``_CachedRequest`` context is created along with an
        in-memory object stream. The dispatch function is invoked with that
        context and a ``call_next`` closure that runs the inner app in a
        background task, streaming the response back through the memory
        channel.

        Args:
            scope: The ASGI connection scope dictionary describing the
                connection type and metadata.
            receive: The ASGI receive callable for reading incoming messages.
            send: The ASGI send callable for transmitting outgoing messages.
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        ctx = _CachedRequest(scope, receive)
        wrapped_receive = ctx.wrapped_receive
        response_sent = anyio.Event()

        async def call_next(*_):
            """Invoke the inner application and return its response as a stream.

            Runs the inner ASGI application inside a background task and
            returns a ``_StreamingResponse`` that replays the response
            headers and body chunks received through the in-memory stream.
            Handles debug info messages, client disconnection, and exception
            propagation from the inner application.

            Returns:
                A ``_StreamingResponse`` instance containing the status code,
                headers, and body stream from the inner application.

            Raises:
                RuntimeError: If the client disconnects before the inner app
                    sends a response, or if the inner app raises no exception
                    but the stream ends prematurely.
                Exception: Re-raises any exception caught from the inner
                    application during request processing.
            """
            app_exc: Exception | None = None

            async def receive_or_disconnect() -> Message:
                """Return the next message or a disconnect if the response is sent.

                Races the wrapped receive callable against the ``response_sent``
                event so that the inner application receives a disconnect
                signal once the middleware has finished sending the response.

                Returns:
                    An ASGI message dictionary, either from the underlying
                    receive callable or a synthetic ``http.disconnect``
                    message if the response has already been sent.
                """
                if response_sent.is_set():
                    return {"type": "http.disconnect"}
                async with anyio.create_task_group() as task_group:

                    async def wrap(
                        func: typing.Callable[[], typing.Awaitable[T]],
                    ) -> T:
                        """Await a callable then cancel the sibling task in the group.

                        Args:
                            func: A zero-argument async callable to execute.

                        Returns:
                            The return value of the awaited callable.
                        """
                        result = await func()
                        task_group.cancel_scope.cancel()
                        return result

                    task_group.start_soon(wrap, response_sent.wait)
                    message = await wrap(wrapped_receive)
                if response_sent.is_set():
                    return {"type": "http.disconnect"}
                return message

            async def send_no_error(message: Message) -> None:
                """Send an ASGI message, raising on broken stream resources.

                Args:
                    message: The ASGI message dictionary to send through the
                        in-memory stream to the dispatch function.

                Raises:
                    RuntimeError: If the send stream has been closed or
                        broken, indicating the response was not properly
                        returned by the dispatch function.
                """
                try:
                    await send_stream.send(message)
                except anyio.BrokenResourceError:
                    raise RuntimeError("No response returned")

            async def coro() -> None:
                """Run the inner ASGI application and capture any exception.

                Executes the inner application within a context-managed send
                stream, catching and storing any exception so it can be
                re-raised in the dispatch function's task after the body
                stream has been fully consumed.
                """
                nonlocal app_exc
                with send_stream:
                    try:
                        # Everything downstream reads the body through this
                        # callable, and it replays what ``_CachedRequest``
                        # buffered rather than pulling from the wire.
                        # Announcing it lets ``HttpContext`` tell "the body is
                        # gone" apart from "the body is being replayed" —
                        # without it, a dispatch middleware peeking at the body
                        # would leave the handler unable to read it.
                        scope["_sillo_body_replay"] = receive_or_disconnect
                        await self.app(scope, receive_or_disconnect, send_no_error)
                    except Exception as exc:
                        app_exc = exc

            task_group.start_soon(coro)
            try:
                message = await recv_stream.receive()
                info = message.get("info", None)
                if message["type"] == "http.response.debug" and info is not None:
                    message = await recv_stream.receive()
            except anyio.EndOfStream:
                if app_exc is not None:
                    raise app_exc
                raise RuntimeError("Client disconnected before response was sent")
            assert message["type"] == "http.response.start"

            async def body_stream() -> typing.AsyncGenerator[bytes, None]:
                """Yield response body chunks from the in-memory receive stream.

                Iterates over messages from the receive stream, yielding body
                byte strings until a message with ``more_body`` set to
                ``False`` is encountered. Re-raises any exception captured
                from the inner application after the body is fully consumed.

                Yields:
                    Byte strings containing portions of the HTTP response
                    body as forwarded by the inner ASGI application.

                Raises:
                    Exception: Re-raises any exception that occurred in the
                        inner application during response generation.
                """
                async for message in recv_stream:
                    assert message["type"] == "http.response.body"
                    body = message.get("body", b"")
                    if body:
                        yield body
                    if not message.get("more_body", False):
                        break
                if app_exc is not None:
                    raise app_exc

            response_object = _StreamingResponse(
                content=body_stream(),
                status_code=message["status"],
            )
            response_object.raw_headers = message["headers"]
            return response_object

        streams = anyio.create_memory_object_stream()
        send_stream, recv_stream = streams
        with recv_stream, send_stream, collapse_excgroups():
            async with anyio.create_task_group() as task_group:
                returned_response = await self.dispatch_func(ctx, call_next)
                await returned_response(scope, wrapped_receive, send)
                response_sent.set()
                recv_stream.close()


class _StreamingResponse(BaseResponse):
    """A response that streams its body content from an async iterable.

    Unlike ``BaseResponse`` which holds the full body in memory, this response
    class consumes an async content stream chunk by chunk, sending each chunk
    as a separate ASGI ``http.response.body`` message. This enables efficient
    handling of large responses or responses whose content is generated
    incrementally by the inner application.

    Optionally supports sending a debug info message before the response
    start, and handles both raw byte chunks and ASGI message dictionaries
    (for features like ``pathsend``) within the content stream.

    Attributes:
        info: Optional debug information dictionary to send before the
            response start message.
        content_iterator: The async iterable yielding body chunks or ASGI
            message dictionaries.
        status_code: The HTTP status code for the response.
        media_type: Optional media type string for the Content-Type header.
    """

    def __init__(
        self,
        content: AsyncContentStream,
        status_code: int = 200,
        headers: Mapping[str, str] | None = None,
        media_type: str | None = None,
        info: Mapping[str, Any] | None = None,
    ) -> None:
        """Initialise a streaming response with an async content source.

        Args:
            content: An async iterable yielding body chunks as strings, bytes,
                memoryview objects, or ASGI message dictionaries.
            status_code: The HTTP status code to send in the response start
                message. Defaults to 200.
            headers: An optional mapping of HTTP header names to values. If
                ``None``, an empty header set is used.
            media_type: An optional media type string for the Content-Type
                response header.
            info: An optional dictionary of debug information to send as an
                ``http.response.debug`` message before the response start.
        """
        self.info = info
        self.content_iterator = content
        self.status_code = status_code
        self.media_type = media_type

        super().__init__(headers=dict(headers or {}), status_code=status_code)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Send the streaming response through the ASGI send callable.

        Sends the response in three phases: an optional debug info message,
        the response start message with status and headers, and then the body
        chunks from the content iterator. Each body chunk is sent as a
        separate ``http.response.body`` message with ``more_body`` set to
        ``True``. A final empty body message with ``more_body`` set to
        ``False`` is sent to signal the end of the response, unless the
        content stream contained ASGI message dictionaries.

        Args:
            scope: The ASGI connection scope dictionary.
            receive: The ASGI receive callable (unused by this response).
            send: The ASGI send callable used to transmit all response
                messages to the client.
        """
        if self.info is not None:
            await send({"type": "http.response.debug", "info": self.info})
        await send(
            {
                "type": "http.response.start",
                "status": self.status_code,
                "headers": self.raw_headers,
            }
        )

        should_close_body = True
        async for chunk in self.content_iterator:
            if isinstance(chunk, dict):
                # We got an ASGI message which is not response body (eg: pathsend)
                should_close_body = False
                await send(chunk)
                continue
            await send({"type": "http.response.body", "body": chunk, "more_body": True})

        if should_close_body:
            await send({"type": "http.response.body", "body": b"", "more_body": False})


WebSocketDispatchFunction = typing.Callable[
    ["WebSocketContext", typing.Coroutine[None, None, typing.Any]], typing.Awaitable[None]
]


def wrap_middleware(middleware_function: MiddlewareType) -> DefineMiddleware:
    """Wrap a dispatch-style middleware function into a ``DefineMiddleware`` instance.

    Creates a ``DefineMiddleware`` descriptor that pairs the
    ``ASGIRequestResponseBridge`` class with the given dispatch middleware
    function. This allows the middleware to be added to the application's
    middleware stack in the standard format expected by the framework.

    Args:
        middleware_function: A dispatch-style middleware callable that accepts
            ``(ctx, call_next)`` and returns an awaitable
            response object.

    Returns:
        A ``DefineMiddleware`` instance wrapping the
        ``ASGIRequestResponseBridge`` with the provided dispatch function
        bound as the ``dispatch`` keyword argument.
    """
    return DefineMiddleware(ASGIRequestResponseBridge, dispatch=middleware_function)
