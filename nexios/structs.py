from __future__ import annotations

import typing
from typing import Any, Dict, ItemsView, Iterator, KeysView, Sequence, ValuesView
from urllib.parse import SplitResult, parse_qsl, urlencode, urlsplit

from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler
from pydantic_core import core_schema

from nexios.utils.concurrency import run_in_threadpool

Scope = typing.MutableMapping[str, typing.Any]
Message = typing.MutableMapping[str, typing.Any]

Receive = typing.Callable[[], typing.Awaitable[Message]]
Send = typing.Callable[[Message], typing.Awaitable[None]]


class Address(typing.NamedTuple):
    host: str
    port: int


_KeyType = typing.TypeVar("_KeyType")
# you can only read them
# that is, you can't do `Mapping[str, Animal]()["fido"] = Dog()`
_CovariantValueType = typing.TypeVar("_CovariantValueType", covariant=True)


class URL:
    def __init__(
        self,
        url: str = "",
        scope: Scope | None = None,
        **components: Any,
    ) -> None:
        if scope is not None:
            assert not url, 'Cannot set both "url" and "scope".'
            assert not components, 'Cannot set both "scope" and "**components".'
            scheme = scope.get("scheme", "http")
            server = scope.get("server", None)
            path = scope["path"]
            query_string = scope.get("query_string", b"")

            host_header = None
            for key, value in scope["headers"]:
                if key == b"host":
                    host_header = value.decode("latin-1")
                    break

            if host_header is not None:
                url = f"{scheme}://{host_header}{path}"
            elif server is None:
                url = path
            else:
                host, port = server
                default_port = {"http": 80, "https": 443, "ws": 80, "wss": 443}[scheme]
                if port == default_port:
                    url = f"{scheme}://{host}{path}"
                else:
                    url = f"{scheme}://{host}:{port}{path}"

            if query_string:
                url += "?" + query_string.decode()
        elif components:
            assert not url, 'Cannot set both "url" and "**components".'
            url = URL("").replace(**components).components.geturl()

        self._url = url

    @property
    def components(self) -> SplitResult:
        if not hasattr(self, "_components"):
            self._components = urlsplit(self._url)
        return self._components

    @property
    def scheme(self) -> str:
        return self.components.scheme

    @property
    def netloc(self) -> str:
        return self.components.netloc

    @property
    def path(self) -> str:
        return self.components.path

    @property
    def query(self) -> str:
        return self.components.query

    @property
    def fragment(self) -> str:
        return self.components.fragment

    @property
    def username(self) -> None | str:
        return self.components.username

    @property
    def password(self) -> None | str:
        return self.components.password

    @property
    def hostname(self) -> None | str:
        return self.components.hostname

    @property
    def port(self) -> int | None:
        return self.components.port

    @property
    def is_secure(self) -> bool:
        return self.scheme in ("https", "wss")

    def replace(self, **kwargs: Any) -> URL:
        if (
            "username" in kwargs
            or "password" in kwargs
            or "hostname" in kwargs
            or "port" in kwargs
        ):
            hostname = kwargs.pop("hostname", None)
            port = kwargs.pop("port", self.port)
            username = kwargs.pop("username", self.username)
            password = kwargs.pop("password", self.password)

            if hostname is None:
                netloc = self.netloc
                _, _, hostname = netloc.rpartition("@")

                if hostname[-1] != "]":
                    hostname = hostname.rsplit(":", 1)[0]

            netloc = hostname
            if port is not None:
                netloc += f":{port}"
            if username is not None:
                userpass = username
                if password is not None:
                    userpass += f":{password}"
                netloc = f"{userpass}@{netloc}"

            kwargs["netloc"] = netloc

        components = self.components._replace(**kwargs)
        return self.__class__(components.geturl())

    def include_query_params(self, **kwargs: Any) -> URL:
        params = MultiDict(parse_qsl(self.query, keep_blank_values=True))
        params.update({str(key): str(value) for key, value in kwargs.items()})
        query = urlencode(params.multi_items())
        return self.replace(query=query)

    def replace_query_params(self, **kwargs: Any) -> URL:
        query = urlencode([(str(key), str(value)) for key, value in kwargs.items()])
        return self.replace(query=query)

    def remove_query_params(self, keys: str | Sequence[str]) -> URL:
        if isinstance(keys, str):
            keys = [keys]
        params = MultiDict(parse_qsl(self.query, keep_blank_values=True))
        for key in keys:
            params.pop(key, None)
        query = urlencode(params.multi_items())
        return self.replace(query=query)

    def __eq__(self, other: Any) -> bool:
        return str(self) == str(other)

    def __str__(self) -> str:
        return self._url

    def __repr__(self) -> str:
        url = str(self)
        if self.password:
            url = str(self.replace(password="********"))
        return f"{self.__class__.__name__}({repr(url)})"


class URLPath(str):
    """
    A URL path string that may also hold an associated protocol and/or host.
    Used by the routing to return `url_path_for` matches.
    """

    def __new__(cls, path: str, protocol: str = "", host: str = "") -> "URLPath":
        assert protocol in ("http", "websocket", "")
        return str.__new__(cls, path)

    def __init__(self, path: str, protocol: str = "", host: str = "") -> None:
        self.protocol = protocol
        self.host = host

    def make_absolute_url(self, base_url: typing.Union[str, URL]) -> URL:
        if isinstance(base_url, str):
            base_url = URL(base_url)
        if self.protocol:
            scheme = {
                "http": {True: "https", False: "http"},
                "websocket": {True: "wss", False: "ws"},
            }[self.protocol][base_url.is_secure]
        else:
            scheme = base_url.scheme

        netloc = self.host or base_url.netloc
        path = base_url.path.rstrip("/") + str(self)
        return URL(scheme=scheme, netloc=netloc, path=path)


class Secret:
    """
    Holds a string value that should not be revealed in tracebacks etc.
    You should cast the value to `str` at the point it is required.
    """

    def __init__(self, value: str):
        self._value = value

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        return f"{class_name}('**********')"

    def __str__(self) -> str:
        return self._value

    def __bool__(self) -> bool:
        return bool(self._value)


class ImmutableMultiDict(typing.Mapping[_KeyType, _CovariantValueType]):
    _dict: typing.Dict[_KeyType, _CovariantValueType]

    def __init__(
        self,
        *args: typing.Union[
            "ImmutableMultiDict[_KeyType, _CovariantValueType]",
            typing.Mapping[_KeyType, _CovariantValueType],
            typing.Iterable[typing.Tuple[_KeyType, _CovariantValueType]],
        ],
        **kwargs: typing.Any,
    ) -> None:
        assert len(args) < 2, "Too many arguments."

        value: typing.Any = args[0] if args else []
        if kwargs:
            value = (
                ImmutableMultiDict(value).multi_items()
                + ImmutableMultiDict(kwargs).multi_items()  # type: ignore[operator]
            )

        if not value:
            _items: typing.List[typing.Tuple[typing.Any, typing.Any]] = []
        elif hasattr(value, "multi_items"):
            value = typing.cast(
                ImmutableMultiDict[_KeyType, _CovariantValueType], value
            )
            _items = list(value.multi_items())
        elif hasattr(value, "items"):
            value = typing.cast(typing.Mapping[_KeyType, _CovariantValueType], value)
            _items = list(value.items())
        else:
            value = typing.cast(
                typing.List[typing.Tuple[typing.Any, typing.Any]], value
            )
            _items = list(value)

        self._dict = {k: v for k, v in _items}
        self._list = _items

    def getlist(self, key: typing.Any) -> typing.List[_CovariantValueType]:
        return [item_value for item_key, item_value in self._list if item_key == key]

    def keys(self) -> typing.KeysView[_KeyType]:
        return self._dict.keys()

    def values(self) -> typing.ValuesView[_CovariantValueType]:
        return self._dict.values()

    def items(self) -> typing.ItemsView[_KeyType, _CovariantValueType]:
        return self._dict.items()

    def multi_items(self) -> typing.List[typing.Tuple[_KeyType, _CovariantValueType]]:
        return list(self._list)

    def __getitem__(self, key: _KeyType) -> _CovariantValueType:
        return self._dict[key]

    def __contains__(self, key: typing.Any) -> bool:
        return key in self._dict

    def __iter__(self) -> typing.Iterator[_KeyType]:
        return iter(self.keys())

    def __len__(self) -> int:
        return len(self._dict)

    def __eq__(self, other: typing.Any) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return sorted(self._list) == sorted(other._list)

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        items = self.multi_items()
        return f"{class_name}({items!r})"


class MultiDict(ImmutableMultiDict[typing.Any, typing.Any]):
    def __setitem__(self, key: typing.Any, value: typing.Any) -> None:
        self.setlist(key, [value])

    def __delitem__(self, key: typing.Any) -> None:
        self._list = [(k, v) for k, v in self._list if k != key]
        del self._dict[key]

    def pop(self, key: typing.Any, default: typing.Any = None) -> typing.Any:
        self._list = [(k, v) for k, v in self._list if k != key]
        return self._dict.pop(key, default)

    def popitem(self) -> typing.Tuple[typing.Any, typing.Any]:
        key, value = self._dict.popitem()
        self._list = [(k, v) for k, v in self._list if k != key]
        return key, value

    def poplist(self, key: typing.Any) -> typing.List[typing.Any]:
        values = [v for k, v in self._list if k == key]
        self.pop(key)
        return values

    def clear(self) -> None:
        self._dict.clear()
        self._list.clear()

    def setdefault(self, key: typing.Any, default: typing.Any = None) -> typing.Any:
        if key not in self:
            self._dict[key] = default
            self._list.append((key, default))

        return self[key]

    def setlist(self, key: typing.Any, values: typing.List[typing.Any]) -> None:
        if not values:
            self.pop(key, None)
        else:
            existing_items = [(k, v) for (k, v) in self._list if k != key]
            self._list = existing_items + [(key, value) for value in values]
            self._dict[key] = values[-1]

    def append(self, key: typing.Any, value: typing.Any) -> None:
        self._list.append((key, value))
        self._dict[key] = value

    def update(
        self,
        *args: typing.Union[
            "MultiDict",
            typing.Mapping[str, typing.Any],
            typing.List[typing.Tuple[typing.Any, typing.Any]],
        ],
        **kwargs: typing.Any,
    ) -> None:
        value = MultiDict(*args, **kwargs)
        existing_items = [(k, v) for (k, v) in self._list if k not in value.keys()]
        self._list = existing_items + value.multi_items()
        self._dict.update(value)


class QueryParams(ImmutableMultiDict[str, str]):
    """
    An immutable multidict.
    """

    def __init__(
        self,
        *args: typing.Union[
            "ImmutableMultiDict[str,typing.Any]",
            typing.Mapping[str, typing.Any],
            typing.List[typing.Tuple[typing.Any, typing.Any]],
            str,
            bytes,
        ],
        **kwargs: typing.Any,
    ) -> None:
        assert len(args) < 2, "Too many arguments."

        value = args[0] if args else []

        if isinstance(value, str):
            super().__init__(parse_qsl(value, keep_blank_values=True), **kwargs)
        elif isinstance(value, bytes):
            super().__init__(
                parse_qsl(value.decode("latin-1"), keep_blank_values=True), **kwargs
            )
        else:
            super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self._list = [(str(k), str(v)) for k, v in self._list]
        self._dict = {str(k): str(v) for k, v in self._dict.items()}

    def __str__(self) -> str:
        return urlencode(self._list)

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        query_string = str(self)
        return f"{class_name}({query_string!r})"

    def __call__(self, *args: Any, **kwds: Any) -> Dict[str, Any]:
        return self._dict


class Headers(typing.Mapping[str, str]):
    """
    An immutable, case-insensitive multidict.
    """

    def __init__(
        self,
        headers: typing.Optional[typing.Mapping[str, str]] = None,
        raw: typing.Optional[typing.List[typing.Tuple[bytes, bytes]]] = None,
        scope: typing.Optional[typing.MutableMapping[str, typing.Any]] = None,
    ) -> None:
        self._list: typing.List[typing.Tuple[bytes, bytes]] = []
        if headers is not None:
            assert raw is None, 'Cannot set both "headers" and "raw".'
            assert scope is None, 'Cannot set both "headers" and "scope".'
            if isinstance(headers, typing.Mapping):  # type: ignore
                self._list = [
                    (key.lower().encode("latin-1"), value.encode("latin-1"))
                    for key, value in headers.items()
                ]
            else:
                # Assume it's a list of (bytes, bytes) tuples or something convertible
                self._list = [
                    (
                        (
                            k.lower()
                            if isinstance(k, bytes)
                            else k.lower().encode("latin-1")
                        ),
                        v if isinstance(v, bytes) else v.encode("latin-1"),
                    )
                    for k, v in headers
                ]
        elif raw is not None:
            assert scope is None, 'Cannot set both "raw" and "scope".'
            self._list = raw
        elif scope is not None:
            # scope["headers"] isn't necessarily a list
            # it might be a tuple or other iterable
            self._list = list(scope["headers"])

    @property
    def raw(self) -> typing.List[typing.Tuple[bytes, bytes]]:
        return list(self._list)

    def keys(self) -> typing.List[str]:  # type: ignore[override]
        return [key.decode("latin-1") for key, _ in self._list]

    def values(self) -> typing.List[str]:  # type: ignore[override]
        return [value.decode("latin-1") for _, value in self._list]

    def items(self) -> typing.List[typing.Tuple[str, str]]:  # type: ignore
        return [
            (key.decode("latin-1"), value.decode("latin-1"))
            for key, value in self._list
        ]

    def getlist(self, key: str) -> typing.List[str]:
        get_header_key = key.lower().encode("latin-1")
        return [
            item_value.decode("latin-1")
            for item_key, item_value in self._list
            if item_key == get_header_key
        ]

    def mutablecopy(self) -> "MutableHeaders":
        return MutableHeaders(raw=self._list[:])

    def __getitem__(self, key: str):  # type: ignore[override]
        get_header_key = key.lower().encode("latin-1")
        for header_key, header_value in self._list:
            if header_key == get_header_key:
                return header_value.decode("latin-1")
        return None

    def __contains__(self, key: typing.Any) -> bool:
        get_header_key = key.lower().encode("latin-1")
        for header_key, _ in self._list:
            if header_key == get_header_key:
                return True
        return False

    def __iter__(self) -> typing.Iterator[typing.Any]:
        return iter(self.keys())

    def __len__(self) -> int:
        return len(self._list)

    def __eq__(self, other: typing.Any) -> bool:
        if not isinstance(other, Headers):
            return False
        return sorted(self._list) == sorted(other._list)

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        as_dict = dict(self.items())
        if len(as_dict) == len(self):
            return f"{class_name}({as_dict!r})"
        return f"{class_name}(raw={self.raw!r})"


class MutableHeaders(Headers):
    def __setitem__(self, key: str, value: str) -> None:
        """
        Set the header `key` to `value`, removing any duplicate entries.
        Retains insertion order.
        """
        set_key = key.lower().encode("latin-1")
        set_value = value.encode("latin-1")

        found_indexes: "typing.List[int]" = []
        for idx, (item_key, _) in enumerate(self._list):
            if item_key == set_key:
                found_indexes.append(idx)

        for idx in reversed(found_indexes[1:]):
            del self._list[idx]

        if found_indexes:
            idx = found_indexes[0]
            self._list[idx] = (set_key, set_value)
        else:
            self._list.append((set_key, set_value))

    def __delitem__(self, key: str) -> None:
        """
        Remove the header `key`.
        """
        del_key = key.lower().encode("latin-1")

        pop_indexes: "typing.List[int]" = []
        for idx, (item_key, _) in enumerate(self._list):
            if item_key == del_key:
                pop_indexes.append(idx)

        for idx in reversed(pop_indexes):
            del self._list[idx]

    def __ior__(self, other: typing.Mapping[str, str]) -> "MutableHeaders":
        if not isinstance(other, typing.Mapping):  # type: ignore
            raise TypeError(f"Expected a mapping but got {other.__class__.__name__}")
        self.update(other)
        return self

    def __or__(self, other: typing.Mapping[str, str]) -> "MutableHeaders":
        if not isinstance(other, typing.Mapping):  # type: ignore
            raise TypeError(f"Expected a mapping but got {other.__class__.__name__}")
        new = self.mutablecopy()
        new.update(other)
        return new

    @property
    def raw(self) -> typing.List[typing.Tuple[bytes, bytes]]:
        return self._list

    def setdefault(self, key: str, value: str) -> str:
        """
        If the header `key` does not exist, then set it to `value`.
        Returns the header value.
        """
        set_key = key.lower().encode("latin-1")
        set_value = value.encode("latin-1")

        for _, (item_key, item_value) in enumerate(self._list):
            if item_key == set_key:
                return item_value.decode("latin-1")
        self._list.append((set_key, set_value))
        return value

    def update(self, other: typing.Mapping[str, str]) -> None:
        for key, val in other.items():
            self[key] = val

    def append(self, key: str, value: str) -> None:
        """
        Append a header, preserving any duplicate entries.
        """
        append_key = key.lower().encode("latin-1")
        append_value = value.encode("latin-1")
        self._list.append((append_key, append_value))

    def add_vary_header(self, vary: str) -> None:
        existing = self.get("vary")
        if existing is not None:
            vary = ", ".join([existing, vary])
        self["vary"] = vary


class State:
    """
    An object that can be used to store arbitrary state.

    Used for `request.state` and `app.state`.
    """

    _state: typing.Dict[str, typing.Any]

    def __init__(self, state: typing.Optional[typing.Dict[str, typing.Any]] = None):
        if state is None:
            state = {}
        super().__setattr__("_state", state)

    def __setattr__(self, key: typing.Any, value: typing.Any) -> None:
        self._state[key] = value

    def __getattr__(self, key: typing.Any) -> typing.Any:
        try:
            return self._state[key]
        except KeyError:
            return None

    def __delattr__(self, key: typing.Any) -> None:
        del self._state[key]

    def __str__(self) -> str:
        return f"<State data={self._state}>"

    def update(self, values: Dict[str, Any]):
        for key, value in values.items():
            self._state[key] = value


class RouteParam:
    def __init__(self, data: Dict[str, Any]) -> None:
        """Initialize the RouteParam with a dictionary."""
        self.data: Dict[str, Any] = data

    def __iter__(self) -> Iterator[str]:
        """Return an iterator over the dictionary keys."""
        return iter(self.data)

    def __getitem__(self, name: str) -> Any:
        """Retrieve a value by key, returning None if the key does not exist."""
        return self.data.get(name, None)

    def __getattribute__(self, name: str) -> Any:
        """
        Custom attribute access:
        - If the attribute exists in `data`, return its value.
        - Otherwise, fallback to the default attribute resolution.
        """
        data = object.__getattribute__(self, "data")
        if name in data:
            return data[name]
        return object.__getattribute__(self, name)

    def get_lists(self) -> ItemsView[str, Any]:
        """Return the dictionary's items (key-value pairs)."""
        return self.data.items()

    def keys(self) -> KeysView[str]:
        """Return the dictionary's keys."""
        return self.data.keys()

    def values(self) -> ValuesView[Any]:
        """Return the dictionary's values."""
        return self.data.values()

    def items(self) -> ItemsView[str, Any]:
        """Return the dictionary's items (key-value pairs)."""
        return self.data.items()

    def __repr__(self) -> str:
        """Return a string representation of the RouteParam object."""
        return f"<RouteParams {dict(self.data)}>"

    def __len__(self) -> int:
        """Return the number of items in the dictionary."""
        return len(self.data)

    def __call__(self, *args: Any, **kwds: Any) -> Dict[str, Any]:
        return self.data

    def get(self, key: str, default: Any = None) -> Any:
        """Return the value for the given key, or a default value if the key does not exist."""
        return self.data.get(key, default)

    def __dict__(self) -> Dict[str, Any]:  # type:ignore
        return self.data


class UploadedFile:
    """
    An uploaded file included as part of the request data.
    """

    def __init__(
        self,
        file: typing.BinaryIO,
        *,
        size: typing.Optional[int] = None,
        filename: typing.Optional[str] = None,
        headers: typing.Optional[Headers] = None,
    ) -> None:
        self.filename = filename
        self.file = file
        self.size = size
        self.headers = headers or Headers()

    @property
    def content_type(self) -> typing.Union[str, None]:
        return self.headers.get("content-type", None)

    @property
    def _in_memory(self) -> bool:
        # check for SpooledTemporaryFile._rolled
        rolled_to_disk = getattr(self.file, "_rolled", True)
        return not rolled_to_disk

    async def write(self, data: bytes) -> None:
        if self.size is not None:
            self.size += len(data)

        if self._in_memory:
            self.file.write(data)
        else:
            await run_in_threadpool(self.file.write, data)

    async def read(self, size: int = -1) -> bytes:
        if self._in_memory:
            return self.file.read(size)
        return await run_in_threadpool(self.file.read, size)

    async def seek(self, offset: int) -> None:
        if self._in_memory:
            self.file.seek(offset)
        else:
            await run_in_threadpool(self.file.seek, offset)

    async def close(self) -> None:
        if self._in_memory:
            self.file.close()
        else:
            await run_in_threadpool(self.file.close)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"filename={self.filename!r}, "
            f"size={self.size!r}, "
            f"headers={self.headers!r})"
        )

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source: Any, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        # treat this type as bytes in validation
        return core_schema.no_info_after_validator_function(
            cls, core_schema.bytes_schema()
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: core_schema.CoreSchema, handler: GetJsonSchemaHandler
    ) -> dict[str, str]:
        # represent in OpenAPI as a file upload
        return {
            "type": "string",
            "format": "binary",
        }


class FormData(
    MultiDict[str, typing.Union[UploadedFile, str, Sequence[Any]]]  # type:ignore
):  # type:ignore
    def __init__(
        self,
        *args: typing.Union[
            FormData,
            typing.Mapping[str, typing.Union[str, UploadedFile]],
            list[tuple[str, typing.Union[str, UploadedFile]]],
        ],
        **kwargs: typing.Union[str, UploadedFile],
    ) -> None:
        super().__init__(*args, **kwargs)

    async def close(self) -> None:
        for _, value in self.multi_items():
            if isinstance(value, UploadedFile):
                await value.close()

    def get(
        self, key: str, default: typing.Any = None
    ) -> typing.Union[UploadedFile, str, None]:
        """
        Get a value from the form data by key.

        Args:
            key: The key to look up
            default: Value to return if key is not found

        Returns:
            The value if found, or the default
        """
        try:
            return self[key]
        except KeyError:
            return default
