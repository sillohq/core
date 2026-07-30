"""Configuration tests fixtures."""

import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_env_file():
    """Create a temporary .env file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
        f.write("DATABASE_URL=postgresql://localhost/testdb\n")
        f.write("JWT_SECRET=test-secret-key\n")
        f.write("DEBUG=true\n")
        f.write("PORT=9000\n")
        f.write("LOG_LEVEL=debug\n")
        temp_path = f.name

    yield temp_path

    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def empty_env_file():
    """Create an empty .env file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
        temp_path = f.name

    yield temp_path

    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def isolated_env(monkeypatch, tmp_path):
    """Isolate environment for clean tests."""
    # Store original env vars
    original_env = dict(os.environ)

    # Clear custom env vars (keep system vars)
    system_prefixes = ('PATH', 'HOME', 'SHELL', 'USER', 'PWD', 'TMPDIR', 'LANG', 'VIRTUAL_ENV')
    for key in list(os.environ.keys()):
        if not any(key.startswith(prefix) for prefix in system_prefixes):
            monkeypatch.delenv(key, raising=False)

    yield tmp_path

    # Restore original env after test
    for key in list(os.environ.keys()):
        if not any(key.startswith(prefix) for prefix in system_prefixes):
            monkeypatch.delenv(key, raising=False)
    for key, value in original_env.items():
        if not any(key.startswith(prefix) for prefix in system_prefixes):
            monkeypatch.setenv(key, value)
