from __future__ import annotations

import json
import typing
from http import cookies as http_cookies

import anyio

from nexios._internals._formparsers import (
    FormParser,
    MultiPartException,
    MultiPartParser,
    UploadedFile,
)
from nexios.objects import URL, Address, FormData, Headers, QueryParams, State
from nexios.session.base import BaseSessionInterface
from nexios.utils.async_helpers import (
    AwaitableOrContextManager,
    AwaitableOrContextManagerWrapper,
)

if typing.TYPE_CHECKING:
    from nexios import NexiosApp
    from nexios.auth.users.base import BaseUser


try:
    from python_multipart.multipart import parse_options_header  # type:ignore

except ImportError:
    parse_options_header = None
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
            cookie_dict[key] = http_cookies._unquote(val)  # type:ignore
    return cookie_dict


class ClientDisconnect(Exception):
    pass


T = typing.TypeVar("T")


class HTTPConnection(object):
    """
    A base class for incoming HTTP connections, that is used to provide
    any functionality that is common to both `Request` and `WebSocket`.
    """

    def __init__(self, scope: Scope, receive: Receive) -> None:
        assert scope["type"] in ("http", "websocket")
        self.scope = scope
        self.scope.update({"extensions": {"websocket.http.response": {}}})

    def __getitem__(self, key: str) -> typing.Any:
        return self.scope[key]

    def __iter__(self) -> typing.Iterator[str]:
        return iter(self.scope)

    def __len__(self) -> int:
        return len(self.scope)

    __eq__ = object.__eq__
    __hash__ = object.__hash__

    @property
    def app(self) -> typing.Any:
        return self.scope["app"]

    @property
    def base_app(self) -> "NexiosApp":  # noqa: F821
        return self.scope["base_app"]

    @property
    def url(self) -> URL:
        if not hasattr(self, "_url"):  # pragma: no branch
            self._url = URL(scope=self.scope)
        return self._url

    @property
    def base_url(self) -> URL:
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
        if not hasattr(self, "_headers"):
            self._headers = Headers(scope=self.scope)
        return self._headers

    @property
    def path(self) -> str:
        return self.url.path

    @property
    def query_params(self) -> QueryParams:
        if not hasattr(self, "_query_params"):  # pragma: no branch
            self._query_params = QueryParams(self.scope["query_string"])
        return self._query_params

    @property
    def path_params(self) -> dict[str, typing.Any]:
        return self.scope.get("route_params", {})

    @property
    def cookies(self) -> dict[str, str]:
        if not hasattr(self, "_cookies"):
            cookies: dict[str, str] = {}
            cookie_header = self.headers.get("cookie")

            if cookie_header:
                cookies = cookie_parser(cookie_header)
            self._cookies = cookies
        return self._cookies

    @property
    def client(self) -> typing.Union[Address, None]:
        host_port = self.scope.get("client")
        if host_port is not None:
            return Address(*host_port)
        return None

    @property
    def state(self) -> State:
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
        return self.headers.get("Origin")

    @property
    def user_agent(self) -> str:
        """Returns the User-Agent header if available."""
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
            from urllib.parse import urlencode

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
        super().__init__(scope, receive)
        assert scope["type"] == "http"
        self._receive = receive
        self._send = send
        self._stream_consumed = False
        self._is_disconnected = False
        self._form = None  # type: ignore

    @property
    def method(self) -> str:
        return self.scope["method"]

    @property
    def receive(self):
        return self._receive

    @property
    def content_type(self) -> typing.Optional[str]:
        content_type_header = self.headers.get("Content-Type")
        content_type: str
        content_type, _ = parse_options_header(content_type_header)  # type:ignore
        return content_type.decode("utf-8") if content_type else None  # type: ignore

    async def stream(self) -> typing.AsyncGenerator[bytes, None]:
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
        if not hasattr(self, "_body"):
            chunks: list[bytes] = []
            async for chunk in self.stream():
                chunks.append(chunk)
            self._body = b"".join(chunks)
        return self._body

    @property
    async def json(self) -> typing.Dict[str, JSONType]:
        if not hasattr(self, "_json"):
            _body = await self.body
            try:
                body = _body.decode()
            except UnicodeDecodeError:
                return {}
            try:
                self._json = json.loads(body)
            except json.JSONDecodeError:
                self._json = {}
        return self._json  # type: ignore

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
        if self._form is None:  # type:ignore
            assert (
                parse_options_header is not None
            ), "The `python-multipart` library must be installed to use form parsing."
            content_type_header = self.headers.get("Content-Type")
            content_type: bytes
            content_type, _ = parse_options_header(content_type_header)  # type:ignore
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
                    self._form = {}  # type: ignore
            elif content_type == b"application/x-www-form-urlencoded":
                form_parser = FormParser(self.headers, self.stream())

                self._form = await form_parser.parse()
            else:
                self._form: FormData = FormData()
        return self._form  # type:ignore

    @property
    def form_data(self) -> AwaitableOrContextManager[FormData]:
        return AwaitableOrContextManagerWrapper(self._get_form())

    async def close(self) -> None:
        if self._form is not None:  # type: ignore
            await self._form.close()

    async def is_disconnected(self) -> bool:
        if not self._is_disconnected:
            message: typing.Dict[str, typing.Any] = {}

            # If message isn't immediately available, move on
            with anyio.CancelScope() as cs:  # type: ignore
                cs.cancel()  # type: ignore
                message = await self._receive()  # type:ignore

            if message.get("type") == "http.disconnect":
                self._is_disconnected = True

        return self._is_disconnected

    async def send_push_promise(self, path: str) -> None:
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
        """
        This method returns a dictionary of files from the form_data.
        """
        form_data = await self.form_data
        files_dict: typing.Dict[str, typing.Any] = {}
        for key, value in form_data.items():
            if isinstance(value, (list, tuple)):
                for item in value:  # type: ignore
                    if hasattr(item, "filename"):  # type: ignore
                        files_dict[key] = item
            elif hasattr(value, "filename"):
                files_dict[key] = value
        return files_dict

    @property
    async def form(self) -> FormData:
        """
        Parse and return form data from the request body.
        Handles both URL-encoded and multipart form data.
        Uses the existing form_data property which already handles all form types.
        """
        if not hasattr(self, "_form") or self._form is None:  # type: ignore
            form_data = await self.form_data
            self._form = form_data
        return self._form

    def valid(self) -> bool:
        """
        Checks if the request is valid by ensuring the method and headers are properly set.
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
    def session(self) -> BaseSessionInterface:
        assert "session" in self.scope.keys(), "No Session Middleware Installed"
        return typing.cast(BaseSessionInterface, self.scope["session"])

    @property
    def user(self) -> typing.Optional[BaseUser]:
        return self.scope.get("user", None)

    def url_for(self, _name: str, **path_params: typing.Dict[str, typing.Any]) -> str:
        return self.base_app.url_for(_name, **path_params)

    def __str__(self) -> str:
        return f"<Request {self.method} {self.url}>"

    @property
    def is_ajax(self) -> bool:
        """
        Check if the request is an AJAX request.
        Returns True if the X-Requested-With header is XMLHttpRequest.
        """
        return self.headers.get("x-requested-with", "").lower() == "xmlhttprequest"

    @property
    def is_secure(self) -> bool:
        """
        Check if the request is using HTTPS.
        """
        return self.url.scheme == "https"

    @property
    def accepts_html(self) -> bool:
        """
        Check if the request accepts HTML response.
        Returns True if the Accept header includes text/html.
        """
        accept = self.headers.get("accept", "")
        return "text/html" in accept or "*/*" in accept

    @property
    def is_json(self) -> bool:
        """
        Check if the request content type is JSON.
        Returns True if Content-Type header starts with application/json.
        """
        content_type = self.content_type
        return content_type is not None and "application/json" in content_type

    @property
    def is_form(self) -> bool:
        """
        Check if the request is form data (either URL-encoded or multipart).
        Returns True if Content-Type is application/x-www-form-urlencoded or multipart/form-data.
        """
        content_type = self.content_type
        return content_type is not None and (
            content_type.startswith("application/x-www-form-urlencoded")
            or content_type.startswith("multipart/form-data")
        )

    @property
    def is_multipart(self) -> bool:
        """
        Check if the request is multipart form data.
        Returns True if Content-Type starts with multipart/form-data.
        """
        content_type = self.content_type
        return content_type is not None and content_type.startswith(
            "multipart/form-data"
        )

    @property
    def is_urlencoded(self) -> bool:
        """
        Check if the request is URL-encoded form data.
        Returns True if Content-Type is application/x-www-form-urlencoded.
        """
        content_type = self.content_type
        return (
            content_type is not None
            and content_type == "application/x-www-form-urlencoded"
        )

    @property
    def has_cookie(self) -> bool:
        """
        Check if the request has cookies.
        Returns True if Cookie header exists and has content.
        """
        cookie_header = self.headers.get("cookie")
        return cookie_header is not None and cookie_header.strip() != ""

    @property
    def has_files(self) -> bool:
        """
        Check if the request contains uploaded files.
        Returns True if the request has multipart form data with files.
        """
        try:
            # This will check if there are any files in the form data
            import asyncio

            if self.is_multipart:
                # Try to get form data to check for files
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If we're in an async context, we can't use asyncio.run
                    # Just check if the content type suggests files might be present
                    return True
                else:
                    # Safe to use asyncio.run
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
        """
        Check if the request has a body.
        Returns True if Content-Length > 0 or if body contains data.
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
        """
        Check if the request is authenticated (has user in scope).
        Returns True if user is set in the request scope.
        """
        return self.user is not None

    @property
    def has_session(self) -> bool:
        """
        Check if session middleware is available.
        Returns True if session is available in the request scope.
        """
        return "session" in self.scope

    @property
    def accepts_json(self) -> bool:
        """
        Check if the request accepts JSON response.
        Returns True if the Accept header includes application/json.
        """
        accept = self.headers.get("accept", "")
        return "application/json" in accept or "*/*" in accept

    def get_header(self, key: str, default: typing.Any = None) -> typing.Any:
        """
        Get a header value with a default if not found.
        Case-insensitive header lookup.
        """
        return self.headers.get(key.lower()) or default

    def has_header(self, key: str) -> bool:
        """
        Check if a header exists.
        Case-insensitive header lookup.
        """
        return key.lower() in self.headers

    @property
    def origin(self) -> str:
        """
        Get the request's origin.
        Returns the Origin header value or constructs it from the URL.
        """
        if "origin" in self.headers:
            return typing.cast(str, self.headers["origin"])
        return f"{self.url.scheme}://{self.url.netloc}"

    @property
    def referrer(self) -> str:
        """
        Get the request's referrer.
        Returns the Referer header value or empty string if not set.
        """
        return typing.cast(str, self.headers.get("referer")) or ""

    def get_client_ip(self) -> str:
        """
        Get the client's IP address.
        Handles X-Forwarded-For and X-Real-IP headers for proxy scenarios.
        """
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
        """
        Get the request's content length.
        Returns the Content-Length header value as int or 0 if not set.
        """
        try:
            return int(self.headers.get("content-length", 0))
        except (ValueError, TypeError):
            return 0

    def get_query_params(
        self, flat: bool = True
    ) -> typing.Union[typing.Dict[str, str], typing.Dict[str, typing.List[str]]]:
        """
        Get query parameters with option to flatten multiple values.

        Args:
            flat (bool): If True, returns only the first value for each parameter.
                        If False, returns all values as a list.
        """
        params = dict(self.query_params)
        if flat:
            return {k: v[0] if isinstance(v, list) else v for k, v in params.items()}
        return params
