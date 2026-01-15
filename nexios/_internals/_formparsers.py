from __future__ import annotations

import typing
import urllib.parse
from dataclasses import dataclass, field
from enum import Enum
from tempfile import SpooledTemporaryFile

from nexios.objects import FormData, Headers, UploadedFile

if typing.TYPE_CHECKING:
    import multipart  # type:ignore
    from multipart.multipart import (  # type:ignore
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
    FIELD_START = 1
    FIELD_NAME = 2
    FIELD_DATA = 3
    FIELD_END = 4
    END = 5


@dataclass
class MultipartPart:
    content_disposition: typing.Optional[bytes] = None
    field_name: str = ""
    data: bytearray = field(default_factory=bytearray)
    file: typing.Optional[UploadedFile] = None
    item_headers: list[tuple[bytes, bytes]] = field(default_factory=list)


def _user_safe_decode(src: typing.Union[bytes, bytearray], codec: str) -> str:
    try:
        return src.decode(codec)
    except (UnicodeDecodeError, LookupError):
        return src.decode("latin-1")


class MultiPartException(Exception):
    def __init__(self, message: str) -> None:
        self.message = message


class FormParser:
    def __init__(
        self, headers: Headers, stream: typing.AsyncGenerator[bytes, None]
    ) -> None:
        assert (
            multipart is not None
        ), "The `python-multipart` library must be installed to use form parsing."
        self.headers = headers
        self.stream = stream
        self.messages: list[tuple[FormMessage, bytes]] = []

    def on_field_start(self) -> None:
        message = (FormMessage.FIELD_START, b"")
        self.messages.append(message)

    def on_field_name(self, data: bytes, start: int, end: int) -> None:
        message = (FormMessage.FIELD_NAME, data[start:end])
        self.messages.append(message)

    def on_field_data(self, data: bytes, start: int, end: int) -> None:
        message = (FormMessage.FIELD_DATA, data[start:end])
        self.messages.append(message)

    def on_field_end(self) -> None:
        message = (FormMessage.FIELD_END, b"")
        self.messages.append(message)

    def on_end(self) -> None:
        message = (FormMessage.END, b"")
        self.messages.append(message)

    async def parse(self) -> FormData:
        """
        Parse the request stream as form data.

        Returns:
            FormData: The parsed form data.
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
        assert (
            multipart is not None
        ), "The `python-multipart` library must be installed to use form parsing."
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
        self._current_part = MultipartPart()

    def on_part_data(self, data: bytes, start: int, end: int) -> None:
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
        if self._current_part.file is None:
            self.items.append(
                (
                    self._current_part.field_name,
                    _user_safe_decode(
                        self._current_part.data,
                        self._charset,  # type: ignore
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
        self._current_partial_header_name += data[start:end]

    def on_header_value(self, data: bytes, start: int, end: int) -> None:
        self._current_partial_header_value += data[start:end]

    def on_header_end(self) -> None:
        field = self._current_partial_header_name.lower()
        if field == b"content-disposition":
            self._current_part.content_disposition = self._current_partial_header_value
        self._current_part.item_headers.append(
            (field, self._current_partial_header_value)
        )
        self._current_partial_header_name = b""
        self._current_partial_header_value = b""

    def on_headers_finished(self) -> None:
        _, options = parse_options_header(self._current_part.content_disposition)
        try:
            self._current_part.field_name = _user_safe_decode(
                options[b"name"],
                self._charset,  # type: ignore
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
                self._charset,  # type: ignore
            )  # type:ignore
            tempfile = SpooledTemporaryFile(max_size=self.max_file_size)
            self._files_to_close_on_error.append(tempfile)
            self._current_part.file = UploadedFile(
                file=tempfile,  # type: ignore[arg-type]
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
        pass

    async def parse(self) -> FormData:
        """Parse the form data from the request body."""
        content_type = self.headers.get("content-type", "")
        content_type, params = parse_options_header(content_type)

        if content_type != b"multipart/form-data":
            return FormData()

        boundary = params.get(b"boundary")
        if not boundary:
            return FormData()

        charset = params.get(b"charset")
        self._charset = charset.decode("latin-1") if charset else "utf-8"

        callbacks: typing.Dict[str, typing.Callable[..., typing.Any]] = {
            "on_part_begin": self.on_part_begin,
            "on_part_data": self.on_part_data,
            "on_part_end": self.on_part_end,
            "on_header_field": self.on_header_field,
            "on_header_value": self.on_header_value,
            "on_header_end": self.on_header_end,
            "on_headers_finished": self.on_headers_finished,
            "on_end": self.on_end,
        }

        parser = multipart.MultipartParser(boundary, callbacks)  # type:ignore
        try:
            # Feed the parser with data from the request.
            async for chunk in self.stream:
                parser.write(chunk)  # type:ignore
                # Write file data, it needs to use await with the UploadedFile methods
                # that call the corresponding file methods *in a threadpool*,
                # otherwise, if they were called directly in the callback methods above
                # (regular, non-async functions), that would block the event loop in
                # the main thread.
                for part, data in self._file_parts_to_write:
                    # assert part.file  # for type checkers
                    await part.file.write(data)  # type:ignore
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

        parser.finalize()  # type:ignore
        return FormData(self.items)
