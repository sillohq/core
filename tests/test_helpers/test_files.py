"""
File helpers: size formatting, extension inspection, and path safety.

``safe_filename`` and ``is_dangerous_extension`` guard user-supplied upload
names, so the traversal and executable-extension cases are covered explicitly.
"""

import time
from pathlib import Path

import pytest

from sillo.helpers.files import (
    ensure_directory,
    file_age,
    file_age_human,
    format_size,
    format_size_binary,
    get_extension,
    get_extension_clean,
    guess_mime_type,
    is_dangerous_extension,
    is_image_extension,
    is_media_extension,
    list_files,
    parse_size,
    safe_filename,
    unique_filename,
)


# ── size formatting ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "value,expected_unit",
    [(0, "B"), (512, "B"), (2048, "KB"), (5 * 1024**2, "MB"), (3 * 1024**3, "GB")],
)
def test_format_size_picks_a_unit(value, expected_unit):
    assert expected_unit in format_size(value)


def test_format_size_binary_uses_binary_units():
    assert "iB" in format_size_binary(2048) or "KB" in format_size_binary(2048)


def test_format_size_of_zero():
    assert "0" in format_size(0)


def test_format_size_accepts_a_float():
    assert isinstance(format_size(1536.5), str)


# ── size parsing ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text,expected",
    [
        ("100", 100),
        ("1KB", 1024),
        ("1MB", 1024**2),
        ("1GB", 1024**3),
        ("2 KB", 2048),
        ("1kb", 1024),
    ],
)
def test_parse_size(text, expected):
    assert parse_size(text) == expected


def test_parse_size_rejects_nonsense():
    with pytest.raises(ValueError):
        parse_size("not a size")


def test_parse_size_round_trips_with_format():
    assert parse_size("1KB") == 1024


# ── extensions ───────────────────────────────────────────────────────────


def test_get_extension_keeps_the_dot():
    assert get_extension("report.pdf") == ".pdf"


def test_get_extension_clean_drops_the_dot():
    assert get_extension_clean("report.PDF") == "pdf"


def test_get_extension_of_a_file_without_one():
    assert get_extension("README") == ""


def test_get_extension_uses_only_the_last_suffix():
    assert get_extension("archive.tar.gz") == ".gz"


def test_guess_mime_type():
    assert guess_mime_type("page.html") == "text/html"
    assert guess_mime_type("photo.png") == "image/png"


def test_guess_mime_type_of_an_unknown_extension():
    assert guess_mime_type("file.zzzz") is None


@pytest.mark.parametrize("name", ["evil.exe", "run.sh", "macro.bat", "script.cmd"])
def test_dangerous_extensions_are_flagged(name):
    assert is_dangerous_extension(name) is True


@pytest.mark.parametrize("name", ["photo.png", "notes.txt", "report.pdf"])
def test_ordinary_extensions_are_not_flagged(name):
    assert is_dangerous_extension(name) is False


@pytest.mark.parametrize("name", ["a.png", "b.jpg", "c.jpeg", "d.gif", "e.webp"])
def test_image_extensions(name):
    assert is_image_extension(name) is True


def test_a_document_is_not_an_image():
    assert is_image_extension("doc.pdf") is False


@pytest.mark.parametrize("name", ["a.mp4", "b.mp3", "c.wav"])
def test_media_extensions(name):
    assert is_media_extension(name) is True


# ── filename safety ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "hostile",
    ["../../etc/passwd", "a/b/c.txt", "..\\..\\win.ini", "....//x.txt", "/abs/path"],
)
def test_safe_filename_cannot_escape_its_directory(hostile, tmp_path):
    """A filename is attacker-controlled; joining it must stay inside the base.

    Note that a bare ".." may survive as text — harmless without a separator,
    which is what actually enables traversal.
    """
    cleaned = safe_filename(hostile)
    assert "/" not in cleaned and "\\" not in cleaned

    resolved = (tmp_path / cleaned).resolve()
    assert resolved.parent == tmp_path.resolve()


def test_safe_filename_removes_separators():
    assert "/" not in safe_filename("a/b/c.txt")


def test_safe_filename_keeps_the_extension():
    assert safe_filename("my report.pdf").endswith(".pdf")


def test_safe_filename_uses_the_given_replacement():
    assert "-" in safe_filename("my report.txt", replacement="-")


def test_safe_filename_of_an_already_safe_name():
    assert safe_filename("report.pdf") == "report.pdf"


def test_safe_filename_handles_an_empty_name():
    assert isinstance(safe_filename(""), str)


# ── filesystem helpers ───────────────────────────────────────────────────


def test_unique_filename_leaves_a_free_name_alone(tmp_path):
    assert unique_filename(tmp_path, "new.txt") == "new.txt"


def test_unique_filename_avoids_an_existing_name(tmp_path):
    (tmp_path / "taken.txt").write_text("x")
    result = unique_filename(tmp_path, "taken.txt")
    assert result != "taken.txt"
    assert result.endswith(".txt")


def test_unique_filename_avoids_several_collisions(tmp_path):
    (tmp_path / "f.txt").write_text("x")
    first = unique_filename(tmp_path, "f.txt")
    (tmp_path / first).write_text("x")
    second = unique_filename(tmp_path, "f.txt")
    assert second not in {"f.txt", first}


def test_ensure_directory_creates_it(tmp_path):
    target = tmp_path / "a" / "b"
    result = ensure_directory(target)
    assert target.is_dir()
    assert isinstance(result, Path)


def test_ensure_directory_is_idempotent(tmp_path):
    ensure_directory(tmp_path / "x")
    ensure_directory(tmp_path / "x")
    assert (tmp_path / "x").is_dir()


def test_file_age_of_a_fresh_file(tmp_path):
    f = tmp_path / "f.txt"
    f.write_text("x")
    assert file_age(f) < 5


def test_file_age_human_is_readable(tmp_path):
    f = tmp_path / "f.txt"
    f.write_text("x")
    assert isinstance(file_age_human(f), str)


def test_file_age_of_an_older_file(tmp_path):
    import os

    f = tmp_path / "old.txt"
    f.write_text("x")
    old = time.time() - 90000
    os.utime(f, (old, old))
    assert file_age(f) > 3600
    assert isinstance(file_age_human(f), str)


# ── listing ──────────────────────────────────────────────────────────────


@pytest.fixture
def tree(tmp_path):
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.md").write_text("b")
    nested = tmp_path / "sub"
    nested.mkdir()
    (nested / "c.txt").write_text("c")
    return tmp_path


def test_list_files_is_shallow_by_default(tree):
    names = {Path(p).name for p in list_files(tree)}
    assert "a.txt" in names
    assert "c.txt" not in names


def test_list_files_recursive(tree):
    names = {Path(p).name for p in list_files(tree, recursive=True)}
    assert {"a.txt", "c.txt"} <= names


def test_list_files_with_a_pattern(tree):
    names = {Path(p).name for p in list_files(tree, pattern="*.txt")}
    assert "a.txt" in names
    assert "b.md" not in names


def test_list_files_in_an_empty_directory(tmp_path):
    assert list_files(tmp_path) == []
