from __future__ import annotations

import asyncio
import json
import typing
from http import cookies as http_cookies
from typing import Any
from urllib.parse import urlencode

import anyio

from sillo.formparser import (
    FormParser,
    MultiPartException,
    MultiPartParser,
    UploadedFile,
)
from sillo.objects import URL, Address, FormData, Headers, QueryParams, State
from sillo.core.helpers.async_helpers import (
    AwaitableOrContextManager,
    AwaitableOrContextManagerWrapper,
)

if typing.TYPE_CHECKING:
    from sillo import silloApp
    from sillo.users import BaseUser
    from sillo.session.session_objects import Session


try:
    from python_multipart.multipart import parse_options_header

except ImportError:
    parse_options_header = None  # ty:ignore[invalid-assignment]

Scope = typing.MutableMapping[str, typing.Any]
Message = typing.MutableMapping[str, typing.Any]

Receive = typing.Callable[[], typing.Awaitable[Message]]
Send = typing.Callable[[Message], typing.Awaitable[None]]
JSONType = typing.Union[
    str, int, float, bool, None, typing.Dict[str, typing.Any], typing.List[typing.Any]
]

SERVER_PUSH_HEADERS_TO_COPY = {
    "accept",
    "accept-encoding",
    "accept-language",
    "cache-control",
    "user-agent",
}


def cookie_parser(cookie_string: str) -> dict[str, str]:
    """Parse a ``Cookie`` HTTP header into a dictionary of key-value pairs.

    Attempts to mimic browser cookie-parsing behavior: browsers and web servers
    frequently disregard the formal specification (RFC 6265) when setting and
    reading cookies, so this implementation handles the common real-world
    scenarios that arise in production traffic.

    The function splits the raw header value on semicolons, trims whitespace
    from each resulting token, and unquotes values using Python's built-in
    ``http.cookies._unquote`` helper.  Tokens without an ``=`` separator are
    treated as values with an empty key, following the Mozilla convention
    documented at https://bugzilla.mozilla.org/show_bug.cgi?id=169091.

    Adapted from Django 3.1.0.  Note: ``SimpleCookie.load`` is intentionally
    avoided because it is based on an outdated spec and rejects many inputs
    that real browsers accept without issue.

    Args:
        cookie_string: The raw ``Cookie`` header value as received from the
            HTTP client.  Must be a non-empty string containing one or more
            semicolon-separated cookie tokens.

    Returns:
        A dictionary mapping cookie names to their unquoted string values.
        Returns an empty dictionary when the input contains no parseable
        cookie tokens.

    Raises:
        AttributeError: If *cookie_string* does not support ``.split()``.
    """
    cookie_dict: dict[str, str] = {}
    for chunk in cookie_string.split(";"):
        if "=" in chunk:
            key, val = chunk.split("=", 1)
        else:
            # Assume an empty name per
            # https://bugzilla.mozilla.org/show_bug.cgi?id=169091
            key, val = "", chunk
        key, val = key.strip(), val.strip()
        if key or val:
            # unquote using Python's algorithm.
            cookie_dict[key] = http_cookies._unquote(val)
    return cookie_dict


class ClientDisconnect(Exception):
    """Exception raised when the HTTP client disconnects during request processing.

    This exception is raised by the request body streaming machinery when the
    ASGI server delivers an ``http.disconnect`` message instead of the expected
    ``http.request`` message.  Handlers and middleware can catch this exception
    to perform cleanup or return an appropriate error response when a client
    aborts the connection mid-request.

    The exception carries no additional payload; its presence alone signals
    that the client terminated the connection before the server finished
    reading the request body.

    Inherits from:
        Exception: Standard Python exception base class.
    """


T = typing.TypeVar("T")


class HTTPConnection(object):
    """Base class for incoming HTTP connections in the ASGI protocol.

    Provides common functionality shared by both the :class:`Request` class
    and WebSocket connection handlers.  Wraps the raw ASGI scope dictionary
    and exposes convenient properties for accessing URL components, headers,
    query parameters, path parameters, cookies, client information, and
    request-scoped state.

    Instances of this class are not created directly; instead, the framework
    instantiates the appropriate subclass (:class:`Request` for HTTP or a
    WebSocket wrapper for upgrade connections) and passes the ASGI scope
    and receive callable through to this base constructor.

    The class implements the mapping protocol for direct scope access,
    allowing ``connection["type"]`` style lookups alongside the richer
    property-based interface.

    Attributes:
        scope: The ASGI scope dictionary containing connection metadata.

    Inherits from:
        object: Python built-in base class.
    """

    def __init__(self, scope: Scope, receive: Receive) -> None:
        """Initialize the HTTP connection from an ASGI scope dictionary.

        Validates that the scope type is either ``"http"`` or ``"websocket"``
        and stores references to the scope and receive callable for later use
        by subclasses and property accessors.  An extensions entry is also
        injected into the scope to advertise support for the
        ``websocket.http.response`` extension.

        Args:
            scope: The ASGI scope dictionary containing connection metadata
                such as type, headers, path, query string, and client address.
            receive: An async callable that yields ASGI messages from the
                client (e.g. ``http.request`` or ``http.disconnect``).

        Returns:
            None: This method initializes the instance in-place.

        Raises:
            AssertionError: If ``scope["type"]`` is neither ``"http"`` nor
                ``"websocket"``.
        """
        assert scope["type"] in ("http", "websocket")
        self.scope = scope
        self.scope.update({"extensions": {"websocket.http.response": {}}})

    def __getitem__(self, key: str) -> typing.Any:
        """Retrieve a value from the underlying ASGI scope by key.

        Provides dictionary-style access to the raw ASGI scope, enabling
        lookups such as ``connection["type"]`` or ``connection["method"]``.
        This is a thin wrapper around the scope dictionary's ``__getitem__``
        method and raises the same exceptions for missing keys.

        Args:
            key: The scope dictionary key to look up.  Common keys include
                ``"type"``, ``"method"``, ``"path"``, and ``"query_string"``.

        Returns:
            The value associated with *key* in the ASGI scope dictionary.

        Raises:
            KeyError: If *key* is not present in the scope dictionary.
        """
        return self.scope[key]

    def __iter__(self) -> typing.Iterator[str]:
        """Iterate over the keys of the underlying ASGI scope dictionary.

        Enables the connection object to be used in ``for`` loops and with
        functions like ``list(connection)`` to obtain all scope keys.  This
        delegates directly to the scope dictionary's ``__iter__`` method,
        yielding keys in insertion order as maintained by the ASGI server.

        Returns:
            An iterator yielding each key (``str``) present in the ASGI
            scope dictionary.

        Raises:
            RuntimeError: If the scope dictionary has been mutated during
                iteration (standard dict behavior).
        """
        return iter(self.scope)

    def __len__(self) -> int:
        """Return the number of entries in the underlying ASGI scope dictionary.

        Delegates to the scope dictionary's ``__len__`` method, returning the
        total count of key-value pairs currently stored in the scope.  This
        includes all standard ASGI keys as well as any framework-injected
        extensions such as ``"state"`` or ``"route_params"``.

        Returns:
            The number of entries (``int``) in the ASGI scope dictionary.

        Raises:
            RuntimeError: If the scope dictionary is in an inconsistent state
                (standard dict behavior, extremely rare in practice).
        """
        return len(self.scope)

    __eq__ = object.__eq__
    __hash__ = object.__hash__

    @property
    def app(self) -> typing.Any:
        """The ASGI application instance that is handling this connection.

        Retrieves the application object from the ASGI scope.  This is
        typically the innermost application in the middleware stack and
        can be used to access application-level configuration or state.

        Returns:
            The ASGI application instance stored in the scope under the
            ``"app"`` key.  The concrete type depends on the framework
            configuration.

        Raises:
            KeyError: If the ``"app"`` key is not present in the scope.
        """
        return self.scope["app"]

    @property
    def base_app(self) -> "silloApp":  # noqa: F821
        """The root ASGI application instance for the sillo framework.

        Retrieves the base application object from the ASGI scope.  This
        is the top-level application instance (``silloApp``) that was
        originally created by the developer, before any middleware wrapping.
        It provides access to framework-level utilities such as URL
        generation via ``url_for``.

        Returns:
            The root ``silloApp`` instance stored in the scope under the
            ``"base_app"`` key.

        Raises:
            KeyError: If the ``"base_app"`` key is not present in the scope.
        """
        return self.scope["base_app"]

    @property
    def url(self) -> URL:
        """The full URL for this request, constructed from the ASGI scope.

        Lazily builds and caches a :class:`URL` object from the scope's
        scheme, server, path, and query string components.  The resulting
        URL represents the complete address the client used to reach the
        server, including any query parameters.

        Returns:
            A :class:`URL` instance representing the full request URL.

        Raises:
            KeyError: If required scope keys (``"scheme"``, ``"server"``,
                ``"path"``) are missing.
        """
        if not hasattr(self, "_url"):  # pragma: no branch
            self._url = URL(scope=self.scope)
        return self._url

    @property
    def base_url(self) -> URL:
        """The base URL (root path) for this request, without path or query.

        Constructs a URL pointing to the application's root path by combining
        the ``app_root_path`` (or ``root_path``) with the server's scheme and
        host.  The query string is cleared and the path is set to the root,
        making this suitable for building absolute URIs via
        :meth:`build_absolute_uri`.

        Returns:
            A :class:`URL` instance representing the application's root URL.

        Raises:
            KeyError: If required scope keys are missing from the ASGI scope.
        """
        if not hasattr(self, "_base_url"):
            base_url_scope = dict(self.scope)
            app_root_path = base_url_scope.get(
                "app_root_path", base_url_scope.get("root_path", "")
            )
            path = app_root_path
            if not path.endswith("/"):
                path += "/"
            base_url_scope["path"] = path
            base_url_scope["query_string"] = b""
            base_url_scope["root_path"] = app_root_path
            self._base_url = URL(scope=base_url_scope)
        return self._base_url

    @property
    def headers(self) -> Headers:
        """The request headers as a case-insensitive mapping.

        Lazily builds and caches a :class:`Headers` object from the raw
        header list in the ASGI scope.  Provides convenient access to
        individual header values via dictionary-style lookups with
        case-insensitive key matching.

        Returns:
            A :class:`Headers` instance wrapping the request's raw headers.

        Raises:
            KeyError: If the ``"headers"`` key is missing from the scope.
        """
        if not hasattr(self, "_headers"):
            self._headers = Headers(scope=self.scope)
        return self._headers

    @property
    def path(self) -> str:
        """The URL path component of the request.

        Extracts the path portion of the request URL from the ASGI scope.
        This does not include the query string or fragment.  The path is
        always a string and may be empty for requests to the root.

        Returns:
            The URL path as a string (e.g. ``"/users/42"``).

        Raises:
            KeyError: If the ``"path"`` key is missing from the scope.
        """
        return self.url.path

    @property
    def query_params(self) -> QueryParams:
        """The URL query parameters parsed from the request's query string.

        Lazily builds and caches a :class:`QueryParams` instance from the
        raw ``query_string`` bytes in the ASGI scope.  Supports multi-value
        parameters and provides dictionary-style access with fallback to
        lists for repeated keys.

        Returns:
            A :class:`QueryParams` instance containing all parsed query
            parameters from the request URL.

        Raises:
            KeyError: If the ``"query_string"`` key is missing from scope.
        """
        if not hasattr(self, "_query_params"):  # pragma: no branch
            self._query_params = QueryParams(self.scope["query_string"])
        return self._query_params

    @property
    def path_params(self) -> dict[str, typing.Any]:
        """The path parameters extracted from the URL route pattern.

        Retrieves the dictionary of path parameters that were matched by
        the router when dispatching the request.  These correspond to the
        named segments in the route pattern (e.g. ``/users/{user_id}``
        yields ``{"user_id": "42"}``).

        Returns:
            A dictionary mapping parameter names to their string values.
            Returns an empty dictionary if no path parameters were matched.

        Raises:
            None: This method does not raise exceptions; it returns an
                empty dict when the ``"route_params"`` key is absent.
        """
        return self.scope.get("route_params", {})

    @property
    def cookies(self) -> dict[str, str]:
        """The cookies sent with this request, parsed from the Cookie header.

        Lazily parses the ``Cookie`` HTTP header using the module-level
        :func:`cookie_parser` function and caches the result.  Returns an
        empty dictionary if no ``Cookie`` header was present in the request.

        Returns:
            A dictionary mapping cookie names to their unquoted string
            values.  Returns an empty dictionary when the header is absent.

        Raises:
            AttributeError: If cookie parsing fails due to unexpected
                header format (propagated from ``cookie_parser``).
        """
        if not hasattr(self, "_cookies"):
            cookies: dict[str, str] = {}
            cookie_header = self.headers.get("cookie")

            if cookie_header:
                cookies = cookie_parser(cookie_header)
            self._cookies = cookies
        return self._cookies

    @property
    def client(self) -> typing.Union[Address, None]:
        """The client address (host, port) for this request.

        Extracts the client's network address from the ASGI scope's
        ``"client"`` key and wraps it in an :class:`Address` named tuple.
        Returns ``None`` if the ASGI server did not provide client
        address information (e.g. for Unix domain sockets).

        Returns:
            An :class:`Address` instance with ``host`` and ``port``
            attributes, or ``None`` if the client address is unavailable.

        Raises:
            None: This method does not raise exceptions; it returns
                ``None`` when the ``"client"`` key is absent.
        """
        host_port = self.scope.get("client")
        if host_port is not None:
            return Address(*host_port)
        return None

    @property
    def state(self) -> State:
        """Request-scoped state for sharing data between middleware and handlers.

        Lazily creates and caches a :class:`State` instance backed by the
        ``"state"`` dictionary in the ASGI scope.  The state is initialized
        with any global state from ``"global_state"`` and can be used to
        pass data between middleware layers and request handlers without
        polluting the scope dictionary directly.

        Returns:
            A :class:`State` instance providing attribute-style access to
            request-scoped key-value pairs.

        Raises:
            None: This method does not raise exceptions; it creates the
                state dict if it does not already exist.
        """
        if not hasattr(self, "_state"):
            # Ensure 'state' has an empty dict if it's not already populated.
            self.scope.setdefault("state", {})
            # Create a state instance with a reference to the dict in which it should
            # store info
            self._state = State(self.scope["state"])
            self._state.update(self.scope.get("global_state", {}))
        return self._state

    @property
    def origin(self):
        """The Origin header value from the request.

        Retrieves the ``Origin`` header, which indicates the origin of the
        request (scheme, host, and port).  This is commonly used for CORS
        validation and security checks.  Returns ``None`` if the header
        is not present.

        Returns:
            The Origin header value as a string, or ``None`` if the header
            was not included in the request.

        Raises:
            None: This method does not raise exceptions.
        """
        return self.headers.get("Origin")

    @property
    def user_agent(self) -> str:
        """The User-Agent header value from the request.

        Retrieves the ``User-Agent`` header, which typically identifies the
        client software, operating system, and vendor.  Returns an empty
        string if the header is not present, making it safe to use in
        string operations without null checks.

        Returns:
            The User-Agent header value as a string, or an empty string
            if the header was not included in the request.

        Raises:
            None: This method does not raise exceptions.
        """
        return self.headers.get("user-agent", "")

    def build_absolute_uri(
        self, path: str = "", query_params: typing.Optional[dict[str, str]] = None
    ) -> str:
        """Build an absolute URI using the base URL and the provided path.

        Constructs a fully-qualified URI by combining the application's base
        URL (scheme, host, and root path) with the given relative path and
        optional query parameters.  Leading slashes on the path are handled
        correctly to avoid double-slash artifacts.

        Args:
            path: A relative path to append to the base URL.  If it starts
                with ``"/"``, it is joined directly; otherwise a ``"/"``
                separator is inserted automatically.  Defaults to ``""``.
            query_params: Optional dictionary of query parameter key-value
                pairs to append as a URL-encoded query string.  Defaults
                to ``None``, meaning no query string is added.

        Returns:
            A fully constructed absolute URI as a string, including scheme,
            host, root path, the provided path, and any query parameters.

        Raises:
            TypeError: If *query_params* is not a dictionary or ``None``.
        """
        base_url = str(self.base_url).rstrip("/")

        if path.startswith("/"):
            uri = f"{base_url}{path}"
        else:
            uri = f"{base_url}/{path}"

        if query_params:
            query_string = urlencode(query_params)
            uri = f"{uri}?{query_string}"

        return uri


async def empty_receive() -> typing.NoReturn:
    """Placeholder receive callable that always raises RuntimeError.

    Used as the default ``receive`` argument when constructing a
    :class:`Request` without a real ASGI receive channel.  This ensures
    that any attempt to read the request body through the default receive
    callable fails immediately with a clear error message rather than
    hanging indefinitely.

    Returns:
        This function never returns; it always raises an exception.

    Raises:
        RuntimeError: Always raised with a message indicating that the
            receive channel has not been made available.
    """
    raise RuntimeError(
        "Cannot receive. No receive channel has been made available."
    )


async def empty_send(message: Message) -> typing.NoReturn:
    """Placeholder send callable that always raises RuntimeError.

    Used as the default ``send`` argument when constructing a
    :class:`Request` without a real ASGI send channel.  This ensures
    that any attempt to send a response through the default send
    callable fails immediately with a clear error message rather than
    silently discarding the data.

    Args:
        message: The ASGI message dictionary that would be sent.  This
            parameter is accepted for signature compatibility but is
            never used since the function always raises.

    Returns:
        This function never returns; it always raises an exception.

    Raises:
        RuntimeError: Always raised with a message indicating that the
            send channel has not been made available.
    """
    raise RuntimeError(
        "Cannot send. No send channel has been made available."
    )


class Request(HTTPConnection):
    """
    HTTP request object providing access to request data and metadata.

    The Request object encapsulates all information about an incoming HTTP request,
    including headers, body, query parameters, path parameters, cookies, and more.
    It provides both synchronous and asynchronous access to request data with
    convenient methods for common operations.

    Key Features:
    - Lazy loading of request body and form data
    - Support for JSON, form data, and file uploads
    - Path and query parameter access
    - Cookie and session management
    - User authentication integration
    - Content type detection and validation

    Examples:
        1. Basic request handling:
        ```python
        @app.post("/users")
        async def create_user(request: Request, response: Response):
            # Access JSON data
            data = await request.json

            # Access path parameters
            user_id = request.path_params.get('id')

            # Access query parameters
            limit = request.query_params.get('limit', '10')

            # Access headers
            auth_header = request.headers.get('Authorization')

            return response.json({"created": True})
        ```

        2. File upload handling:
        ```python
        @app.post("/upload")
        async def upload_file(request: Request, response: Response):
            # Check if request has files
            if not request.has_files:
                return response.json({"error": "No files uploaded"}, status=400)

            # Access uploaded files
            files = await request.files
            uploaded_file = files.get('file')

            if uploaded_file:
                # Save file
                content = await uploaded_file.read()
                with open(f"uploads/{uploaded_file.filename}", "wb") as f:
                    f.write(content)

            return response.json({"uploaded": uploaded_file.filename})
        ```

        3. Form data handling:
        ```python
        @app.post("/contact")
        async def contact_form(request: Request, response: Response):
            # Access form data
            form = await request.form
            name = form.get('name')
            email = form.get('email')
            message = form.get('message')

            # Process form data
            await send_contact_email(name, email, message)

            return response.json({"message": "Contact form submitted"})
        ```
    """

    def __init__(
        self, scope: Scope, receive: Receive = empty_receive, send: Send = empty_send
    ):
        """Initialize a Request from ASGI scope and receive/send callables.

        Validates that the scope type is ``"http"`` and stores references to
        the ASGI receive and send callables for later use by body streaming,
        form parsing, and response sending methods.  Initializes internal
        state flags for stream consumption tracking, disconnection detection,
        and lazy-loaded form data.

        Args:
            scope: The ASGI scope dictionary containing HTTP request metadata
                such as method, path, headers, and query string.
            receive: An async callable that yields ASGI messages from the
                client.  Defaults to :func:`empty_receive` which raises
                RuntimeError if invoked.
            send: An async callable that sends ASGI messages to the client.
                Defaults to :func:`empty_send` which raises RuntimeError if
                invoked.

        Returns:
            None: This method initializes the instance in-place.

        Raises:
            AssertionError: If ``scope["type"]`` is not ``"http"``.
        """
        super().__init__(scope, receive)
        assert scope["type"] == "http"
        self._receive = receive
        self._send = send
        self._stream_consumed = False
        self._is_disconnected = False
        self._form: FormData | Any = None
        self._validated_data = None

    @property
    def method(self) -> str:
        """The HTTP method used for this request.

        Retrieves the HTTP method (e.g. ``"GET"``, ``"POST"``, ``"PUT"``)
        from the ASGI scope.  The method is always returned as an uppercase
        string as specified by the HTTP/1.1 standard.

        Returns:
            The HTTP method as an uppercase string (e.g. ``"GET"``).

        Raises:
            KeyError: If the ``"method"`` key is missing from the scope.
        """
        return self.scope["method"]

    @property
    def receive(self):
        """The ASGI receive callable for this request.

        Returns the async callable that was passed to the constructor, which
        yields ASGI messages from the client.  This is used internally by
        the body streaming machinery and can be accessed directly for custom
        message consumption patterns.

        Returns:
            The ASGI receive callable (``Receive`` type) that yields
            messages from the client connection.

        Raises:
            None: This property does not raise exceptions.
        """
        return self._receive

    @property
    def content_type(self) -> typing.Optional[str]:
        """The Content-Type header value without parameters.

        Extracts the media type portion of the ``Content-Type`` header,
        stripping any parameters such as ``charset`` or ``boundary``.
        Uses ``python-multipart``'s ``parse_options_header`` for robust
        parsing.  Returns ``None`` if the header is not present.

        Returns:
            The content type as a lowercase string (e.g. ``"application/json"``),
            or ``None`` if the ``Content-Type`` header is absent.

        Raises:
            None: This method does not raise exceptions; returns ``None``
                when the header is missing or unparseable.
        """
        content_type_header = self.headers.get("Content-Type")
        if content_type_header is None:
            return None
        content_type, _ = parse_options_header(content_type_header)  # ty: ignore
        return content_type.decode("utf-8") if content_type else None

    async def stream(self) -> typing.AsyncGenerator[bytes, None]:
        """Stream the request body as an async generator of byte chunks.

        Yields chunks of bytes as they are received from the client via the
        ASGI receive callable.  If the body has already been fully read (e.g.
        via the ``body`` property), yields the cached body followed by an
        empty bytes marker.  Raises :class:`ClientDisconnect` if the client
        terminates the connection before the body is fully received.

        Yields:
            Byte chunks (``bytes``) from the request body.  An empty ``b""``
            marker is yielded after the final chunk to signal completion.

        Raises:
            RuntimeError: If the stream has already been consumed by a
                previous call to this method.
            ClientDisconnect: If the client disconnects before the body
                is fully received.
        """
        if hasattr(self, "_body"):
            yield self._body
            yield b""
            return
        if self._stream_consumed:
            raise RuntimeError("Stream consumed")
        while not self._stream_consumed:
            message = await self._receive()
            if message["type"] == "http.request":
                body = message.get("body", b"")
                if not message.get("more_body", False):
                    self._stream_consumed = True
                if body:
                    yield body
            elif message["type"] == "http.disconnect":
                self._is_disconnected = True
                raise ClientDisconnect()
        yield b""

    @property
    async def body(self) -> bytes:
        """The full request body as bytes, reading from the stream if needed.

        Lazily reads and caches the entire request body by consuming the
        :meth:`stream` async generator.  Subsequent accesses return the
        cached value without re-reading from the client.  This is the
        foundation for the ``json``, ``text``, and form parsing properties.

        Returns:
            The complete request body as a ``bytes`` object.  Returns an
            empty ``b""`` if the request has no body.

        Raises:
            RuntimeError: If the underlying stream has already been consumed.
            ClientDisconnect: If the client disconnects during body reading.
        """
        if not hasattr(self, "_body"):
            chunks: list[bytes] = []
            async for chunk in self.stream():
                chunks.append(chunk)
            self._body = b"".join(chunks)
        return self._body

    @property
    async def json(self) -> typing.Dict[str, JSONType]:
        """The request body parsed as a JSON object.

        Lazily reads the request body via the :attr:`body` property and
        parses it as JSON using the standard ``json.loads`` function.
        The parsed result is cached for subsequent accesses.

        Returns:
            A dictionary (or other JSON-compatible structure) representing
            the parsed JSON body.  Values may be ``str``, ``int``, ``float``,
            ``bool``, ``None``, ``dict``, or ``list``.

        Raises:
            json.JSONDecodeError: If the body is not valid JSON.
            RuntimeError: If the underlying stream has already been consumed.
            ClientDisconnect: If the client disconnects during body reading.
        """
        if not hasattr(self, "_json"):
            _body = await self.body
            self._json = json.loads(_body)
        return self._json

    @property
    def validated_data(self) -> typing.Any:
        """The request body validated against the route's request model.

        Returns the validated data that was produced by the route's
        ``request_model`` validation step, if one was configured.  This
        is typically a Pydantic model instance or dictionary containing
        the validated and type-coerced request data.

        Returns:
            The validated request data, or ``None`` if no ``request_model``
            was configured for the route or validation has not yet occurred.

        Raises:
            None: This property does not raise exceptions; returns ``None``
                when validation data is not available.
        """
        return self._validated_data

    @property
    async def text(self) -> str:
        """Read and decode the request body as a text string.

        Lazily reads the request body via the :attr:`body` property and
        decodes it to a string.  Attempts UTF-8 decoding first, falling
        back to Latin-1 if UTF-8 fails.  The decoded result is cached for
        subsequent accesses.

        Returns:
            The request body decoded as a ``str``.  Uses UTF-8 encoding
            when possible, falling back to Latin-1 for non-UTF-8 bodies.

        Raises:
            RuntimeError: If the underlying stream has already been consumed.
            ClientDisconnect: If the client disconnects during body reading.
        """
        if not hasattr(self, "_text"):
            body = await self.body
            try:
                self._text = body.decode("utf-8")
            except UnicodeDecodeError:
                self._text = body.decode("latin-1")
        return self._text

    async def _get_form(
        self,
        *,
        max_files: typing.Optional[int] = 1000,
        max_fields: typing.Optional[int] = 1000,
    ) -> FormData:
        """Parse form data from the request body.

        Lazily parses the request body as form data, supporting both
        ``multipart/form-data`` and ``application/x-www-form-urlencoded``
        content types.  The parsed result is cached in ``self._form`` for
        subsequent accesses.  Requires the ``python-multipart`` library
        to be installed.

        Args:
            max_files: Maximum number of file fields to accept in a
                multipart form.  Defaults to 1000.  Exceeding this limit
                results in an empty form being returned.
            max_fields: Maximum number of non-file form fields to accept.
                Defaults to 1000.  Exceeding this limit results in an
                empty form being returned.

        Returns:
            A :class:`FormData` instance containing the parsed form fields
            and uploaded files.  Returns an empty :class:`FormData` if the
            content type is not a recognized form type.

        Raises:
            AssertionError: If ``python-multipart`` is not installed.
            MultiPartException: If multipart parsing fails (caught internally
                and returns an empty form).
        """
        if self._form is None:
            assert parse_options_header is not None, (
                "The `python-multipart` library must be installed to use form parsing."
            )
            content_type_header = self.headers.get("Content-Type")
            content_type: bytes
            content_type, _ = parse_options_header(content_type_header)
            if content_type == b"multipart/form-data":
                try:
                    multipart_parser = MultiPartParser(
                        self.headers,
                        self.stream(),
                        max_files=max_files,
                        max_fields=max_fields,
                    )
                    self._form = await multipart_parser.parse()
                except MultiPartException as _:
                    self._form = {}
            elif content_type == b"application/x-www-form-urlencoded":
                form_parser = FormParser(self.headers, self.stream())

                self._form = await form_parser.parse()
            else:
                self._form: FormData = FormData()
        return self._form  # ty : ignore[invalid-return-type]

    @property
    def form_data(self) -> AwaitableOrContextManager[FormData]:
        """Context manager and awaitable for accessing parsed form data.

        Returns an :class:`AwaitableOrContextManagerWrapper` that can be
        used either as an awaitable (``await request.form_data``) or as an
        async context manager (``async with request.form_data as form:``).
        Delegates to :meth:`_get_form` for the actual parsing.

        Returns:
            An :class:`AwaitableOrContextManager` wrapping the form parsing
            coroutine, yielding a :class:`FormData` instance.

        Raises:
            AssertionError: If ``python-multipart`` is not installed.
        """
        return AwaitableOrContextManagerWrapper(self._get_form())

    async def close(self) -> None:
        """Close any resources held by the request.

        Releases resources associated with the request, particularly any
        open file handles from uploaded files in multipart form data.
        Should be called when the request processing is complete to ensure
        proper cleanup of temporary files and file descriptors.

        Returns:
            None: This method performs cleanup in-place and returns nothing.

        Raises:
            None: This method does not raise exceptions under normal
                circumstances; errors during file closure are silently
                ignored by the underlying form data implementation.
        """
        if self._form is not None:
            await self._form.close()

    async def is_disconnected(self) -> bool:
        """Check if the client has disconnected from the server.

        Attempts a non-blocking check for an ``http.disconnect`` message
        from the ASGI receive channel.  Uses an immediately-cancelled
        ``anyio.CancelScope`` to ensure the check does not block if no
        message is available.  The result is cached so subsequent calls
        return immediately if a disconnection was previously detected.

        Returns:
            ``True`` if the client has disconnected, ``False`` otherwise.

        Raises:
            None: This method does not raise exceptions; connection errors
                are handled internally and result in ``True`` being returned.
        """
        if not self._is_disconnected:
            message = {}

            # If message isn't immediately available, move on
            with anyio.CancelScope() as cs:
                cs.cancel()
                message = await self._receive()

            if message.get("type") == "http.disconnect":
                self._is_disconnected = True

        return self._is_disconnected

    async def send_push_promise(self, path: str) -> None:
        """Send an HTTP/2 push promise for the given path.

        Sends an ``http.response.push`` ASGI message to the server,
        requesting that the specified path be pushed to the client as a
        server push promise.  Only copies headers that are safe to forward
        (accept, accept-encoding, accept-language, cache-control, user-agent).
        This is a no-op if the ASGI server does not support the
        ``http.response.push`` extension.

        Args:
            path: The URL path to push to the client.  This should be a
                path that the client is likely to request next (e.g. static
                assets referenced by the response body).

        Returns:
            None: This method sends the push promise via the ASGI send
                callable and returns nothing.

        Raises:
            None: This method does not raise exceptions; it silently skips
                the push if the extension is not supported.
        """
        if "http.response.push" in self.scope.get("extensions", {}):
            raw_headers: list[tuple[bytes, bytes]] = []
            for name in SERVER_PUSH_HEADERS_TO_COPY:
                for value in self.headers.getlist(name):
                    raw_headers.append(
                        (name.encode("latin-1"), value.encode("latin-1"))
                    )
            await self._send(
                {"type": "http.response.push", "path": path, "headers": raw_headers}
            )

    @property
    async def files(self) -> typing.Dict[str, UploadedFile]:
        """A dictionary of uploaded files from the request.

        Parses the form data and extracts all fields that represent uploaded
        files (i.e. have a ``filename`` attribute).  If a form field contains
        multiple files, the last file with that key is returned.  The form
        data is lazily parsed on first access.

        Returns:
            A dictionary mapping form field names to :class:`UploadedFile`
            instances.  Returns an empty dictionary if no files were uploaded.

        Raises:
            AssertionError: If ``python-multipart`` is not installed.
        """
        form_data = await self.form_data
        files_dict: typing.Dict[str, typing.Any] = {}
        for key, value in form_data.items():
            if isinstance(value, (list, tuple)):
                for item in value:
                    if hasattr(item, "filename"):
                        files_dict[key] = item
            elif hasattr(value, "filename"):
                files_dict[key] = value
        return files_dict

    @property
    async def form(self) -> FormData:
        """The parsed form data from the request body.

        Lazily parses the request body as form data by delegating to the
        :attr:`form_data` property.  The result is cached for subsequent
        accesses.  Supports both ``multipart/form-data`` and
        ``application/x-www-form-urlencoded`` content types.

        Returns:
            A :class:`FormData` instance containing the parsed form fields
            and uploaded files.

        Raises:
            AssertionError: If ``python-multipart`` is not installed.
        """
        if not hasattr(self, "_form") or self._form is None:
            form_data = await self.form_data
            self._form = form_data
        return self._form

    def valid(self) -> bool:
        """Check if the request has a valid HTTP method and non-empty headers.

        Validates that the request method is one of the standard HTTP methods
        (GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS) and that the headers
        mapping is non-empty.  This provides a basic sanity check for
        well-formed HTTP requests.

        Returns:
            ``True`` if the method is valid and headers are present,
            ``False`` otherwise.

        Raises:
            None: This method does not raise exceptions.
        """
        return self.method in {
            "GET",
            "POST",
            "PUT",
            "DELETE",
            "PATCH",
            "HEAD",
            "OPTIONS",
        } and bool(self.headers)

    @property
    def session(self) -> Session:
        """The session interface for this request.

        Retrieves the session object from the ASGI scope.  Requires the
        session middleware to be installed; raises an assertion error if
        the ``"session"`` key is not present in the scope.

        Returns:
            A :class:`Session` instance providing access to session data
            for the current request.

        Raises:
            AssertionError: If the session middleware is not installed and
                the ``"session"`` key is missing from the scope.
        """
        assert "session" in self.scope.keys(), "No Session Middleware Installed"
        return self.scope["session"]

    @property
    def user(self) -> BaseUser:
        """The authenticated user for this request.

        Retrieves the user object from the ASGI scope.  Requires the
        authentication middleware to be installed; raises a ``ValueError``
        if the ``"user"`` key is not present or is falsy in the scope.

        Returns:
            A :class:`BaseUser` instance representing the authenticated user.

        Raises:
            ValueError: If the authentication middleware is not installed
                or no user is present in the scope.
        """

        user = self.scope.get("user", None)
        if not user:
            raise ValueError("Authentication middleware required to use request.user")
        return user

    def url_for(self, _name: str, **path_params: typing.Dict[str, typing.Any]) -> str:
        """Generate a URL path for the given route name.

        Delegates to the base application's ``url_for`` method to generate
        a URL path by matching the route name and substituting the provided
        path parameters.  This is a convenience wrapper that avoids the need
        to access the base app directly.

        Args:
            _name: The name of the route as defined in the route decorator
                (e.g. ``"get_user"`` for ``@app.get("/users/{id}", name="get_user")``).
            **path_params: Keyword arguments corresponding to the route's
                path parameters (e.g. ``id=42``).

        Returns:
            The generated URL path as a string with path parameters substituted.

        Raises:
            KeyError: If the route name is not found or required path
                parameters are missing.
        """
        return self.base_app.url_for(_name, **path_params)

    def __str__(self) -> str:
        """Return a human-readable string representation of this request.

        Formats the request as ``"<Request METHOD URL>"`` for debugging
        and logging purposes.  The URL includes the full path and query
        string.

        Returns:
            A string in the format ``"<Request GET /path?query>"`` showing
            the HTTP method and full URL.

        Raises:
            None: This method does not raise exceptions.
        """
        return f"<Request {self.method} {self.url}>"

    @property
    def is_ajax(self) -> bool:
        """Check if the request is an AJAX (XMLHttpRequest) request.

        Examines the ``X-Requested-With`` header to determine if the request
        was made via JavaScript's XMLHttpRequest or a compatible library.
        This header is conventionally set to ``"XMLHttpRequest"`` by AJAX
        libraries, though modern fetch-based code may not set it.

        Returns:
            ``True`` if the ``X-Requested-With`` header equals
            ``"xmlhttprequest"`` (case-insensitive), ``False`` otherwise.

        Raises:
            None: This method does not raise exceptions.
        """
        return self.headers.get("x-requested-with", "").lower() == "xmlhttprequest"

    @property
    def is_secure(self) -> bool:
        """Check if the request was made over HTTPS.

        Examines the URL scheme from the ASGI scope to determine if the
        request was transmitted over a secure TLS/SSL connection.  This
        is useful for enforcing security policies such as redirecting
        HTTP traffic to HTTPS.

        Returns:
            ``True`` if the URL scheme is ``"https"``, ``False`` otherwise.

        Raises:
            None: This method does not raise exceptions.
        """
        return self.url.scheme == "https"

    @property
    def accepts_html(self) -> bool:
        """Check if the client accepts HTML responses.

        Examines the ``Accept`` header to determine if the client can
        receive HTML content.  Returns ``True`` if the header contains
        ``"text/html"`` or the wildcard ``"*/*"`` media type.

        Returns:
            ``True`` if the ``Accept`` header includes ``"text/html"`` or
            ``"*/*"``, ``False`` otherwise.

        Raises:
            None: This method does not raise exceptions.
        """
        accept = self.headers.get("accept", "")
        return "text/html" in accept or "*/*" in accept

    @property
    def is_json(self) -> bool:
        """Check if the request content type is JSON.

        Examines the ``Content-Type`` header to determine if the request
        body contains JSON data.  Returns ``True`` if the content type
        includes ``"application/json"``.

        Returns:
            ``True`` if the content type contains ``"application/json"``,
            ``False`` otherwise or if no content type is set.

        Raises:
            None: This method does not raise exceptions.
        """
        content_type = self.content_type
        return content_type is not None and "application/json" in content_type

    @property
    def is_form(self) -> bool:
        """Check if the request contains form data.

        Examines the ``Content-Type`` header to determine if the request
        body contains form-encoded data.  Returns ``True`` if the content
        type starts with ``"application/x-www-form-urlencoded"`` or
        ``"multipart/form-data"``.

        Returns:
            ``True`` if the content type indicates form data, ``False``
            otherwise or if no content type is set.

        Raises:
            None: This method does not raise exceptions.
        """
        content_type = self.content_type
        return content_type is not None and (
            content_type.startswith("application/x-www-form-urlencoded")
            or content_type.startswith("multipart/form-data")
        )

    @property
    def is_multipart(self) -> bool:
        """Check if the request contains multipart form data.

        Examines the ``Content-Type`` header to determine if the request
        body contains multipart form data (typically used for file uploads).
        Returns ``True`` if the content type starts with
        ``"multipart/form-data"``.

        Returns:
            ``True`` if the content type indicates multipart form data,
            ``False`` otherwise or if no content type is set.

        Raises:
            None: This method does not raise exceptions.
        """
        content_type = self.content_type
        return content_type is not None and content_type.startswith(
            "multipart/form-data"
        )

    @property
    def is_urlencoded(self) -> bool:
        """Check if the request contains URL-encoded form data.

        Examines the ``Content-Type`` header to determine if the request
        body contains URL-encoded form data.  Returns ``True`` if the
        content type exactly equals ``"application/x-www-form-urlencoded"``.

        Returns:
            ``True`` if the content type is URL-encoded form data,
            ``False`` otherwise or if no content type is set.

        Raises:
            None: This method does not raise exceptions.
        """
        content_type = self.content_type
        return (
            content_type is not None
            and content_type == "application/x-www-form-urlencoded"
        )

    @property
    def has_cookie(self) -> bool:
        """Check if the request contains any cookies.

        Examines the ``Cookie`` header to determine if the client sent
        any cookies with the request.  Returns ``True`` if the header
        is present and non-empty after stripping whitespace.

        Returns:
            ``True`` if a non-empty ``Cookie`` header is present,
            ``False`` otherwise.

        Raises:
            None: This method does not raise exceptions.
        """
        cookie_header = self.headers.get("cookie")
        return cookie_header is not None and cookie_header.strip() != ""

    @property
    def has_files(self) -> bool:
        """Check if the request contains uploaded files.

        Examines the request to determine if it contains multipart form
        data with file uploads.  For multipart requests, attempts to parse
        the form data and check for fields with a ``filename`` attribute.
        Returns ``False`` if the request is not multipart or if parsing
        fails for any reason.

        Returns:
            ``True`` if the request contains uploaded files, ``False``
            otherwise or if the request is not multipart.

        Raises:
            None: This method does not raise exceptions; all errors during
                form parsing are caught and result in ``False`` being returned.
        """
        try:
            if self.is_multipart:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    return True
                else:
                    form_data = loop.run_until_complete(self.form_data)
                    for value in form_data.values():
                        if hasattr(value, "filename") and value.filename:
                            return True
                    return False
            return False
        except Exception:
            return False

    @property
    def has_body(self) -> bool:
        """Check if the request has a body.

        Determines whether the request likely contains a body by checking
        the ``Content-Length`` header and the HTTP method.  Returns ``True``
        if the content length is greater than zero, or if the method is
        POST, PUT, or PATCH (which typically have bodies).

        Returns:
            ``True`` if the request has a body or is a method that typically
            carries a body, ``False`` otherwise.

        Raises:
            None: This method does not raise exceptions.
        """
        content_length = self.content_length
        if content_length > 0:
            return True

        # For methods that typically have bodies
        if self.method in ("POST", "PUT", "PATCH"):
            return True

        return False

    @property
    def is_authenticated(self) -> bool:
        """Check if the request has an authenticated user.

        Attempts to retrieve the user from the scope and checks if the user
        is authenticated.  Returns ``False`` if no authentication middleware
        is installed or if the user is not authenticated.

        Returns:
            ``True`` if an authenticated user is present, ``False`` otherwise
            or if authentication middleware is not installed.

        Raises:
            None: This method does not raise exceptions; missing middleware
                is handled gracefully by returning ``False``.
        """
        try:
            user = self.user
            return user.is_authenticated
        except ValueError:
            return False

    @property
    def has_session(self) -> bool:
        """Check if session middleware is available for this request.

        Checks whether the ``"session"`` key is present in the ASGI scope,
        indicating that the session middleware has been installed and a
        session object is available for use.

        Returns:
            ``True`` if session middleware is installed and a session is
            available, ``False`` otherwise.

        Raises:
            None: This method does not raise exceptions.
        """
        return "session" in self.scope

    @property
    def accepts_json(self) -> bool:
        """Check if the client accepts JSON responses.

        Examines the ``Accept`` header to determine if the client can
        receive JSON content.  Returns ``True`` if the header contains
        ``"application/json"`` or the wildcard ``"*/*"`` media type.

        Returns:
            ``True`` if the ``Accept`` header includes ``"application/json"``
            or ``"*/*"``, ``False`` otherwise.

        Raises:
            None: This method does not raise exceptions.
        """
        accept = self.headers.get("accept", "")
        return "application/json" in accept or "*/*" in accept

    def get_header(self, key: str, default: typing.Any = None) -> typing.Any:
        """Get a header value with a default if not found.

        Retrieves the value of the specified HTTP header, performing a
        case-insensitive lookup.  Returns the provided default value if
        the header is not present in the request.

        Args:
            key: The header name to look up (case-insensitive).
            default: The value to return if the header is not found.
                Defaults to ``None``.

        Returns:
            The header value as a string, or the *default* value if the
            header is not present.

        Raises:
            None: This method does not raise exceptions.
        """
        return self.headers.get(key.lower()) or default

    def has_header(self, key: str) -> bool:
        """Check if a header exists in the request.

        Performs a case-insensitive check for the presence of the specified
        HTTP header in the request.

        Args:
            key: The header name to check for (case-insensitive).

        Returns:
            ``True`` if the header is present, ``False`` otherwise.

        Raises:
            None: This method does not raise exceptions.
        """
        return key.lower() in self.headers

    @property
    def origin(self) -> str:
        """Get the request's origin URL.

        Returns the ``Origin`` header value if present, otherwise constructs
        the origin from the request's URL scheme and network location.  This
        is useful for CORS validation and security checks.

        Returns:
            The origin URL as a string (e.g. ``"https://example.com"``).

        Raises:
            None: This method does not raise exceptions; falls back to
                constructing the origin from the URL components.
        """
        if "origin" in self.headers:
            return typing.cast(str, self.headers["origin"])
        return f"{self.url.scheme}://{self.url.netloc}"

    @property
    def referrer(self) -> str:
        """Get the request's referrer URL.

        Returns the ``Referer`` header value (note the historical misspelling
        in the HTTP spec).  Returns an empty string if the header is not
        present.

        Returns:
            The referrer URL as a string, or an empty string if the header
            is not present.

        Raises:
            None: This method does not raise exceptions.
        """
        return typing.cast(str, self.headers.get("referer")) or ""

    def get_client_ip(self) -> str:
        """Get the client's IP address, considering proxy headers.

        Extracts the client's IP address by first checking the
        ``X-Forwarded-For`` header (taking the first IP in the chain),
        then the ``X-Real-IP`` header, and finally falling back to the
        direct client address from the ASGI scope.  Returns an empty
        string if no client address is available.

        Returns:
            The client's IP address as a string, or an empty string if
            the address cannot be determined.

        Raises:
            None: This method does not raise exceptions; returns an empty
                string when the client address is unavailable.
        """
        forwarded_for = self.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = self.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        return self.client.host if self.client else ""

    def is_method(self, method: str) -> bool:
        """Check if the request method matches the given method.

        Performs a case-insensitive comparison of the request's HTTP method
        against the provided method string.  This is a convenience method
        for checking the request method without worrying about case.

        Args:
            method: The HTTP method to compare against (e.g. ``"GET"``,
                ``"post"``).  Case-insensitive.

        Returns:
            ``True`` if the request method matches the given method
            (case-insensitive), ``False`` otherwise.

        Raises:
            None: This method does not raise exceptions.
        """
        return self.method.upper() == method.upper()

    @property
    def content_length(self) -> int:
        """The Content-Length header value as an integer.

        Retrieves the ``Content-Length`` header and converts it to an integer.
        Returns 0 if the header is not present, is empty, or cannot be
        converted to an integer.

        Returns:
            The content length as an integer, or 0 if the header is absent
            or invalid.

        Raises:
            None: This method does not raise exceptions; conversion errors
                are caught and result in 0 being returned.
        """
        try:
            return int(self.headers.get("content-length", 0))
        except (ValueError, TypeError):
            return 0

    def get_query_params(
        self, flat: bool = True
    ) -> typing.Union[typing.Dict[str, str], typing.Dict[str, typing.List[str]]]:
        """Get query parameters, optionally flattened to single values.

        Retrieves the query parameters from the request URL.  When *flat*
        is ``True`` (the default), returns only the first value for each
        parameter key.  When *flat* is ``False``, returns all values as
        lists, which is useful for parameters that appear multiple times.

        Args:
            flat: If ``True``, returns only the first value for each
                parameter.  If ``False``, returns all values as lists.
                Defaults to ``True``.

        Returns:
            A dictionary mapping parameter names to their values.  When
            *flat* is ``True``, values are strings.  When *flat* is
            ``False``, values are lists of strings.

        Raises:
            None: This method does not raise exceptions.
        """
        params = dict(self.query_params)
        if flat:
            return {k: v[0] if isinstance(v, list) else v for k, v in params.items()}
        return params
