"""
Tests for file-based session manager
"""

import asyncio
import json
import os
import tempfile
import warnings

import pytest

from nexios import NexiosApp
from nexios.config import MakeConfig, set_config
from nexios.http import Request, Response
from nexios.session import SessionConfig
from nexios.session.file import FileSessionManager
from nexios.session.middleware import SessionMiddleware


class TestFileSessionManager:
    """Test file-based session manager functionality"""

    def setup_method(self):
        """Set up test configuration with temporary directory"""
        self.temp_dir = tempfile.mkdtemp()
        config = MakeConfig(
            secret_key="test-secret-key-for-file-sessions",
            session=SessionConfig(
                session_cookie_name="test_session",
                session_expiration_time=3600,
                session_permanent=False,
                session_refresh_each_request=False,
                session_file_storage_path=self.temp_dir,
                session_file_name="test_sessions",
            ),
        )
        set_config(config)

    def teardown_method(self):
        """Clean up temporary directory"""
        import shutil

        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_file_session_initialization(self):
        """Test file session manager initialization"""
        session = FileSessionManager("test-session-key")

        assert session.session_key == "test-session-key"
        assert session._session_cache == {}
        assert os.path.exists(session._get_storage_path()) is False

    async def test_file_session_save_and_load(self):
        """Test saving and loading session data"""
        session = FileSessionManager("test-key-1")

        # Set some data
        session["user_id"] = 123
        session["preferences"] = {"theme": "dark"}

        # Save the session
        await session.save()

        # Verify file was created
        assert os.path.exists(session._get_storage_path())

        # Create new session and load data
        new_session = FileSessionManager("test-key-1")
        await new_session.load()

        assert new_session["user_id"] == 123
        assert new_session["preferences"] == {"theme": "dark"}

    async def test_file_session_with_existing_file(self):
        """Test loading from existing session file"""
        session1 = FileSessionManager("test-key-2")

        # Create initial data
        session1["initial"] = "data"
        await session1.save()

        # Modify in new session
        session2 = FileSessionManager("test-key-2")
        session2["initial"] = "modified_data"
        session2["new_key"] = "new_value"
        await session2.save()

        # Load and verify
        session3 = FileSessionManager("test-key-2")
        await session3.load()

        assert session3["initial"] == "modified_data"
        assert session3["new_key"] == "new_value"

    def test_file_session_file_path_generation(self):
        """Test session file path generation"""
        session = FileSessionManager("custom-key")

        expected_path = os.path.join(self.temp_dir, "custom-key.json")
        assert session._get_storage_path() == expected_path

    async def test_file_session_corrupted_data(self):
        """Test handling of corrupted session file"""
        session = FileSessionManager("corrupted-key")

        # Create corrupted JSON file
        with open(session._get_storage_path(), "w") as f:
            f.write("invalid json content")

        # Should handle gracefully
        await session.load()
        assert session._session_cache == {}

    async def test_file_session_missing_file(self):
        """Test loading when session file doesn't exist"""
        session = FileSessionManager("nonexistent-key")

        # Should handle gracefully
        await session.load()
        assert session._session_cache == {}

    async def test_file_session_clear(self):
        """Test clearing session data and file"""
        session = FileSessionManager("clear-test")

        session["data"] = "test"
        await session.save()

        # Verify file exists
        assert os.path.exists(session._get_storage_path())

        # Clear the session
        session.clear()

        # File should be removed
        assert os.path.exists(session._get_storage_path()) is False
        assert session._session_cache == {}

    def test_file_session_operations(self):
        """Test various session operations"""
        session = FileSessionManager("operations-test")

        # Test set_session and get_session
        session.set_session("key1", "value1")
        assert session.get_session("key1") == "value1"

        # Test get_all
        session.set_session("key2", "value2")
        items = dict(session.get_all())
        assert items == {"key1": "value1", "key2": "value2"}

        # Test keys and values
        assert set(session.keys()) == {"key1", "key2"}
        assert set(session.values()) == {"value1", "value2"}

        # Test is_empty
        assert session.is_empty() is False

        # Clear and test empty
        session.clear()
        assert session.is_empty() is True

    async def test_file_session_concurrent_access(self):
        """Test concurrent access to session files"""
        session1 = FileSessionManager("concurrent-test")

        # Session 1 sets data
        session1["counter"] = 1
        await session1.save()

        # Session 2 reads and modifies
        session2 = FileSessionManager("concurrent-test")
        await session2.load()
        session2["counter"] = 2
        await session2.save()

        # Session 3 reads final value
        session3 = FileSessionManager("concurrent-test")
        await session3.load()
        assert session3["counter"] == 2

    async def test_file_session_large_data(self):
        """Test session with large data"""
        session = FileSessionManager("large-data-test")

        # Create large data
        large_data = {"data": "x" * 10000, "list": list(range(1000))}
        session["large"] = large_data
        await session.save()

        # Load and verify
        new_session = FileSessionManager("large-data-test")
        await new_session.load()
        assert new_session["large"] == large_data

    async def test_file_session_key_generation(self):
        """Test session key generation"""
        session = FileSessionManager()

        # Initially no key
        assert session.session_key is None

        # After setting data and saving, should have a key
        session["test"] = "value"
        await session.save()

        assert session.session_key is not None
        assert isinstance(session.session_key, str)


class TestSessionMiddleware:
    """Test session middleware with new configuration style"""

    def setup_method(self):
        """Set up test configuration with temporary directory"""
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Clean up temporary directory"""
        import shutil

        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_session_middleware_with_config_object(self, test_client_factory):
        """Test session middleware with SessionConfig object"""
        session_config = SessionConfig(
            session_cookie_name="test_session",
            manager=FileSessionManager,
        )

        app = NexiosApp()
        app.add_middleware(SessionMiddleware(config=session_config))

        @app.get("/set-session")
        async def set_session(request: Request, response: Response):
            request.session["user_id"] = 123
            return response.json({"status": "session_set"})

        @app.get("/get-session")
        async def get_session(request: Request, response: Response):
            user_id = request.session.get("user_id")
            return response.json({"user_id": user_id})

        with test_client_factory(app) as client:
            # Set session
            res1 = client.get("/set-session")
            assert res1.status_code == 200
            assert "test_session" in res1.cookies

            # Get session
            res2 = client.get("/get-session", cookies=res1.cookies)
            assert res2.status_code == 200
            assert res2.json() == {"user_id": 123}

    def test_session_middleware_deprecated_config_style(self, test_client_factory):
        """Test session middleware with deprecated config style (should show warning)."""
        config = MakeConfig(
            secret_key="test-secret",
            session=SessionConfig(session_cookie_name="deprecated_session"),
        )
        set_config(config)

        app = NexiosApp(config)

        @app.get("/test")
        async def test_route(request: Request, response: Response):
            return response.json({"status": "ok"})

        # This should trigger a deprecation warning
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            app.add_middleware(SessionMiddleware())

            # Check that deprecation warning was issued
            assert len(w) > 0
            assert any("deprecated" in str(warning.message).lower() for warning in w)

        with test_client_factory(app) as client:
            res = client.get("/test")
            assert res.status_code == 200

    def test_session_middleware_no_config(self, test_client_factory):
        """Test session middleware without any config (should use fallback)."""
        app = NexiosApp()
        app.add_middleware(SessionMiddleware())

        @app.get("/test")
        async def test_route(request: Request, response: Response):
            return response.json({"status": "ok"})

        with test_client_factory(app) as client:
            res = client.get("/test")
            # Should work but no session functionality
            assert res.status_code == 200
