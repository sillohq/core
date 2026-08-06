from __future__ import annotations

import os
import shutil
import typing
from typing import Any, Dict, Sequence
from urllib.parse import parse_qsl, urlencode

from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler
from pydantic_core import core_schema

from sillo.objects.datastructures import ImmutableMultiDict, MultiDict
from sillo.utils.concurrency import run_in_threadpool


class QueryParams(ImmutableMultiDict[str, str]):
    """
    An immutable multidict for HTTP query string parameters.

    Extends ImmutableMultiDict to provide specialized handling of URL query
    parameters. Accepts initialization from query string strings, bytes, or
    standard multidict inputs. All keys and values are coerced to strings
    to ensure consistent type handling for URL parameter access.

    Supports encoding back to a query string format via ``str()`` conversion,
    and can be called as a function to retrieve the underlying dictionary.
    """

    def __init__(
        self,
        *args: typing.Union[
            "ImmutableMultiDict[str,typing.Any]",
            typing.Mapping[str, str],
            typing.List[typing.Tuple[typing.Any, typing.Any]],
            str,
            bytes,
        ],
        **kwargs: typing.Any,
    ) -> None:
        """
        Initializes QueryParams from a query string, bytes, mapping, or iterable.

        Parses the input into key-value pairs suitable for query parameter storage.
        String and bytes inputs are parsed using ``parse_qsl`` with blank values
        preserved. All keys and values are coerced to strings to ensure type
        consistency across different input formats.

        Args:
            *args: Positional arguments that can be a query string, bytes,
                an ImmutableMultiDict, a Mapping, or a list of tuples.
            **kwargs: Additional keyword arguments to include as query parameters.

        Raises:
            AssertionError: If more than one positional argument is provided.
        """
        assert len(args) < 2, "Too many arguments."

        value = args[0] if args else []

        if isinstance(value, str):
            super().__init__(parse_qsl(value, keep_blank_values=True), **kwargs)
        elif isinstance(value, bytes):
            super().__init__(
                parse_qsl(value.decode("latin-1"), keep_blank_values=True), **kwargs
            )
        else:
            super().__init__(*args, **kwargs)  # ty: ignore
        self._list = [(str(k), str(v)) for k, v in self._list]
        self._dict = {str(k): str(v) for k, v in self._dict.items()}

    def __str__(self) -> str:
        """
        Encode the query parameters back into a URL query string format.

        Converts the internal list of key-value pairs into a properly
        URL-encoded query string using ``urlencode``, suitable for
        appending to a URL after a '?' delimiter. All keys and values
        are encoded as strings.

        Returns:
            str: A URL-encoded query string representation of all
            parameters in the form 'key1=value1&key2=value2'.

        Raises:
            None: No exceptions are raised during encoding.
        """
        return urlencode(self._list)

    def __repr__(self) -> str:
        """
        Return a developer-friendly string representation of the QueryParams.

        Produces a repr string showing the class name and the encoded query
        string for easy debugging and logging of query parameter contents.
        The repr shows the URL-encoded form, not the raw internal data.

        Returns:
            str: A string of the form ``QueryParams('key=value&...')`` showing
            the URL-encoded query parameters.

        Raises:
            None: No exceptions are raised during representation.
        """
        return f"QueryParams('{urlencode(self._list)}')"

    def __call__(self, *args: Any, **kwds: Any) -> Dict[str, Any]:
        """
        Returns the underlying dictionary of query parameters.

        Allows the QueryParams instance to be called as a function to retrieve
        the internal dictionary representation containing the last value for
        each unique key.

        Returns:
            Dict[str, Any]: The internal dictionary mapping parameter names
            to their last stored string values.
        """
        return self._dict


class Headers(typing.Mapping[str, str]):
    """
    An immutable, case-insensitive multidict for HTTP headers.

    Stores HTTP headers as a list of raw byte tuples internally while providing
    a string-based interface for header access. Header lookups are case-insensitive
    as required by the HTTP specification. Supports construction from a mapping,
    raw byte tuples, or an ASGI scope dictionary.

    Use ``mutablecopy()`` to obtain a ``MutableHeaders`` instance when header
    modification is required.
    """

    def __init__(
        self,
        headers: typing.Optional[typing.Mapping[str, str]] = None,
        raw: typing.Optional[typing.List[typing.Tuple[bytes, bytes]]] = None,
        scope: typing.Optional[typing.MutableMapping[str, typing.Any]] = None,
    ) -> None:
        """
        Initializes Headers from a mapping, raw byte tuples, or an ASGI scope.

        Accepts exactly one of three initialization sources: a string mapping
        of header names to values, a list of raw byte tuple pairs, or an ASGI
        connection scope dictionary containing a ``headers`` key. The headers
        are stored internally as lowercase byte tuples for case-insensitive access.

        Args:
            headers (Optional[Mapping[str, str]]): A mapping of header names
                to values. Keys are lowercased and encoded to bytes.
            raw (Optional[List[Tuple[bytes, bytes]]]): Pre-encoded raw header
                byte tuples as received from the ASGI server.
            scope (Optional[MutableMapping[str, Any]]): An ASGI scope dictionary
                from which the ``headers`` key is extracted.

        Raises:
            AssertionError: If more than one initialization source is provided.
        """
        self._list: typing.List[typing.Tuple[bytes, bytes]] = []
        if headers is not None:
            assert raw is None, 'Cannot set both "headers" and "raw".'
            assert scope is None, 'Cannot set both "headers" and "scope".'
            if isinstance(headers, typing.Mapping):
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
        """
        Returns a copy of the raw header byte tuples.

        Provides access to the internal header storage as a list of byte
        tuple pairs suitable for use in ASGI message construction. Returns
        a copy to prevent external modification of the internal state.

        Returns:
            List[Tuple[bytes, bytes]]: A list of lowercase header name and
            value byte pairs representing all stored headers.
        """
        return list(self._list)

    def keys(self):
        """
        Returns a list of all header names decoded as strings.

        Decodes each header name from bytes to a string using the latin-1
        encoding. May contain duplicates if the same header name appears
        multiple times in the raw header list.

        Returns:
            List[str]: A list of decoded header name strings.
        """
        return [k.decode("latin-1") for k, _ in self._list]

    def values(self):
        """
        Returns a list of all header values decoded as strings.

        Decodes each header value from bytes to a string using the latin-1
        encoding. The order corresponds to the order of keys returned by
        the ``keys()`` method.

        Returns:
            List[str]: A list of decoded header value strings.
        """
        return [v.decode("latin-1") for _, v in self._list]

    def items(self):
        """
        Returns a list of all header name-value pairs decoded as strings.

        Decodes both header names and values from bytes to strings using
        the latin-1 encoding. Each tuple in the returned list represents
        one header entry from the internal storage.

        Returns:
            List[Tuple[str, str]]: A list of decoded header name-value pairs.
        """
        return [(k.decode("latin-1"), v.decode("latin-1")) for k, v in self._list]

    def getlist(self, key: str) -> typing.List[str]:
        """
        Returns all values for a given header name as a list of strings.

        Performs a case-insensitive search through the internal header list
        and collects all values associated with the specified header name.
        This is useful for headers that may appear multiple times such as
        ``Set-Cookie`` or ``Accept``.

        Args:
            key (str): The header name to look up, compared case-insensitively.

        Returns:
            List[str]: A list of all decoded values for the given header name.
            Returns an empty list if the header is not present.
        """
        get_header_key = key.lower().encode("latin-1")
        return [
            item_value.decode("latin-1")
            for item_key, item_value in self._list
            if item_key == get_header_key
        ]

    def mutablecopy(self) -> "MutableHeaders":
        """
        Create a mutable copy of these headers for modification.

        Returns a new MutableHeaders instance initialized with a shallow
        copy of the internal raw byte tuple list. Modifications to the
        returned MutableHeaders do not affect this immutable Headers
        instance, allowing safe header manipulation.

        Returns:
            MutableHeaders: A new mutable headers instance containing
            copies of all header entries from this immutable instance.

        Raises:
            None: No exceptions are raised during the copy operation.
        """
        return MutableHeaders(raw=self._list[:])

    def __getitem__(self, key: str):  # type: ignore[override]
        """
        Retrieve the value of a header by its name (case-insensitive).

        Searches the internal header list for a matching header name using
        case-insensitive comparison. Returns the decoded string value of
        the first matching header found. Returns None if no matching
        header exists, rather than raising a KeyError.

        Args:
            key: The header name to look up. Comparison is case-insensitive
                as per HTTP specification requirements.

        Returns:
            str | None: The decoded header value string if found, or None
            if no header with the given name exists.

        Raises:
            None: No exceptions are raised; returns None for missing headers.
        """
        get_header_key = key.lower().encode("latin-1")
        for header_key, header_value in self._list:
            if header_key == get_header_key:
                return header_value.decode("latin-1")
        return None

    def get(  # ty: ignore[invalid-method-override]
        self, key: str, default: typing.Any = None
    ) -> typing.Any:
        """
        Retrieve a header value, falling back to *default* when it is absent.

        ``Mapping.get`` is implemented by catching ``KeyError`` from
        ``__getitem__``, but this class deliberately returns ``None`` for a
        missing header instead of raising — which would make the inherited
        ``get`` ignore the caller's default and always answer ``None``. This
        override honours the default while leaving subscript access as it is.

        Args:
            key: The header name to look up, matched case-insensitively.
            default: Value to return when no such header is present.

        Returns:
            The decoded header value, or *default* when the header is absent.
        """
        value = self[key]
        return default if value is None else value

    def __contains__(self, key: typing.Any) -> bool:
        """
        Check whether a header with the given name exists (case-insensitive).

        Searches the internal header list for a matching header name using
        case-insensitive byte comparison. This enables the ``in`` operator
        for header membership testing.

        Args:
            key: The header name to check for existence. Comparison is
                case-insensitive as per HTTP specification requirements.

        Returns:
            bool: True if a header with the given name exists, False
            otherwise.

        Raises:
            None: No exceptions are raised during the membership check.
        """
        get_header_key = key.lower().encode("latin-1")
        for header_key, _ in self._list:
            if header_key == get_header_key:
                return True
        return False

    def __iter__(self) -> typing.Iterator[typing.Any]:
        """
        Return an iterator over all header names decoded as strings.

        Delegates to the ``keys()`` method to provide iteration over
        header names. Each header name is decoded from bytes to string
        using latin-1 encoding. May yield duplicates if the same header
        appears multiple times.

        Returns:
            Iterator[Any]: An iterator yielding decoded header name
            strings from the internal header list.

        Raises:
            None: No exceptions are raised during iteration.
        """
        return iter(self.keys())

    def __len__(self) -> int:
        """
        Return the total number of header entries including duplicates.

        Returns the length of the internal header list, which counts
        all header entries including duplicate header names. This may
        differ from the number of unique header names.

        Returns:
            int: The total number of header entries in the internal
            list, including any duplicate header names.

        Raises:
            None: No exceptions are raised during length computation.
        """
        return len(self._list)

    def __eq__(self, other: typing.Any) -> bool:
        """
        Compare this Headers instance with another for equality.

        Two Headers instances are considered equal if they contain the
        same set of raw byte tuple pairs regardless of order. Comparison
        with objects of other types always returns False.

        Args:
            other: The object to compare against this Headers instance.
                Must be another Headers instance for equality to hold.

        Returns:
            bool: True if both Headers contain the same sorted list of
            byte tuple pairs, False if types differ or contents differ.

        Raises:
            None: No exceptions are raised during comparison.
        """
        if not isinstance(other, Headers):
            return False
        return sorted(self._list) == sorted(other._list)

    def __repr__(self) -> str:
        """
        Return a developer-friendly string representation of the Headers.

        Produces a repr string showing the class name and either a dict
        representation (when all header names are unique) or the raw
        byte tuple list (when duplicates exist). This aids debugging
        and logging of header contents.

        Returns:
            str: A string of the form 'Headers({...})' for unique headers
            or 'Headers(raw=[...])' when duplicate header names exist.

        Raises:
            None: No exceptions are raised during representation.
        """
        class_name = self.__class__.__name__
        as_dict = dict(self.items())
        if len(as_dict) == len(self):
            return f"{class_name}({as_dict!r})"
        return f"{class_name}(raw={self.raw!r})"


class MutableHeaders(Headers):
    """
    A mutable variant of Headers that supports header modification operations.

    Extends the immutable Headers class with methods for setting, deleting,
    updating, and appending headers. Maintains case-insensitive header name
    handling and stores headers as raw byte tuples internally. Use
    ``Headers.mutablecopy()`` to obtain a MutableHeaders from an existing
    Headers instance.
    """

    def __setitem__(self, key: str, value: str) -> None:
        """
        Set a header to the given value, removing any duplicate entries.

        Searches for existing headers with the given name using case-insensitive
        comparison. If found, replaces the first occurrence with the new value
        and removes all subsequent duplicates. If not found, appends the new
        header to the end of the list. Preserves insertion order.

        Args:
            key: The header name to set. Will be lowercased and encoded
                to bytes for storage.
            value: The header value to associate with the key. Will be
                encoded to bytes using latin-1 encoding.

        Raises:
            None: No exceptions are raised during the set operation.
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
        Remove all header entries with the given name (case-insensitive).

        Searches the internal header list for all entries matching the
        given header name using case-insensitive comparison and removes
        them all. If no matching headers exist, the operation is a no-op.

        Args:
            key: The header name to remove. Comparison is case-insensitive
                as per HTTP specification requirements.

        Raises:
            None: No exceptions are raised even if the header does not exist.
        """
        del_key = key.lower().encode("latin-1")

        pop_indexes: "typing.List[int]" = []
        for idx, (item_key, _) in enumerate(self._list):
            if item_key == del_key:
                pop_indexes.append(idx)

        for idx in reversed(pop_indexes):
            del self._list[idx]

    def __ior__(self, other: typing.Mapping[str, str]) -> "MutableHeaders":
        """
        Update headers in-place using the |= operator with a mapping.

        Merges all key-value pairs from the provided mapping into this
        MutableHeaders instance, replacing any existing headers with
        matching names. Modifies this instance in place and returns it.

        Args:
            other: A mapping of header names to values to merge into
                this MutableHeaders instance.

        Returns:
            MutableHeaders: This instance after being updated in place.

        Raises:
            TypeError: If other is not a Mapping instance.
        """
        if not isinstance(other, typing.Mapping):
            raise TypeError(f"Expected a mapping but got {other.__class__.__name__}")
        self.update(other)
        return self

    def __or__(self, other: typing.Mapping[str, str]) -> "MutableHeaders":
        """
        Create a new MutableHeaders by merging with a mapping using | operator.

        Creates a copy of this MutableHeaders and merges the provided
        mapping into it, replacing any existing headers with matching
        names. The original instance is not modified.

        Args:
            other: A mapping of header names to values to merge into
                the new MutableHeaders copy.

        Returns:
            MutableHeaders: A new MutableHeaders instance containing
            the merged headers from both sources.

        Raises:
            TypeError: If other is not a Mapping instance.
        """
        if not isinstance(other, typing.Mapping):
            raise TypeError(f"Expected a mapping but got {other.__class__.__name__}")
        new = self.mutablecopy()
        new.update(other)
        return new

    @property
    def raw(self) -> typing.List[typing.Tuple[bytes, bytes]]:
        """
        Return the raw header byte tuples for ASGI message construction.

        Provides direct access to the internal header storage as a list
        of byte tuple pairs. Unlike the immutable Headers class, this
        returns the actual internal list reference, allowing direct
        manipulation when needed for ASGI message handling.

        Returns:
            List[Tuple[bytes, bytes]]: The internal list of lowercase
            header name and value byte pairs.

        Raises:
            None: No exceptions are raised during access.
        """
        return self._list

    def setdefault(self, key: str, value: str) -> str:
        """
        Set a header value only if the header name does not already exist.

        Searches for an existing header with the given name using
        case-insensitive comparison. If found, returns the existing
        value without modification. If not found, appends the new
        header with the provided value and returns that value.

        Args:
            key: The header name to check and optionally set. Will be
                lowercased and encoded to bytes for comparison.
            value: The header value to set if the key does not exist.
                Will be encoded to bytes using latin-1 encoding.

        Returns:
            str: The existing header value if the key was found, or
            the newly set value if the key was not present.

        Raises:
            None: No exceptions are raised during the operation.
        """
        set_key = key.lower().encode("latin-1")
        set_value = value.encode("latin-1")

        for _, (item_key, item_value) in enumerate(self._list):
            if item_key == set_key:
                return item_value.decode("latin-1")
        self._list.append((set_key, set_value))
        return value

    def update(self, other: typing.Mapping[str, str]) -> None:
        """
        Update headers with key-value pairs from another mapping.

        Iterates over the provided mapping and sets each header using
        ``__setitem__``, which replaces any existing entries for each
        key. This allows bulk header updates from dictionaries or
        other Mapping objects.

        Args:
            other: A mapping of header names to values to merge into
                this MutableHeaders instance. Existing headers with
                matching names are replaced.

        Raises:
            None: No exceptions are raised during the update operation.
        """
        for key, val in other.items():
            self[key] = val

    def append(self, key: str, value: str) -> None:
        """
        Append a header, preserving any duplicate entries.

        Adds a new header entry to the internal list without checking
        for or removing existing entries with the same name. This is
        useful for headers that legitimately appear multiple times,
        such as Set-Cookie or Link headers.

        Args:
            key: The header name to append. Will be lowercased and
                encoded to bytes using latin-1 encoding.
            value: The header value to append. Will be encoded to
                bytes using latin-1 encoding.

        Raises:
            None: No exceptions are raised during the append operation.
        """
        append_key = key.lower().encode("latin-1")
        append_value = value.encode("latin-1")
        self._list.append((append_key, append_value))

    def add_vary_header(self, vary: str) -> None:
        """
        Add a value to the Vary header, combining with any existing value.

        Checks if a Vary header already exists. If it does, appends the
        new value to the existing value with a comma separator. If no
        Vary header exists, sets it to the provided value. This ensures
        proper Vary header construction for HTTP caching.

        Args:
            vary: The vary value to add to the Vary header, such as
                'Accept-Encoding' or 'Accept-Language'.

        Raises:
            None: No exceptions are raised during the operation.
        """
        existing = self.get("vary")
        if existing is not None:
            vary = ", ".join([existing, vary])
        self["vary"] = vary


class UploadedFile:
    """
    Represents an uploaded file included as part of request data.

    Wraps a file object with metadata about the upload including filename,
    size, and headers. Supports both in-memory and disk-backed file storage
    via SpooledTemporaryFile. Provides async methods for reading, writing,
    seeking, and closing the file, with automatic threadpool delegation for
    disk-based operations to avoid blocking the event loop.
    """

    def __init__(
        self,
        file: typing.Any,
        *,
        size: typing.Optional[int] = None,
        filename: typing.Optional[str] = None,
        headers: typing.Optional[Headers] = None,
    ) -> None:
        """
        Initialize an UploadedFile with file object and metadata.

        Wraps the provided file object with upload metadata. The file can
        be either an in-memory BytesIO or a SpooledTemporaryFile that may
        roll over to disk. Size tracking is maintained automatically on
        write operations. Headers provide access to content-type and other
        multipart form field metadata.

        Args:
            file: The file object to wrap. Can be BytesIO, SpooledTemporaryFile,
                or any file-like object supporting read/write/seek/close.
            size: The initial size of the file in bytes. Defaults to None
                if not known. Updated automatically on write operations.
            filename: The original filename from the upload. Defaults to None
                if not provided by the client.
            headers: Headers associated with this file from the multipart
                form data. Defaults to empty Headers if not provided.

        Raises:
            None: No exceptions are raised during initialization.
        """
        self.filename = filename
        self.file = file
        self.size = size
        self.headers = headers or Headers()

    @property
    def content_type(self) -> typing.Union[str, None]:
        """
        Return the MIME content type of the uploaded file.

        Retrieves the content-type header value from the file's headers,
        which indicates the MIME type of the uploaded file as reported
        by the client. Returns None if no content-type header is present.

        Returns:
            str | None: The MIME content type string such as 'image/png'
            or 'application/pdf', or None if not specified.

        Raises:
            None: No exceptions are raised during access.
        """
        return self.headers.get("content-type", None)

    @property
    def _in_memory(self) -> bool:
        """
        Determine whether the file data is currently stored in memory.

        Checks the SpooledTemporaryFile's _rolled attribute to determine
        if the file has been rolled over to disk. Files that have not
        rolled are considered in-memory and can be accessed synchronously
        without blocking the event loop.

        Returns:
            bool: True if the file is stored in memory (not rolled to disk),
            False if it has been rolled to disk storage.

        Raises:
            None: No exceptions are raised during the check.
        """
        # check for SpooledTemporaryFile._rolled
        rolled_to_disk = getattr(self.file, "_rolled", True)
        return not rolled_to_disk

    async def write(self, data: bytes) -> None:
        """
        Write data to the uploaded file asynchronously.

        Writes the provided bytes to the underlying file object. Updates
        the size tracker if size tracking is enabled. For in-memory files,
        writes directly; for disk-backed files, delegates to a threadpool
        to avoid blocking the event loop.

        Args:
            data: The bytes to write to the file.

        Returns:
            None: This method does not return a value.

        Raises:
            IOError: If the write operation fails on the underlying file.
        """
        if self.size is not None:
            self.size += len(data)

        if self._in_memory:
            self.file.write(data)
        else:
            await run_in_threadpool(self.file.write, data)

    async def read(self, size: int = -1) -> bytes:
        """
        Read data from the uploaded file asynchronously.

        Reads up to the specified number of bytes from the underlying file
        object. For in-memory files, reads directly; for disk-backed files,
        delegates to a threadpool to avoid blocking the event loop.

        Args:
            size: The maximum number of bytes to read. Defaults to -1,
                which reads the entire file contents.

        Returns:
            bytes: The data read from the file as a bytes object. Returns
            an empty bytes object if at end of file.

        Raises:
            IOError: If the read operation fails on the underlying file.
        """
        if self._in_memory:
            return self.file.read(size)
        return await run_in_threadpool(self.file.read, size)

    async def seek(self, offset: int) -> None:
        """
        Seek to a position in the uploaded file asynchronously.

        Changes the file position indicator to the specified offset.
        For in-memory files, seeks directly; for disk-backed files,
        delegates to a threadpool to avoid blocking the event loop.

        Args:
            offset: The byte offset to seek to in the file. The
                interpretation depends on the file's seek mode.

        Returns:
            None: This method does not return a value.

        Raises:
            IOError: If the seek operation fails on the underlying file.
        """
        if self._in_memory:
            self.file.seek(offset)
        else:
            await run_in_threadpool(self.file.seek, offset)

    async def close(self) -> None:
        """
        Close the uploaded file asynchronously.

        Closes the underlying file object, releasing any system resources
        associated with it. For in-memory files, closes directly; for
        disk-backed files, delegates to a threadpool to avoid blocking
        the event loop. After closing, further read/write operations
        will fail.

        Returns:
            None: This method does not return a value.

        Raises:
            IOError: If the close operation fails on the underlying file.
        """
        if self._in_memory:
            self.file.close()
        else:
            await run_in_threadpool(self.file.close)

    async def save(self, destination: typing.Union[str, os.PathLike[str]]) -> None:
        """
        Save the uploaded file to a destination path on disk.

        Copies the file contents to the specified destination path.
        For in-memory files, uses shutil.copyfileobj to copy to a new
        file opened at the destination. For disk-backed files, delegates
        the copy operation to a threadpool to avoid blocking the event
        loop.

        Args:
            destination: The file system path where the uploaded file
                should be saved. Can be a string path or os.PathLike object.

        Returns:
            None: This method does not return a value.

        Raises:
            IOError: If the file cannot be written to the destination path.
            OSError: If the destination directory does not exist or is
                not writable.
        """
        if self._in_memory:
            # Copy from the start regardless of where the caller left the
            # cursor. A handler that inspects the upload before saving it
            # leaves the stream at EOF, which would otherwise write an empty
            # file with no error.
            self.file.seek(0)
            with open(destination, "wb") as f:
                shutil.copyfileobj(self.file, f)
        else:
            await run_in_threadpool(self._save_to_disk, destination)

    def _save_to_disk(self, destination: typing.Union[str, os.PathLike[str]]) -> None:
        """
        Save the uploaded file to disk (synchronous helper for threadpool).

        Internal synchronous method that copies the file contents to the
        specified destination path. Called by the async ``save`` method
        via ``run_in_threadpool`` when the file is stored on disk. Uses
        shutil.copyfileobj for efficient streaming copy.

        Args:
            destination: The file system path where the uploaded file
                should be saved. Can be a string path or os.PathLike object.

        Returns:
            None: This method does not return a value.

        Raises:
            IOError: If the file cannot be written to the destination path.
            OSError: If the destination directory does not exist or is
                not writable.
        """
        self.file.seek(0)
        with open(destination, "wb") as f:
            shutil.copyfileobj(self.file, f)

    def __repr__(self) -> str:
        """
        Return a developer-friendly string representation of the UploadedFile.

        Produces a repr string showing the class name and key metadata
        including filename, size, and headers. This aids debugging and
        logging of uploaded file information without exposing file contents.

        Returns:
            str: A string of the form 'UploadedFile(filename=..., size=...,
            headers=...)' showing the file's metadata.

        Raises:
            None: No exceptions are raised during representation.
        """
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
        """
        Provide Pydantic core schema for UploadedFile validation.

        Defines how Pydantic should validate UploadedFile instances by
        treating them as bytes during validation. This allows UploadedFile
        to be used in Pydantic models and validated as binary data.

        Args:
            source: The source type being validated (UploadedFile class).
            handler: The Pydantic schema handler for generating sub-schemas.

        Returns:
            core_schema.CoreSchema: A Pydantic core schema that validates
            the input as bytes and then constructs an UploadedFile instance.

        Raises:
            None: No exceptions are raised during schema generation.
        """
        # treat this type as bytes in validation
        return core_schema.no_info_after_validator_function(
            cls, core_schema.bytes_schema()
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: core_schema.CoreSchema, handler: GetJsonSchemaHandler
    ) -> dict[str, str]:
        """
        Provide Pydantic JSON schema for OpenAPI documentation generation.

        Defines how UploadedFile should be represented in JSON Schema and
        OpenAPI documentation. Represents the file as a string with binary
        format, which is the standard OpenAPI representation for file uploads.

        Args:
            core_schema: The Pydantic core schema for this type.
            handler: The Pydantic JSON schema handler for generating schemas.

        Returns:
            dict[str, str]: A JSON Schema dictionary with type 'string' and
            format 'binary' for OpenAPI file upload representation.

        Raises:
            None: No exceptions are raised during schema generation.
        """
        # represent in OpenAPI as a file upload
        return {
            "type": "string",
            "format": "binary",
        }


class FormData(MultiDict[str, typing.Union[UploadedFile, str, Sequence[Any]]]):
    """
    A mutable multidict for HTTP form data supporting file uploads.

    Extends MultiDict to handle form data from multipart/form-data and
    application/x-www-form-urlencoded requests. Values can be strings
    for regular form fields or UploadedFile instances for file uploads.
    Provides async close method to properly clean up uploaded file resources.
    """

    def __init__(
        self,
        *args: typing.Union[
            FormData,
            typing.Mapping[str, typing.Union[str, UploadedFile]],
            list[tuple[str, typing.Union[str, UploadedFile]]],
        ],
        **kwargs: typing.Union[str, UploadedFile],
    ) -> None:
        """
        Initialize FormData from various input formats.

        Constructs a FormData instance from another FormData, a mapping of
        field names to values, or a list of (name, value) tuples. Values
        can be strings for regular fields or UploadedFile instances for
        file uploads. Supports keyword arguments for additional fields.

        Args:
            *args: Positional arguments that can be a FormData instance,
                a Mapping of field names to values, or a list of tuples.
            **kwargs: Additional field name-value pairs to include in
                the form data.

        Raises:
            AssertionError: If more than one positional argument is provided.
        """
        super().__init__(*args, **kwargs)

    async def close(self) -> None:
        """
        Close all uploaded files in the form data asynchronously.

        Iterates through all values in the form data and closes any
        UploadedFile instances to release file handles and system
        resources. String values are ignored. This should be called
        after processing the form data to prevent resource leaks.

        Returns:
            None: This method does not return a value.

        Raises:
            IOError: If closing an uploaded file fails.
        """
        for _, value in self.multi_items():
            if isinstance(value, UploadedFile):
                await value.close()

    def get(
        self, key: str, default: typing.Any = None
    ) -> typing.Union[UploadedFile, str, None]:
        """
        Get a form field value by key with an optional default.

        Retrieves the last stored value for the given field name from
        the form data. Returns the value as either a string for regular
        fields or an UploadedFile for file uploads. If the key does not
        exist, returns the provided default value.

        Args:
            key: The form field name to look up in the form data.
            default: The value to return if the key is not found.
                Defaults to None if not explicitly provided.

        Returns:
            UploadedFile | str | None: The field value (string or uploaded
            file) if found, or the default value if the key does not exist.

        Raises:
            None: No exceptions are raised; returns default for missing keys.
        """
        return super().get(key, default)
