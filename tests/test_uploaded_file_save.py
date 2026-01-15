import io
import os
import tempfile

import pytest

from nexios.objects.http import UploadedFile


@pytest.mark.asyncio
async def test_uploaded_file_save_memory():
    content = b"Hello, World!"
    file_obj = io.BytesIO(content)
    uploaded_file = UploadedFile(file=file_obj, filename="test.txt")

    # Mocking _in_memory to true for BytesIO
    # Actually UploadedFile._in_memory checks for SpooledTemporaryFile._rolled
    # For BytesIO, it will likely return True (not rolled to disk)

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        dest = tmp.name

    try:
        await uploaded_file.save(dest)
        with open(dest, "rb") as f:
            saved_content = f.read()
        assert saved_content == content
    finally:
        if os.path.exists(dest):
            os.remove(dest)


@pytest.mark.asyncio
async def test_uploaded_file_save_spooled():
    content = b"Large content " * 1000
    from tempfile import SpooledTemporaryFile

    file_obj = SpooledTemporaryFile(max_size=1024)
    file_obj.write(content)
    file_obj.seek(0)

    uploaded_file = UploadedFile(file=file_obj, filename="test.txt")

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        dest = tmp.name

    try:
        await uploaded_file.save(dest)
        with open(dest, "rb") as f:
            saved_content = f.read()
        assert saved_content == content
    finally:
        if os.path.exists(dest):
            os.remove(dest)
