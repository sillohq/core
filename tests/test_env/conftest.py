"""Fixtures for the .env loader tests."""

import os

import pytest

from sillo.env import _loader


@pytest.fixture(autouse=True)
def clean_env():
    """Restore os.environ, and forget what autoload has already read.

    ``load_env`` writes to ``os.environ`` directly rather than through
    monkeypatch, and ``autoload`` remembers files across calls by design, so
    both need undoing between tests.
    """
    original = dict(os.environ)
    _loader._reset_autoload()

    yield

    os.environ.clear()
    os.environ.update(original)
    _loader._reset_autoload()


@pytest.fixture
def project(tmp_path, monkeypatch):
    """A directory that looks like a project root, and is the cwd."""
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n")
    monkeypatch.chdir(tmp_path)
    return tmp_path
