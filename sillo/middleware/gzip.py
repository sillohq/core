"""
implemented from starlette (0.45.3)
"""

import gzip
import io
import typing

from sillo.objects import Headers, MutableHeaders
from sillo.types import ASGIApp, Message, Receive, Scope, Send


class GZipMiddleware:
    """
    Middleware that compresses response bodies using GZip encoding.

    This middleware intercepts HTTP responses and applies GZip compression
    to reduce the size of the response payload sent to the client. It only
    compresses responses for clients that indicate support for GZip encoding
    via the ``Accept-Encoding`` request header. Responses smaller than the
    configured minimum size threshold are sent uncompressed.

    The implementation is based on the Starlette GZip middleware and follows
    the ASGI specification for streaming response compression.
    """

    def __init__(
        self, app: ASGIApp, minimum_size: int = 500, compresslevel: int = 9
    ) -> None:
        """
        Initializes the GZip middleware with compression settings.

        Sets up the middleware with the ASGI application to wrap, the minimum
        response size threshold for compression, and the GZip compression level.
        The compression level controls the trade-off between speed and compression
        ratio, where 1 is fastest and 9 provides the best compression.

        Args:
            app (ASGIApp): The ASGI application instance to wrap with compression.
            minimum_size (int): Minimum response body size in bytes before GZip
                compression is applied. Responses smaller than this threshold
                are sent without compression. Defaults to 500 bytes.
            compresslevel (int): The GZip compression level ranging from 1 (fastest,
                least compression) to 9 (slowest, best compression). Defaults to 9.
        """
        self.app = app
        self.minimum_size = minimum_size
        self.compresslevel = compresslevel

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """
        Processes an incoming ASGI connection and applies GZip if applicable.

        Inspects the connection scope to determine whether this is an HTTP request
        and whether the client advertises support for GZip encoding. If both conditions
        are met, the request is delegated to a ``GZipResponder`` that handles the
        compression of the response body. Otherwise, the request is passed through
        to the wrapped application without modification.

        Args:
            scope (Scope): The ASGI connection scope dictionary containing metadata
                about the incoming request including type, headers, and routing info.
            receive (Receive): An async callable that yields ASGI message dictionaries
                from the client as they arrive over the connection.
            send (Send): An async callable used to transmit ASGI message dictionaries
                back to the client through the server.
        """
        if scope["type"] == "http":  # pragma: no branch
            headers = Headers(scope=scope)
            if "gzip" in headers.get("Accept-Encoding", ""):
                responder = GZipResponder(
                    self.app, self.minimum_size, compresslevel=self.compresslevel
                )
                await responder(scope, receive, send)
                return
        await self.app(scope, receive, send)


class GZipResponder:
    """
    Handles GZip compression of HTTP response bodies within the ASGI pipeline.

    This responder wraps the downstream ASGI application and intercepts response
    messages to apply GZip compression. It supports both single-shot responses and
    streaming responses where the body arrives in multiple chunks. The responder
    manages header modifications including ``Content-Encoding``, ``Content-Length``,
    and ``Vary`` headers to ensure correct client-side decompression.

    The implementation buffers response data and applies compression lazily, only
    sending the initial response headers once the compression strategy has been
    determined based on the response body size.
    """

    def __init__(self, app: ASGIApp, minimum_size: int, compresslevel: int = 9) -> None:
        """
        Initializes the GZip responder with compression parameters.

        Sets up the internal GZip buffer and compression file object, along with
        tracking state for the response lifecycle. The responder maintains state
        about whether headers have been sent and whether the content encoding
        has already been set by a downstream handler.

        Args:
            app (ASGIApp): The downstream ASGI application whose response will
                be compressed before being sent to the client.
            minimum_size (int): The minimum body size in bytes required for GZip
                compression to be applied. Smaller responses bypass compression.
            compresslevel (int): The GZip compression level from 1 to 9 controlling
                the speed versus compression ratio trade-off. Defaults to 9.
        """
        self.app = app
        self.minimum_size = minimum_size
        self.send: Send = unattached_send
        self.initial_message: Message = {}
        self.started = False
        self.content_encoding_set = False
        self.gzip_buffer = io.BytesIO()
        self.gzip_file = gzip.GzipFile(
            mode="wb", fileobj=self.gzip_buffer, compresslevel=compresslevel
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """
        Invokes the responder to process the ASGI connection with GZip compression.

        Stores the send callable and delegates to the wrapped application while
        intercepting outgoing messages through the ``send_with_gzip`` method.
        The GZip buffer and file objects are managed within a context manager
        to ensure proper cleanup of resources after the response is complete.

        Args:
            scope (Scope): The ASGI connection scope dictionary containing request
                metadata such as type, headers, and routing information.
            receive (Receive): An async callable that yields incoming ASGI messages
                from the client over the connection.
            send (Send): An async callable for transmitting outgoing ASGI messages
                back to the client through the server.
        """
        self.send = send
        with self.gzip_buffer, self.gzip_file:
            await self.app(scope, receive, self.send_with_gzip)

    async def send_with_gzip(self, message: Message) -> None:
        """
        Processes an outgoing ASGI message and applies GZip compression as needed.

        This method intercepts each ASGI message in the response lifecycle and
        determines the appropriate compression strategy. For the initial response
        start message, it stores the message and checks whether content encoding
        is already set. For body messages, it handles four cases: pre-encoded
        content that should pass through unchanged, small single-shot responses
        that skip compression, complete single-shot responses that get compressed,
        and streaming responses that are compressed incrementally across chunks.

        Args:
            message (Message): An ASGI message dictionary representing either an
                ``http.response.start`` or ``http.response.body`` event in the
                response lifecycle.
        """
        message_type = message["type"]
        if message_type == "http.response.start":
            # Don't send the initial message until we've determined how to
            # modify the outgoing headers correctly.
            self.initial_message = message
            headers = Headers(raw=self.initial_message["headers"])
            self.content_encoding_set = "content-encoding" in headers
        elif message_type == "http.response.body" and self.content_encoding_set:
            if not self.started:
                self.started = True
                await self.send(self.initial_message)
            await self.send(message)
        elif message_type == "http.response.body" and not self.started:
            self.started = True
            body = message.get("body", b"")
            more_body = message.get("more_body", False)
            if len(body) < self.minimum_size and not more_body:
                # Don't apply GZip to small outgoing responses.
                await self.send(self.initial_message)
                await self.send(message)
            elif not more_body:
                # Standard GZip response.
                self.gzip_file.write(body)
                self.gzip_file.close()
                body = self.gzip_buffer.getvalue()

                headers = MutableHeaders(raw=self.initial_message["headers"])
                headers["Content-Encoding"] = "gzip"
                headers["Content-Length"] = str(len(body))
                headers.add_vary_header("Accept-Encoding")
                message["body"] = body

                await self.send(self.initial_message)
                await self.send(message)
            else:
                # Initial body in streaming GZip response.
                headers = MutableHeaders(raw=self.initial_message["headers"])
                headers["Content-Encoding"] = "gzip"
                headers.add_vary_header("Accept-Encoding")
                del headers["Content-Length"]

                self.gzip_file.write(body)
                message["body"] = self.gzip_buffer.getvalue()
                self.gzip_buffer.seek(0)
                self.gzip_buffer.truncate()

                await self.send(self.initial_message)
                await self.send(message)

        elif message_type == "http.response.body":  # pragma: no branch
            # Remaining body in streaming GZip response.
            body = message.get("body", b"")
            more_body = message.get("more_body", False)

            self.gzip_file.write(body)
            if not more_body:
                self.gzip_file.close()

            message["body"] = self.gzip_buffer.getvalue()
            self.gzip_buffer.seek(0)
            self.gzip_buffer.truncate()

            await self.send(message)


async def unattached_send(message: Message) -> typing.NoReturn:
    """
    Placeholder send callable used before the responder is properly initialized.

    This function serves as a sentinel value for the ``send`` attribute of
    ``GZipResponder`` before it is bound to the actual ASGI send callable during
    the ``__call__`` invocation. If this function is ever invoked, it indicates
    a programming error where messages are being sent before the responder has
    been properly attached to the ASGI connection lifecycle.

    Args:
        message (Message): The ASGI message dictionary that would be sent to the
            client. This parameter is accepted but never used since the function
            always raises an exception.

    Raises:
        RuntimeError: Always raised to indicate that the send awaitable has not
            been properly attached to an active ASGI connection.
    """
    raise RuntimeError("send awaitable not set")  # pragma: no cover
