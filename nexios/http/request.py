from __future__ import annotations
from nexios.auth.users.simple import UnauthenticatedUser

import json
import typing
from http import cookies as http_cookies
from typing import Any
from urllib.parse import urlencode

import anyio

from nexios._internals._formparsers import (
    FormParser,
    MultiPartException,
    MultiPartParser,
    UploadedFile,
)
from nexios.objects import URL, Address, FormData, Headers, QueryParams, State
from nexios.utils.async_helpers import (
    AwaitableOrContextManager,
    AwaitableOrContextManagerWrapper,
)

if typing.TYPE_CHECKING:
    from nexios import NexiosApp
    from nexios.auth.users.base import BaseUser
    from nexios.session.session_objects import Session


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
    """
    This function parses a ``Cookie`` HTTP header into a dict of key/value pairs.

    It attempts to mimic browser cookie parsing behavior: browsers and web servers
    frequently disregard the spec (RFC 6265) when setting and reading cookies,
    so we attempt to suit the common scenarios here.

    This function has been adapted from Django 3.1.0.
    Note: we are explicitly _NOT_ using `SimpleCookie.load` because it is based
    on an outdated spec and will fail on lots of input we want to support
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
    pass


T = typing.TypeVar("T")


class HTTPConnection(object):
    """Base class for incoming HTTP connections.

    Provides common functionality for both Request and WebSocket classes.
    """

    def __init__(self, scope: Scope, receive: Receive) -> None:
        """Initialize HTTP connection from ASGI scope.

        Args:
            scope: ASGI scope dictionary.
            receive: ASGI receive callable.
        """
        assert scope["type"] in ("http", "websocket")
        self.scope = scope
        self.scope.update({"extensions": {"websocket.http.response": {}}})

    def __getitem__(self, key: str) -> typing.Any:
        """Get a value from the scope by key."""
        return self.scope[key]

    def __iter__(self) -> typing.Iterator[str]:
        """Iterate over scope keys."""
        return iter(self.scope)

    def __len__(self) -> int:
        """Return the number of items in scope."""
        return len(self.scope)

    __eq__ = object.__eq__
    __hash__ = object.__hash__

    @property
    def app(self) -> typing.Any:
        """The ASGI application instance."""
        return self.scope["app"]

    @property
    def base_app(self) -> "NexiosApp":  # noqa: F821
        """The root ASGI application instance."""
        return self.scope["base_app"]

    @property
    def url(self) -> URL:
        """The full URL for this request."""
        if not hasattr(self, "_url"):  # pragma: no branch
            self._url = URL(scope=self.scope)
        return self._url

    @property
    def base_url(self) -> URL:
        """The base URL (root path) for this request."""
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
        """The request headers."""
        if not hasattr(self, "_headers"):
            self._headers = Headers(scope=self.scope)
        return self._headers

    @property
    def path(self) -> str:
        """The URL path for this request."""
        return self.url.path

    @property
    def query_params(self) -> QueryParams:
        """The URL query parameters."""
        if not hasattr(self, "_query_params"):  # pragma: no branch
            self._query_params = QueryParams(self.scope["query_string"])
        return self._query_params

    @property
    def path_params(self) -> dict[str, typing.Any]:
        """The path parameters extracted from the URL."""
        return self.scope.get("route_params", {})

    @property
    def cookies(self) -> dict[str, str]:
        """The cookies sent with this request."""
        if not hasattr(self, "_cookies"):
            cookies: dict[str, str] = {}
            cookie_header = self.headers.get("cookie")

            if cookie_header:
                cookies = cookie_parser(cookie_header)
            self._cookies = cookies
        return self._cookies

    @property
    def client(self) -> typing.Union[Address, None]:
        """The client address (host, port) for this request."""
        host_port = self.scope.get("client")
        if host_port is not None:
            return Address(*host_port)
        return None

    @property
    def state(self) -> State:
        """Request-scoped state for sharing data between middleware."""
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
        """The Origin header value."""
        return self.headers.get("Origin")

    @property
    def user_agent(self) -> str:
        """The User-Agent header value."""
        return self.headers.get("user-agent", "")

    def build_absolute_uri(
        self, path: str = "", query_params: typing.Optional[dict[str, str]] = None
    ) -> str:
        """
        Builds an absolute URI using the base URL and the provided path.

        :param path: A relative path to append to the base URL.
        :param query_params: Optional query parameters to append as a query string.
        :return: A fully constructed absolute URI as a string.
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
    raise RuntimeError("Receive channel has not been made available")


async def empty_send(message: Message) -> typing.NoReturn:
    raise RuntimeError("Send channel has not been made available")


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
        """Initialize a Request from ASGI scope and receive callable.

        Args:
            scope: ASGI scope dictionary.
            receive: ASGI receive callable.
            send: ASGI send callable.
        """
        super().__init__(scope, receive)
        assert scope["type"] == "http"
        self._receive = receive
        self._send = send
        self._stream_consumed = False
        self._is_disconnected = False
        self._form: FormData | Any = None

    @property
    def method(self) -> str:
        """The HTTP method (GET, POST, etc.)."""
        return self.scope["method"]

    @property
    def receive(self):
        """The ASGI receive callable."""
        return self._receive

    @property
    def content_type(self) -> typing.Optional[str]:
        """The Content-Type header without parameters."""
        content_type_header = self.headers.get("Content-Type")
        if content_type_header is None:
            return None
        content_type, _ = parse_options_header(content_type_header)
        return content_type.decode("utf-8") if content_type else None

    async def stream(self) -> typing.AsyncGenerator[bytes, None]:
        """Stream the request body as an async generator.

        Yields chunks of bytes as they are received from the client.
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
        """The full request body as bytes."""
        if not hasattr(self, "_body"):
            chunks: list[bytes] = []
            async for chunk in self.stream():
                chunks.append(chunk)
            self._body = b"".join(chunks)
        return self._body

    @property
    async def json(self) -> typing.Dict[str, JSONType]:
        """The request body parsed as JSON."""
        if not hasattr(self, "_json"):
            _body = await self.body
            self._json = json.loads(_body)
        return self._json

    @property
    async def text(self) -> str:
        """
        Read and decode the body of the request as text.

        Returns:
            str: The decoded text content of the request body.
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

        Args:
            max_files: Maximum number of files to parse.
            max_fields: Maximum number of form fields to parse.

        Returns:
            FormData object containing parsed form fields.
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
        """Context manager for accessing form data."""
        return AwaitableOrContextManagerWrapper(self._get_form())

    async def close(self) -> None:
        """Close any resources held by the request."""
        if self._form is not None:
            await self._form.close()

    async def is_disconnected(self) -> bool:
        """Check if the client has disconnected."""
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

        Args:
            path: The path to push.
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
        """A dictionary of uploaded files from the request."""
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
        """The parsed form data from the request body."""
        if not hasattr(self, "_form") or self._form is None:
            form_data = await self.form_data
            self._form = form_data
        return self._form

    def valid(self) -> bool:
        """Check if the request has a valid HTTP method and headers."""
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
        """The session interface for this request."""
        assert "session" in self.scope.keys(), "No Session Middleware Installed"
        return self.scope["session"]

    @property
    def user(self) -> BaseUser:
        """The authenticated user for this request."""
        return self.scope.get("user", UnauthenticatedUser())

    def url_for(self, _name: str, **path_params: typing.Dict[str, typing.Any]) -> str:
        """Generate a URL for the given route name.

        Args:
            _name: The name of the route.
            **path_params: Path parameters to substitute.

        Returns:
            The generated URL path.
        """
        return self.base_app.url_for(_name, **path_params)

    def __str__(self) -> str:
        """Return a string representation of this request."""
        return f"<Request {self.method} {self.url}>"

    @property
    def is_ajax(self) -> bool:
        """Check if the request is an AJAX request."""
        return self.headers.get("x-requested-with", "").lower() == "xmlhttprequest"

    @property
    def is_secure(self) -> bool:
        """Check if the request is using HTTPS."""
        return self.url.scheme == "https"

    @property
    def accepts_html(self) -> bool:
        """Check if the request accepts HTML response."""
        accept = self.headers.get("accept", "")
        return "text/html" in accept or "*/*" in accept

    @property
    def is_json(self) -> bool:
        """Check if the request content type is JSON."""
        content_type = self.content_type
        return content_type is not None and "application/json" in content_type

    @property
    def is_form(self) -> bool:
        """Check if the request is form data."""
        content_type = self.content_type
        return content_type is not None and (
            content_type.startswith("application/x-www-form-urlencoded")
            or content_type.startswith("multipart/form-data")
        )

    @property
    def is_multipart(self) -> bool:
        """Check if the request is multipart form data."""
        content_type = self.content_type
        return content_type is not None and content_type.startswith(
            "multipart/form-data"
        )

    @property
    def is_urlencoded(self) -> bool:
        """Check if the request is URL-encoded form data."""
        content_type = self.content_type
        return (
            content_type is not None
            and content_type == "application/x-www-form-urlencoded"
        )

    @property
    def has_cookie(self) -> bool:
        """Check if the request has cookies."""
        cookie_header = self.headers.get("cookie")
        return cookie_header is not None and cookie_header.strip() != ""

    @property
    def has_files(self) -> bool:
        """Check if the request contains uploaded files."""
        try:
            import asyncio

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
        """Check if the request has a body."""
        content_length = self.content_length
        if content_length > 0:
            return True

        # For methods that typically have bodies
        if self.method in ("POST", "PUT", "PATCH"):
            return True

        return False

    @property
    def is_authenticated(self) -> bool:
        """Check if the request has an authenticated user."""
        return self.user is not None

    @property
    def has_session(self) -> bool:
        """Check if session middleware is available."""
        return "session" in self.scope

    @property
    def accepts_json(self) -> bool:
        """Check if the request accepts JSON response."""
        accept = self.headers.get("accept", "")
        return "application/json" in accept or "*/*" in accept

    def get_header(self, key: str, default: typing.Any = None) -> typing.Any:
        """Get a header value with a default if not found."""
        return self.headers.get(key.lower()) or default

    def has_header(self, key: str) -> bool:
        """Check if a header exists."""
        return key.lower() in self.headers

    @property
    def origin(self) -> str:
        """Get the request's origin URL."""
        if "origin" in self.headers:
            return typing.cast(str, self.headers["origin"])
        return f"{self.url.scheme}://{self.url.netloc}"

    @property
    def referrer(self) -> str:
        """Get the request's referrer."""
        return typing.cast(str, self.headers.get("referer")) or ""

    def get_client_ip(self) -> str:
        """Get the client's IP address, considering proxy headers."""
        forwarded_for = self.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = self.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        return self.client.host if self.client else ""

    def is_method(self, method: str) -> bool:
        """
        Check if the request method matches the given method.
        Case-insensitive method comparison.
        """
        return self.method.upper() == method.upper()

    @property
    def content_length(self) -> int:
        """The Content-Length header value as int."""
        try:
            return int(self.headers.get("content-length", 0))
        except (ValueError, TypeError):
            return 0

    def get_query_params(
        self, flat: bool = True
    ) -> typing.Union[typing.Dict[str, str], typing.Dict[str, typing.List[str]]]:
        """Get query parameters, optionally flattened.

        Args:
            flat (bool): If True, returns only the first value for each parameter.
                        If False, returns all values as a list.
        """
        params = dict(self.query_params)
        if flat:
            return {k: v[0] if isinstance(v, list) else v for k, v in params.items()}
        return params
