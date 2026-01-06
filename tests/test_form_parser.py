from typing import AsyncGenerator

import pytest

from nexios import NexiosApp
from nexios.http import Request, Response
from nexios.http.formparsers import FormParser, MultiPartException, MultiPartParser
from nexios.objects import FormData, Headers, UploadedFile
from nexios.testing import Client

# Set default limits for MultiPartParser if they don't exist
if not hasattr(MultiPartParser, "max_file_size"):
    MultiPartParser.max_file_size = 1024 * 1024  # 1MB
if not hasattr(MultiPartParser, "max_fields"):
    MultiPartParser.max_fields = 1000
if not hasattr(MultiPartParser, "max_files"):
    MultiPartParser.max_files = 1000

# Create an application instance for testing
app = NexiosApp()


# Define test endpoints for form submission
@app.post("/form")
async def handle_form(request: Request, response: Response):
    form = await request.form_data
    return response.json({"fields": dict(form.items())})


@app.post("/upload")
async def handle_upload(request: Request, response: Response):
    form = await request.form_data
    files = {}
    fields = {}

    for key, value in form.items():
        if isinstance(value, UploadedFile):
            content = await value.read()
            files[key] = {
                "filename": value.filename,
                "content": content.decode("utf-8", errors="replace"),
                "size": value.size,
                "content_type": value.headers.get("content-type", ""),
            }
        else:
            fields[key] = value

    return response.json({"files": files, "fields": fields})


# Helper function to create a stream from bytes for testing parsers
async def create_form_stream(data: bytes) -> AsyncGenerator[bytes, None]:
    yield data


# Pytest fixture for client
@pytest.fixture
async def client():
    async with Client(app) as client:
        yield client


# Tests for basic form data parsing
async def test_basic_form_parsing():
    # Create simple form data
    form_data = b"name=John&age=30&email=john%40example.com"
    headers = Headers(
        [
            (b"content-type", b"application/x-www-form-urlencoded"),
            (b"content-length", str(len(form_data)).encode()),
        ]
    )

    # Parse the form data
    parser = FormParser(headers, create_form_stream(form_data))
    form = await parser.parse()

    # Verify parsed data
    assert isinstance(form, FormData)
    assert dict(form.items()) == {
        "name": "John",
        "age": "30",
        "email": "john@example.com",
    }


async def test_empty_form():
    form_data = b""
    headers = Headers(
        [
            (b"content-type", b"application/x-www-form-urlencoded"),
            (b"content-length", b"0"),
        ]
    )

    parser = FormParser(headers, create_form_stream(form_data))
    form = await parser.parse()

    assert isinstance(form, FormData)
    assert len(form) == 0


async def test_form_with_special_characters():
    # Test URL-encoded special characters
    form_data = b"message=Hello+World%21&symbols=%24%26%2B%2C%3A%3B%3D%3F%40"
    headers = Headers(
        [
            (b"content-type", b"application/x-www-form-urlencoded"),
            (b"content-length", str(len(form_data)).encode()),
        ]
    )

    parser = FormParser(headers, create_form_stream(form_data))
    form = await parser.parse()

    assert dict(form.items()) == {"message": "Hello World!", "symbols": "$&+,:;=?@"}


# Tests for multipart form data
async def test_multipart_text_fields():
    boundary = b"boundary123"
    form_data = (
        b"--" + boundary + b"\r\n"
        b'Content-Disposition: form-data; name="field1"\r\n\r\n'
        b"value1\r\n"
        b"--" + boundary + b"\r\n"
        b'Content-Disposition: form-data; name="field2"\r\n\r\n'
        b"value2\r\n"
        b"--" + boundary + b"--\r\n"
    )

    headers = Headers(
        [
            (b"content-type", b"multipart/form-data; boundary=" + boundary),
            (b"content-length", str(len(form_data)).encode()),
        ]
    )

    parser = MultiPartParser(headers, create_form_stream(form_data))
    form = await parser.parse()

    assert dict(form.items()) == {"field1": "value1", "field2": "value2"}


async def test_multipart_file_upload():
    boundary = b"boundary123"
    file_content = b"Hello, this is a test file content!"
    form_data = (
        b"--" + boundary + b"\r\n"
        b'Content-Disposition: form-data; name="file1"; filename="test.txt"\r\n'
        b"Content-Type: text/plain\r\n\r\n" + file_content + b"\r\n"
        b"--" + boundary + b"--\r\n"
    )

    headers = Headers(
        [
            (b"content-type", b"multipart/form-data; boundary=" + boundary),
            (b"content-length", str(len(form_data)).encode()),
        ]
    )

    parser = MultiPartParser(headers, create_form_stream(form_data))
    form = await parser.parse()

    assert len(form) == 1
    file = form.get("file1")
    assert isinstance(file, UploadedFile)
    assert file.filename == "test.txt"
    content = await file.read()
    assert content == file_content


async def test_multipart_mixed_content():
    boundary = b"boundary123"
    file_content = b"Test file content"
    form_data = (
        b"--" + boundary + b"\r\n"
        b'Content-Disposition: form-data; name="field1"\r\n\r\n'
        b"text_value\r\n"
        b"--" + boundary + b"\r\n"
        b'Content-Disposition: form-data; name="file1"; filename="test.txt"\r\n'
        b"Content-Type: text/plain\r\n\r\n" + file_content + b"\r\n"
        b"--" + boundary + b"--\r\n"
    )

    headers = Headers(
        [
            (b"content-type", b"multipart/form-data; boundary=" + boundary),
            (b"content-length", str(len(form_data)).encode()),
        ]
    )

    parser = MultiPartParser(headers, create_form_stream(form_data))
    form = await parser.parse()

    assert len(form) == 2
    assert form.get("field1") == "text_value"
    file = form.get("file1")
    assert isinstance(file, UploadedFile)
    content = await file.read()
    assert content == file_content


async def test_multipart_multiple_files():
    boundary = b"boundary123"
    file1_content = b"Content of file 1"
    file2_content = b"Content of file 2"
    form_data = (
        b"--" + boundary + b"\r\n"
        b'Content-Disposition: form-data; name="file1"; filename="file1.txt"\r\n'
        b"Content-Type: text/plain\r\n\r\n" + file1_content + b"\r\n"
        b"--" + boundary + b"\r\n"
        b'Content-Disposition: form-data; name="file2"; filename="file2.txt"\r\n'
        b"Content-Type: text/plain\r\n\r\n" + file2_content + b"\r\n"
        b"--" + boundary + b"--\r\n"
    )

    headers = Headers(
        [
            (b"content-type", b"multipart/form-data; boundary=" + boundary),
            (b"content-length", str(len(form_data)).encode()),
        ]
    )

    parser = MultiPartParser(headers, create_form_stream(form_data))
    form = await parser.parse()

    assert len(form) == 2
    file1 = form.get("file1")
    file2 = form.get("file2")

    assert isinstance(file1, UploadedFile)
    assert isinstance(file2, UploadedFile)

    assert file1.filename == "file1.txt"
    assert file2.filename == "file2.txt"

    content1 = await file1.read()
    content2 = await file2.read()

    assert content1 == file1_content
    assert content2 == file2_content


# Edge cases tests
# async def test_max_file_size_limit():
#     boundary = b"boundary123"
#     # Make file content slightly larger than the max file size
#     # This assumes MultiPartParser.max_file_size is accessible and not too large for testing
#     file_size = 1024 * 10  # Use a smaller size for testing
#     original_max_size = MultiPartParser.max_file_size
#     MultiPartParser.max_file_size = file_size

#     try:
#         file_content = b"x" * (file_size + 100)  # Exceed max file size
#         form_data = (
#             b"--" + boundary + b"\r\n"
#             b'Content-Disposition: form-data; name="file"; filename="large.txt"\r\n'
#             b"Content-Type: text/plain\r\n\r\n" + file_content + b"\r\n"
#             b"--" + boundary + b"--\r\n"
#         )

#         headers = Headers(
#             [
#                 (b"content-type", b"multipart/form-data; boundary=" + boundary),
#                 (b"content-length", str(len(form_data)).encode()),
#             ]
#         )

#         parser = MultiPartParser(headers, create_form_stream(form_data))

#         # This should raise an exception due to file size
#         with pytest.raises(MultiPartException):
#             await parser.parse()
#     finally:
#         # Restore original max file size
#         MultiPartParser.max_file_size = original_max_size


async def test_max_field_count_limit():
    # Test with more fields than max_fields
    max_fields = 5
    # Store original value
    original_max_fields = MultiPartParser.max_fields
    # Temporarily set max_fields to test value
    MultiPartParser.max_fields = max_fields

    try:
        # Create a multipart form with more than max_fields
        boundary = b"boundary123"
        parts = []
        for i in range(max_fields + 2):
            parts.append(
                b"--"
                + boundary
                + b"\r\n"
                + f'Content-Disposition: form-data; name="field{i}"\r\n\r\n'.encode()
                + f"value{i}\r\n".encode()
            )
        parts.append(b"--" + boundary + b"--\r\n")

        form_data = b"".join(parts)

        headers = Headers(
            [
                (b"content-type", b"multipart/form-data; boundary=" + boundary),
                (b"content-length", str(len(form_data)).encode()),
            ]
        )

        parser = MultiPartParser(
            headers, create_form_stream(form_data), max_fields=max_fields
        )

        # This should raise an exception due to too many fields
        with pytest.raises(MultiPartException):
            await parser.parse()
    finally:
        # Restore original max fields
        MultiPartParser.max_fields = original_max_fields


async def test_character_encoding_handling():
    # Test with non-ASCII characters
    boundary = b"boundary123"
    unicode_text = "Hello 世界 こんにちは"  # Unicode text
    form_data = (
        b"--" + boundary + b"\r\n"
        b'Content-Disposition: form-data; name="text"\r\n'
        b"Content-Type: text/plain; charset=utf-8\r\n\r\n"
        + unicode_text.encode("utf-8")
        + b"\r\n"
        b"--" + boundary + b"--\r\n"
    )

    headers = Headers(
        [
            (
                b"content-type",
                b"multipart/form-data; boundary=" + boundary + b"; charset=utf-8",
            ),
            (b"content-length", str(len(form_data)).encode()),
        ]
    )

    parser = MultiPartParser(headers, create_form_stream(form_data))
    form = await parser.parse()

    assert form.get("text") == unicode_text


# Error handling tests
async def test_malformed_headers():
    # Test with malformed content-disposition header
    boundary = b"boundary123"
    form_data = (
        b"--" + boundary + b"\r\n"
        b"Invalid-Header: value\r\n\r\n"  # Missing Content-Disposition
        b"some content\r\n"
        b"--" + boundary + b"--\r\n"
    )

    headers = Headers(
        [
            (b"content-type", b"multipart/form-data; boundary=" + boundary),
            (b"content-length", str(len(form_data)).encode()),
        ]
    )

    parser = MultiPartParser(headers, create_form_stream(form_data))

    # Should raise an exception due to missing Content-Disposition header
    with pytest.raises(Exception):
        await parser.parse()


async def test_invalid_boundary():
    # Test with incorrect boundary in form data
    boundary = b"correct_boundary"
    wrong_boundary = b"wrong_boundary"

    form_data = (
        b"--" + wrong_boundary + b"\r\n"  # Using wrong boundary
        b'Content-Disposition: form-data; name="field1"\r\n\r\n'
        b"value1\r\n"
        b"--" + wrong_boundary + b"--\r\n"
    )

    headers = Headers(
        raw=[
            (
                b"content-type",
                b"multipart/form-data; boundary=" + boundary,
            ),  # Different boundary
            (b"content-length", str(len(form_data)).encode()),
        ]
    )

    parser = MultiPartParser(headers, create_form_stream(form_data))

    # Should fail to parse properly
    with pytest.raises(Exception):
        await parser.parse()


# Integration tests with client
async def test_simple_form_submission(client):
    # Test basic form submission
    data = {
        "name": "John Doe",
        "email": "john@example.com",
        "message": "This is a test message",
    }

    response = await client.post("/form", data=data)
    assert response.status_code == 200

    result = response.json()
    assert result["fields"] == data


async def test_form_with_special_chars_integration(client):
    # Test form with special characters
    data = {
        "name": "User Name",
        "message": "Special characters: !@#$%^&*()_+",
        "unicode": "Hello 世界 こんにちは",
    }

    response = await client.post("/form", data=data)
    assert response.status_code == 200

    result = response.json()
    assert result["fields"] == data


async def test_single_file_upload(client):
    # Test uploading a single file with metadata
    file_content = "This is a test file content."
    files = {"document": ("test.txt", file_content, "text/plain")}
    data = {"description": "Test file upload", "category": "documentation"}

    response = await client.post("/upload", files=files, data=data)
    assert response.status_code == 200

    result = response.json()
    assert "files" in result
    assert "fields" in result

    # Check file data
    assert "document" in result["files"]
    uploaded_file = result["files"]["document"]
    assert uploaded_file["filename"] == "test.txt"
    assert uploaded_file["content"] == file_content
    assert uploaded_file["content_type"] == "text/plain"

    # Check form fields
    assert result["fields"]["description"] == "Test file upload"
    assert result["fields"]["category"] == "documentation"


async def test_multiple_file_uploads(client):
    # Test uploading multiple files of different types
    files = {
        "text_file": ("document.txt", "Text file content", "text/plain"),
        "json_file": ("data.json", '{"key": "value"}', "application/json"),
        "csv_file": ("data.csv", "name,age\nJohn,30\nJane,25", "text/csv"),
    }
    data = {"description": "Multiple files upload test"}

    response = await client.post("/upload", files=files, data=data)
    assert response.status_code == 200

    result = response.json()
    assert len(result["files"]) == 3

    # Check text file
    assert "text_file" in result["files"]
    text_file = result["files"]["text_file"]
    assert text_file["filename"] == "document.txt"
    assert text_file["content"] == "Text file content"
    assert text_file["content_type"] == "text/plain"

    # Check JSON file
    assert "json_file" in result["files"]
    json_file = result["files"]["json_file"]
    assert json_file["filename"] == "data.json"
    assert json_file["content"] == '{"key": "value"}'
    assert json_file["content_type"] == "application/json"

    # Check CSV file
    assert "csv_file" in result["files"]
    csv_file = result["files"]["csv_file"]
    assert csv_file["filename"] == "data.csv"
    assert csv_file["content"] == "name,age\nJohn,30\nJane,25"
    assert csv_file["content_type"] == "text/csv"

    # Check form field
    assert result["fields"]["description"] == "Multiple files upload test"


async def test_unicode_filename_and_content(client):
    # Test handling of Unicode in filenames and content
    filename = "测试文件.txt"
    content = "Unicode content: こんにちは世界 - Hello World!"

    files = {"unicode_file": (filename, content, "text/plain; charset=utf-8")}

    response = await client.post("/upload", files=files)
    assert response.status_code == 200

    result = response.json()
    assert "unicode_file" in result["files"]
    uploaded_file = result["files"]["unicode_file"]
    assert uploaded_file["filename"] == filename
    assert uploaded_file["content"] == content
    assert "text/plain" in uploaded_file["content_type"]


async def test_binary_file_upload(client):
    # Test binary file upload (using simplified binary content for test)
    # In a real scenario, this would be actual binary data
    binary_content = b"Binary content with \x00\x01\x02\x03 bytes"

    files = {"binary_file": ("data.bin", binary_content, "application/octet-stream")}

    response = await client.post("/upload", files=files)
    assert response.status_code == 200

    result = response.json()
    assert "binary_file" in result["files"]
    # Note: The test expects the binary content to be decoded as utf-8 with replacement
    # characters for invalid sequences - this is just for the test's sake
    # In a real app, you might want to handle binary data differently
