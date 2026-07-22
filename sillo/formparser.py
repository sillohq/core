from __future__ import annotations

import typing
import urllib.parse
from dataclasses import dataclass, field
from enum import Enum
from tempfile import SpooledTemporaryFile

from sillo.objects import FormData, Headers, UploadedFile

if typing.TYPE_CHECKING:
    import multipart
    from multipart.multipart import (
        parse_options_header,
    )
else:
    try:
        try:
            import python_multipart as multipart
            from python_multipart.multipart import parse_options_header
        except ModuleNotFoundError:
            import multipart
            from multipart.multipart import parse_options_header
    except ModuleNotFoundError:
        multipart = None
        parse_options_header = None


class FormMessage(Enum):
    """Enumeration of message types emitted during multipart form parsing.

    Each member represents a distinct phase in the lifecycle of a form field
    being parsed by the multipart parser callbacks. These messages are queued
    internally and consumed by the form data assembly logic.

    Attributes:
        FIELD_START: Indicates the beginning of a new form field.
        FIELD_NAME: Carries the name of the current form field.
        FIELD_DATA: Carries a chunk of data for the current form field.
        FIELD_END: Indicates the end of the current form field.
        END: Indicates that the entire multipart body has been fully parsed.
    """

    FIELD_START = 1
    FIELD_NAME = 2
    FIELD_DATA = 3
    FIELD_END = 4
    END = 5


@dataclass
class MultipartPart:
    """Represents a single part within a multipart form-data request body.

    This dataclass accumulates the raw data, headers, and metadata for one
    part as the multipart parser processes the incoming byte stream. It is
    used internally by ``MultiPartParser`` to build up field values and
    uploaded file objects before they are assembled into ``FormData``.

    Attributes:
        content_disposition: The raw Content-Disposition header bytes for
            this part, if present. Used to extract ``name`` and ``filename``.
        field_name: The decoded name of the form field this part belongs to.
        data: A mutable byte buffer that accumulates chunked field data for
            non-file parts. File parts write to ``file`` instead.
        file: An ``UploadedFile`` instance for file uploads. Remains ``None``
            for regular form fields that carry no filename.
        item_headers: A list of raw header tuples ``(name, value)`` parsed
            from this part's header section, stored as bytes.
    """

    content_disposition: typing.Optional[bytes] = None
    field_name: str = ""
    data: bytearray = field(default_factory=bytearray)
    file: typing.Optional[UploadedFile] = None
    item_headers: list[tuple[bytes, bytes]] = field(default_factory=list)


def _user_safe_decode(src: typing.Union[bytes, bytearray], codec: str) -> str:
    """Decode a byte sequence using the specified codec with a safe fallback.

    Attempts to decode the given bytes or bytearray using the provided codec
    name. If the codec is unrecognized or the byte sequence contains invalid
    data for that encoding, the function falls back to decoding with Latin-1,
    which can decode any arbitrary byte sequence without raising an error.

    This is used throughout the form parser to safely decode field names,
    filenames, and header values that may contain non-UTF-8 data.

    Args:
        src: The byte sequence to decode. May be either a ``bytes`` object
            or a mutable ``bytearray``.
        codec: The name of the codec to attempt first (e.g. ``"utf-8"``,
            ``"latin-1"``). Must be a valid Python codec name.

    Returns:
        The decoded string. If the primary codec fails, the string is
        decoded using Latin-1 as a lossless fallback.

    Raises:
        No exceptions are raised; all decoding errors are caught internally.
    """
    try:
        return src.decode(codec)
    except (UnicodeDecodeError, LookupError):
        return src.decode("latin-1")


class MultiPartException(Exception):
    """Exception raised when a multipart form body cannot be parsed.

    This exception is raised by the ``MultiPartParser`` when the incoming
    multipart body violates structural constraints such as missing required
    Content-Disposition fields, exceeding the maximum number of files or
    fields, or other protocol-level errors.

    The exception carries a human-readable error message that describes
    the specific parsing failure and can be returned directly to the
    client as part of an error response.

    Attributes:
        message: A human-readable description of the multipart parsing
            error that occurred.

    Args:
        message: A string describing the reason the multipart body
            could not be parsed successfully.
    """

    def __init__(self, message: str) -> None:
        self.message = message


class FormParser:
    """High-level form parser that dispatches to the appropriate parsing strategy.

    Inspects the ``Content-Type`` header of the incoming request to determine
    whether the body is ``multipart/form-data`` or URL-encoded form data, then
    delegates to the correct parser implementation. For multipart bodies, it
    creates a ``MultiPartParser`` instance; for URL-encoded bodies, it reads
    the entire stream and decodes the query-string format directly.

    This class acts as the main entry point for form parsing in the framework
    and is typically instantiated by request handling code rather than by
    end users directly.

    Attributes:
        headers: The request headers used to determine the content type and
            extract parsing parameters such as boundary and charset.
        stream: An async generator yielding raw byte chunks from the request
            body. The stream is consumed exactly once during parsing.
        messages: A list of ``(FormMessage, bytes)`` tuples accumulated by
            the callback methods during URL-encoded parsing.

    Args:
        headers: The ``Headers`` object from the incoming HTTP request.
        stream: An async generator of byte chunks representing the request
            body to be parsed.
    """

    def __init__(
        self, headers: Headers, stream: typing.AsyncGenerator[bytes, None]
    ) -> None:
        assert multipart is not None, (
            "The `python-multipart` library must be installed to use form parsing."
        )
        self.headers = headers
        self.stream = stream
        self.messages: list[tuple[FormMessage, bytes]] = []

    def on_field_start(self) -> None:
        """Handle the start of a new form field during URL-encoded parsing.

        Appends a ``FIELD_START`` message to the internal messages list to
        signal that a new form field has begun being processed. This callback
        is invoked by the underlying multipart parser when it encounters the
        beginning of a new field boundary in the request body.

        Returns:
            None. This method mutates ``self.messages`` in place.
        """
        message = (FormMessage.FIELD_START, b"")
        self.messages.append(message)

    def on_field_name(self, data: bytes, start: int, end: int) -> None:
        """Handle a chunk of field name data during URL-encoded parsing.

        Extracts the relevant slice of the incoming data buffer and appends
        a ``FIELD_NAME`` message containing the field name bytes. This is
        called one or more times as the parser reads the name portion of
        a URL-encoded form field.

        Args:
            data: The raw byte buffer containing the field name data.
            start: The starting index (inclusive) within ``data`` where
                the field name chunk begins.
            end: The ending index (exclusive) within ``data`` where the
                field name chunk ends.

        Returns:
            None. This method mutates ``self.messages`` in place.
        """
        message = (FormMessage.FIELD_NAME, data[start:end])
        self.messages.append(message)

    def on_field_data(self, data: bytes, start: int, end: int) -> None:
        """Handle a chunk of field value data during URL-encoded parsing.

        Extracts the relevant slice of the incoming data buffer and appends
        a ``FIELD_DATA`` message containing the field value bytes. This is
        called one or more times as the parser reads the value portion of
        a URL-encoded form field.

        Args:
            data: The raw byte buffer containing the field value data.
            start: The starting index (inclusive) within ``data`` where
                the field value chunk begins.
            end: The ending index (exclusive) within ``data`` where the
                field value chunk ends.

        Returns:
            None. This method mutates ``self.messages`` in place.
        """
        message = (FormMessage.FIELD_DATA, data[start:end])
        self.messages.append(message)

    def on_field_end(self) -> None:
        """Handle the end of a form field during URL-encoded parsing.

        Appends a ``FIELD_END`` message to the internal messages list to
        signal that the current form field has been fully read. This callback
        is invoked after all name and data chunks for the field have been
        processed.

        Returns:
            None. This method mutates ``self.messages`` in place.
        """
        message = (FormMessage.FIELD_END, b"")
        self.messages.append(message)

    def on_end(self) -> None:
        """Handle the completion of the entire form parsing process.

        Appends an ``END`` message to the internal messages list to signal
        that the full request body has been consumed and no more data will
        arrive. This is the final callback invoked during the parsing
        lifecycle.

        Returns:
            None. This method mutates ``self.messages`` in place.
        """
        message = (FormMessage.END, b"")
        self.messages.append(message)

    async def parse(self) -> FormData:
        """Parse the request stream as form data.

        Examines the ``Content-Type`` header to determine the encoding format.
        If the content type is ``multipart/form-data``, delegates to an
        internal ``MultiPartParser`` to handle boundary-delimited parts.
        Otherwise, treats the body as ``application/x-www-form-urlencoded``,
        reading the full stream into memory and decoding the query-string
        pairs using UTF-8 with a Latin-1 fallback.

        The method handles URL decoding of values and supports blank values.
        If the initial UTF-8 decode fails, a second attempt is made with
        Latin-1 encoding. If both attempts fail, an empty ``FormData`` is
        returned rather than raising an error.

        Returns:
            A ``FormData`` instance containing all parsed key-value pairs
            and any uploaded file objects from the request body.
        """
        content_type = self.headers.get("content-type", "")
        if content_type.startswith("multipart/form-data"):
            multipart_parser = MultiPartParser(self.headers, self.stream)
            return await multipart_parser.parse()

        # Default to application/x-www-form-urlencoded
        form = FormData()
        content = b""

        # Collect all chunks into a single content buffer
        async for chunk in self.stream:
            if chunk:
                content += chunk

        if content:
            try:
                # Use parse_qsl to get a list of key-value pairs
                field_items = urllib.parse.parse_qsl(
                    content.decode("utf-8"), keep_blank_values=True
                )

                # Add each field to the form data
                for key, value in field_items:
                    # URL decode the value to handle special characters
                    decoded_value = urllib.parse.unquote(value)
                    form.append(key, decoded_value)
            except (UnicodeDecodeError, ValueError):
                # If there's a decoding error, try with latin-1 encoding
                try:
                    field_items = urllib.parse.parse_qsl(
                        content.decode("latin-1"), keep_blank_values=True
                    )
                    for key, value in field_items:
                        decoded_value = urllib.parse.unquote(value)
                        form.append(key, decoded_value)
                except Exception:
                    # If still can't parse, return empty form
                    pass

        return form


class MultiPartParser:
    """Low-level parser for ``multipart/form-data`` request bodies.

    Processes a multipart-encoded HTTP request body by feeding raw byte chunks
    into a ``python-multipart`` parser instance and handling callbacks for each
    part boundary, header, and data segment. Assembles parsed fields and file
    uploads into a ``FormData`` object.

    Enforces configurable limits on the maximum number of fields and files
    to prevent abuse from excessively large multipart payloads. File data is
    written to ``SpooledTemporaryFile`` instances that are kept in memory up
    to ``max_file_size`` bytes before being flushed to disk.

    Attributes:
        max_file_size: Maximum size in bytes before a file is spooled to disk.
        max_part_size: Maximum allowed size for a single non-file part.
        max_fields: Maximum number of non-file form fields allowed.
        max_files: Maximum number of file uploads allowed.

    Args:
        headers: The request headers containing the Content-Type with boundary.
        stream: An async generator yielding raw byte chunks from the body.
        max_fields: Optional override for the maximum number of form fields.
            Defaults to the class-level ``max_fields`` attribute.
        max_files: Optional override for the maximum number of file uploads.
            Defaults to the class-level ``max_files`` attribute.
    """

    max_file_size = 1024 * 1024  # 1MB
    max_part_size = 1024 * 1024  # 1MB
    max_fields = 1000
    max_files = 1000

    def __init__(
        self,
        headers: Headers,
        stream: typing.AsyncGenerator[bytes, None],
        *,
        max_fields: typing.Optional[int] = None,
        max_files: typing.Optional[int] = None,
    ) -> None:
        """Initialize the multipart parser with request context and limits.

        Sets up internal state for tracking the current part being parsed,
        accumulated items, file size counters, and pending write/finish
        operations. Validates that the ``python-multipart`` library is
        available before proceeding.

        Args:
            headers: The request headers containing the Content-Type with
                boundary and charset parameters for the multipart body.
            stream: An async generator yielding raw byte chunks from the
                HTTP request body to be parsed.
            max_fields: Optional override for the maximum number of
                non-file form fields allowed. If ``None``, uses the
                class-level default of 1000.
            max_files: Optional override for the maximum number of file
                uploads allowed. If ``None``, uses the class-level
                default of 1000.

        Raises:
            AssertionError: If the ``python-multipart`` library is not
                installed in the current environment.
        """
        assert multipart is not None, (
            "The `python-multipart` library must be installed to use form parsing."
        )
        self.headers = headers
        self.stream = stream
        self.max_files = max_files if max_files is not None else self.max_files
        self.max_fields = max_fields if max_fields is not None else self.max_fields
        self.items: list[tuple[str, typing.Union[str, UploadedFile]]] = []
        self._current_files = 0
        self._current_fields = 0
        self._current_partial_header_name: bytes = b""
        self._current_partial_header_value: bytes = b""
        self._current_part = MultipartPart()
        self._charset = ""
        self._file_parts_to_write: list[tuple[MultipartPart, bytes]] = []
        self._file_parts_to_finish: list[MultipartPart] = []
        self._files_to_close_on_error: list[SpooledTemporaryFile[bytes]] = []

    def on_part_begin(self) -> None:
        """Handle the beginning of a new multipart part.

        Resets the current part state by creating a fresh ``MultipartPart``
        instance. This callback is invoked by the underlying multipart parser
        whenever a new boundary delimiter is encountered in the request body,
        indicating the start of a new form field or file upload.

        Returns:
            None. This method resets ``self._current_part`` in place.
        """
        self._current_part = MultipartPart()

    def on_part_data(self, data: bytes, start: int, end: int) -> None:
        """Handle a chunk of data for the current multipart part.

        Routes the incoming data to either the in-memory field buffer or the
        deferred file write queue, depending on whether the current part is
        a regular form field or a file upload. For file parts, the data is
        queued for asynchronous writing to avoid blocking the event loop.

        Args:
            data: The raw byte buffer containing the part data chunk.
            start: The starting index (inclusive) within ``data`` where
                the relevant chunk begins.
            end: The ending index (exclusive) within ``data`` where the
                relevant chunk ends.

        Returns:
            None. Mutates internal buffers or write queues in place.
        """
        message_bytes = data[start:end]
        if self._current_part.file is None:
            # if len(self._current_part.data) + len(message_bytes) > self.max_part_size:
            #     raise MultiPartException(
            #         f"Part exceeded maximum size of {int(self.max_part_size / 1024)}KB."
            #     ) might reimplemented in further versions
            self._current_part.data.extend(message_bytes)
        else:
            # Check file size limit when writing file parts
            # if self._current_part.file and self._current_part.file.size is not None:
            # new_size = self._current_part.file.size + len(message_bytes)
            # if new_size > self.max_file_size:
            #     raise MultiPartException(
            #         f"File too large. Maximum size is {self.max_file_size} bytes"
            #     ) might reimplemented in further versions
            self._file_parts_to_write.append((self._current_part, message_bytes))

    def on_part_end(self) -> None:
        """Handle the end of the current multipart part.

        Finalizes the current part by either appending the decoded field value
        to the items list (for regular fields) or queuing the file for
        completion and appending the ``UploadedFile`` reference to the items
        list (for file uploads). File data is not yet flushed at this point;
        that occurs during the ``parse()`` method.

        Returns:
            None. Mutates ``self.items`` and internal queues in place.
        """
        if self._current_part.file is None:
            self.items.append(
                (
                    self._current_part.field_name,
                    _user_safe_decode(
                        self._current_part.data,
                        self._charset,
                    ),
                )
            )
        else:
            self._file_parts_to_finish.append(self._current_part)
            # The file can be added to the items right now even though it's not
            # finished yet, because it will be finished in the `parse()` method, before
            # self.items is used in the return value.
            self.items.append((self._current_part.field_name, self._current_part.file))

    def on_header_field(self, data: bytes, start: int, end: int) -> None:
        """Handle a chunk of header field name data for the current part.

        Appends the relevant slice of the incoming data buffer to the
        partial header name accumulator. Header field names may arrive
        in multiple chunks, so this method concatenates them incrementally
        until ``on_header_end`` is called.

        Args:
            data: The raw byte buffer containing the header field name.
            start: The starting index (inclusive) within ``data`` where
                the header name chunk begins.
            end: The ending index (exclusive) within ``data`` where the
                header name chunk ends.

        Returns:
            None. Mutates ``self._current_partial_header_name`` in place.
        """
        self._current_partial_header_name += data[start:end]

    def on_header_value(self, data: bytes, start: int, end: int) -> None:
        """Handle a chunk of header field value data for the current part.

        Appends the relevant slice of the incoming data buffer to the
        partial header value accumulator. Header field values may arrive
        in multiple chunks, so this method concatenates them incrementally
        until ``on_header_end`` is called.

        Args:
            data: The raw byte buffer containing the header field value.
            start: The starting index (inclusive) within ``data`` where
                the header value chunk begins.
            end: The ending index (exclusive) within ``data`` where the
                header value chunk ends.

        Returns:
            None. Mutates ``self._current_partial_header_value`` in place.
        """
        self._current_partial_header_value += data[start:end]

    def on_header_end(self) -> None:
        """Handle the completion of a single header within the current part.

        Processes the fully accumulated header field name and value by storing
        them as a tuple in the current part's item headers list. If the header
        is ``Content-Disposition``, its raw value is also stored separately
        on the part for later extraction of ``name`` and ``filename``
        parameters. Resets the partial header accumulators for the next header.

        Returns:
            None. Mutates ``self._current_part`` and resets partial
            header accumulators in place.
        """
        field = self._current_partial_header_name.lower()
        if field == b"content-disposition":
            self._current_part.content_disposition = self._current_partial_header_value
        self._current_part.item_headers.append(
            (field, self._current_partial_header_value)
        )
        self._current_partial_header_name = b""
        self._current_partial_header_value = b""

    def on_headers_finished(self) -> None:
        """Handle the completion of all headers for the current part.

        Parses the ``Content-Disposition`` header to extract the field name
        and, optionally, the filename. If a filename is present, the part
        is treated as a file upload: a ``SpooledTemporaryFile`` is created
        and wrapped in an ``UploadedFile``. Otherwise, the part is treated
        as a regular form field.

        Enforces the maximum file and field count limits, raising
        ``MultiPartException`` if exceeded.

        Raises:
            MultiPartException: If the ``Content-Disposition`` header is
                missing the required ``name`` field, or if the number of
                files or fields exceeds the configured maximums.

        Returns:
            None. Mutates ``self._current_part`` and internal counters
            in place.
        """
        _, options = parse_options_header(self._current_part.content_disposition)
        try:
            self._current_part.field_name = _user_safe_decode(
                options[b"name"],
                self._charset,
            )
        except KeyError:
            raise MultiPartException(
                'The Content-Disposition header field "name" must be provided.'
            )
        if b"filename" in options:
            self._current_files += 1
            if self._current_files > self.max_files:
                raise MultiPartException(
                    f"Too many files. Maximum number of files is {self.max_files}."
                )
            filename = _user_safe_decode(
                options[b"filename"],
                self._charset,
            )
            tempfile = SpooledTemporaryFile(max_size=self.max_file_size)
            self._files_to_close_on_error.append(tempfile)
            self._current_part.file = UploadedFile(
                file=tempfile,
                size=0,
                filename=filename,
                headers=Headers(raw=self._current_part.item_headers),
            )
        else:
            self._current_fields += 1
            if self._current_fields > self.max_fields:
                raise MultiPartException(
                    f"Too many fields. Maximum number of fields is {self.max_fields}."
                )
            self._current_part.file = None

    def on_end(self) -> None:
        """Handle the end of the entire multipart body.

        This is a no-op callback invoked by the underlying multipart parser
        when the final boundary delimiter has been processed and the entire
        request body has been consumed. Provided to satisfy the callback
        interface expected by ``python-multipart``.

        Returns:
            None.
        """
        pass

    async def parse(self) -> FormData:
        """Parse the form data from the request body.

        Extracts the boundary and charset from the ``Content-Type`` header,
        configures the underlying ``python-multipart`` parser with the
        registered callbacks, and feeds the async byte stream into it
        chunk by chunk. After each chunk, pending file writes and seeks
        are awaited to avoid blocking the event loop.

        If a ``MultiPartException`` is raised during parsing, all opened
        temporary files are closed before the exception is re-raised to
        prevent resource leaks.

        Returns:
            A ``FormData`` instance populated with all parsed field
            name-value pairs and uploaded file objects. Returns an empty
            ``FormData`` if the content type is not multipart or the
            boundary is missing.

        Raises:
            MultiPartException: If the multipart body violates protocol
                constraints such as missing required headers or exceeding
                configured limits.
        """
        content_type = self.headers.get("content-type", "")
        content_type, params = parse_options_header(content_type)

        if content_type != b"multipart/form-data":
            return FormData()

        boundary = params.get(b"boundary")
        if not boundary:
            return FormData()

        charset = params.get(b"charset")
        self._charset = charset.decode("latin-1") if charset else "utf-8"

        callbacks = {
            "on_part_begin": self.on_part_begin,
            "on_part_data": self.on_part_data,
            "on_part_end": self.on_part_end,
            "on_header_field": self.on_header_field,
            "on_header_value": self.on_header_value,
            "on_header_end": self.on_header_end,
            "on_headers_finished": self.on_headers_finished,
            "on_end": self.on_end,
        }

        parser = multipart.MultipartParser(
            boundary,
            callbacks,  # ty:ignore[invalid-argument-type]
        )
        try:
            # Feed the parser with data from the request.
            async for chunk in self.stream:
                parser.write(chunk)
                # Write file data, it needs to use await with the UploadedFile methods
                # that call the corresponding file methods *in a threadpool*,
                # otherwise, if they were called directly in the callback methods above
                # (regular, non-async functions), that would block the event loop in
                # the main thread.
                for part, data in self._file_parts_to_write:
                    # assert part.file  # for type checkers
                    await part.file.write(data)  # ty: ignore[unresolved-attribute]
                for part in self._file_parts_to_finish:
                    assert part.file  # for type checkers
                    await part.file.seek(0)
                self._file_parts_to_write.clear()
                self._file_parts_to_finish.clear()
        except MultiPartException as exc:
            # Close all the files if there was an error.
            for file in self._files_to_close_on_error:
                file.close()
            raise exc

        parser.finalize()
        return FormData(self.items)
