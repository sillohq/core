from __future__ import annotations

import os
import shutil
import typing
from typing import Any, Dict, Sequence
from urllib.parse import parse_qsl, urlencode

from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler
from pydantic_core import core_schema

from nexios.objects.datastructures import ImmutableMultiDict, MultiDict
from nexios.utils.concurrency import run_in_threadpool


class QueryParams(ImmutableMultiDict[str, str]):
    """
    An immutable multidict for query parameters.
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
    An immutable, case-insensitive multidict for HTTP headers.
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

    async def save(self, destination: typing.Union[str, os.PathLike[str]]) -> None:
        """
        Save the uploaded file to a destination.
        """
        if self._in_memory:
            with open(destination, "wb") as f:
                shutil.copyfileobj(self.file, f)
        else:
            await run_in_threadpool(self._save_to_disk, destination)

    def _save_to_disk(self, destination: typing.Union[str, os.PathLike[str]]) -> None:
        with open(destination, "wb") as f:
            shutil.copyfileobj(self.file, f)

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
        """
        return super().get(key, default)
