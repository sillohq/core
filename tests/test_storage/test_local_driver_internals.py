"""LocalDriver internals the shared DriverContract doesn't reach: the
write() cleanup path on a mid-stream failure, signed_url() without a signer,
the xattr/sidecar content-type fallback chain (forced deterministically via
monkeypatch, since real xattr support is platform-dependent), and directory
pruning on delete.
"""

from __future__ import annotations

import os

import pytest

from sillo.storage.drivers.local import (
    XATTR,
    LocalDriver,
    _prune,
    _recall_type,
    _remember_type,
    _sidecar,
    _xattrs_work,
)


async def _broken_stream():
    yield b"partial data"
    raise RuntimeError("stream blew up")


async def test_write_cleans_up_staging_file_on_error(tmp_path):
    driver = LocalDriver(tmp_path)
    with pytest.raises(RuntimeError, match="stream blew up"):
        await driver.write("a.txt", _broken_stream())

    leftovers = list(tmp_path.rglob("*.partial"))
    assert leftovers == []


def test_signed_url_without_a_signer_raises():
    driver = LocalDriver.__new__(LocalDriver)
    driver._signer = None
    with pytest.raises(NotImplementedError, match="no signer"):
        driver.signed_url("a.txt")


def test_remember_and_recall_type_via_xattr(tmp_path, monkeypatch):
    staging = tmp_path / "staged"
    target = tmp_path / "target"
    staging.write_bytes(b"data")

    # A real filesystem's xattr rides along with the staging->target rename;
    # this fake stands in for that by keying on content-type alone rather
    # than tracking which path currently owns the attribute.
    store = {}

    def fake_setxattr(path, name, value):
        store[name] = value

    def fake_getxattr(path, name):
        return store[name]

    monkeypatch.setattr(os, "setxattr", fake_setxattr, raising=False)
    monkeypatch.setattr(os, "getxattr", fake_getxattr, raising=False)

    _remember_type(staging, target, "text/plain")
    staging.replace(target)
    assert _recall_type(target) == "text/plain"
    # The sidecar fallback must not have been used when xattr succeeded.
    assert not _sidecar(target).exists()


def test_remember_and_recall_type_falls_back_to_sidecar(tmp_path, monkeypatch):
    target = tmp_path / "target"
    target.write_bytes(b"data")

    def raise_oserror(*args, **kwargs):
        raise OSError("xattrs not supported here")

    monkeypatch.setattr(os, "setxattr", raise_oserror, raising=False)
    monkeypatch.setattr(os, "getxattr", raise_oserror, raising=False)

    _remember_type(target, target, "text/plain")
    assert _sidecar(target).is_file()
    assert _recall_type(target) == "text/plain"


def test_recall_type_default_when_nothing_recorded(tmp_path, monkeypatch):
    target = tmp_path / "target"
    target.write_bytes(b"data")

    def raise_oserror(*args, **kwargs):
        raise OSError("no xattrs")

    monkeypatch.setattr(os, "getxattr", raise_oserror, raising=False)

    assert _recall_type(target) == "application/octet-stream"


def test_xattrs_work_reports_true_when_setxattr_succeeds(tmp_path, monkeypatch):
    monkeypatch.setattr(
        os, "setxattr", lambda path, name, value: None, raising=False
    )
    assert _xattrs_work(tmp_path) is True


def test_xattrs_work_reports_false_when_unsupported(tmp_path, monkeypatch):
    def raise_oserror(*args, **kwargs):
        raise OSError("no xattrs")

    monkeypatch.setattr(os, "setxattr", raise_oserror, raising=False)
    assert _xattrs_work(tmp_path) is False


async def test_delete_prunes_empty_parent_directories(tmp_path):
    driver = LocalDriver(tmp_path)
    await driver.write("a/b/c.txt", _one_chunk(b"x"))

    assert await driver.delete("a/b/c.txt") is True

    # Both "a/b" and "a" emptied out and should have been removed, while the
    # bucket root itself must survive.
    assert not (tmp_path / "a").exists()
    assert tmp_path.is_dir()


async def test_delete_does_not_prune_a_directory_with_other_files(tmp_path):
    driver = LocalDriver(tmp_path)
    await driver.write("a/b/c.txt", _one_chunk(b"x"))
    await driver.write("a/keep.txt", _one_chunk(b"y"))

    await driver.delete("a/b/c.txt")

    assert not (tmp_path / "a" / "b").exists()
    assert (tmp_path / "a" / "keep.txt").is_file()


def test_prune_stops_at_an_oserror(tmp_path, monkeypatch):
    sub = tmp_path / "only-empty-dir"
    sub.mkdir()

    def raise_oserror(self):
        raise OSError("permission denied")

    from pathlib import Path

    # Listing the directory (not removing it) is what _prune's OSError
    # branch guards against — e.g. a permissions problem on the directory
    # itself, discovered while checking whether it is empty.
    monkeypatch.setattr(Path, "iterdir", raise_oserror)

    _prune(sub, tmp_path)  # should not raise
    assert sub.exists()


async def _one_chunk(data: bytes):
    yield data
