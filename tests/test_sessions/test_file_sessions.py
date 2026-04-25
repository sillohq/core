"""
Tests for file-based session manager
"""

import json
import os
import tempfile

import pytest

from nexios import NexiosApp
from nexios.config import MakeConfig, set_config
from nexios.http import Request, Response
from nexios.session import SessionConfig
from nexios.session.base import BaseSessionInterface
from nexios.session.file import FileSessionManager
from nexios.session.middleware import SessionMiddleware
from nexios.session.session_objects import Session


class TestFileSessionManager:
    """Test file-based session manager functionality"""

    def setup_method(self):
        """Set up test configuration with temporary directory"""
        self.temp_dir = tempfile.mkdtemp()
        config = MakeConfig(secret_key="test-secret-key-for-file-sessions")
        set_config(config)
        self.config = SessionConfig(session_file_storage_path=self.temp_dir)

    def teardown_method(self):
        """Clean up temporary directory"""
        import shutil

        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_file_session_manager_initialization(self):
        """Test file session manager initialization"""
        manager = FileSessionManager(self.config)
        assert os.path.exists(manager.storage_path)

    async def test_file_session_save_and_load(self):
        """Test saving and loading session data"""
        manager = FileSessionManager(self.config)
        session = manager.create_session("test-key-1")

        session["user_id"] = 123
        session["preferences"] = {"theme": "dark"}

        await session.save()

        file_path = manager._get_file_path("test-key-1")
        assert os.path.exists(file_path)

        new_session = manager.create_session("test-key-1")
        await new_session.load()

        assert new_session["user_id"] == 123
        assert new_session["preferences"] == {"theme": "dark"}

    async def test_file_session_with_existing_file(self):
        """Test loading from existing session file"""
        manager = FileSessionManager(self.config)
        session1 = manager.create_session("test-key-2")

        session1["initial"] = "data"
        await session1.save()

        session2 = manager.create_session("test-key-2")
        session2["initial"] = "modified_data"
        session2["new_key"] = "new_value"
        await session2.save()

        session3 = manager.create_session("test-key-2")
        await session3.load()

        assert session3["initial"] == "modified_data"
        assert session3["new_key"] == "new_value"

    def test_file_session_file_path_generation(self):
        """Test session file path generation"""
        manager = FileSessionManager(self.config)

        expected_path = os.path.join(self.temp_dir, "test-key.json")
        assert manager._get_file_path("test-key") == expected_path

    async def test_file_session_corrupted_data(self):
        """Test handling of corrupted session file"""
        manager = FileSessionManager(self.config)
        session = manager.create_session("corrupted-key")

        file_path = manager._get_file_path("corrupted-key")
        with open(file_path, "w") as f:
            f.write("invalid json content")

        await session.load()
        assert session._session_cache == {}

    async def test_file_session_missing_file(self):
        """Test loading when session file doesn't exist"""
        manager = FileSessionManager(self.config)
        session = manager.create_session("nonexistent-key")

        await session.load()
        assert session._session_cache == {}

    async def test_file_session_clear(self):
        """Test clearing session data and file"""
        manager = FileSessionManager(self.config)
        session = manager.create_session("clear-test")

        session["data"] = "test"
        await session.save()

        file_path = manager._get_file_path("clear-test")
        assert os.path.exists(file_path)

        session.clear()
        await session.save()

        assert not os.path.exists(file_path)
        assert session._session_cache == {}

    def test_file_session_operations(self):
        """Test various session operations via Session object"""
        manager = FileSessionManager(self.config)
        session = manager.create_session("operations-test")

        session.set("key1", "value1")
        assert session.get("key1") == "value1"

        session.set("key2", "value2")
        assert dict(session.items()) == {"key1": "value1", "key2": "value2"}

        assert set(session.keys()) == {"key1", "key2"}
        assert set(session.values()) == {"value1", "value2"}

        assert not session.is_empty()

        session.clear()
        assert session.is_empty()

    async def test_file_session_concurrent_access(self):
        """Test concurrent access to session files"""
        manager = FileSessionManager(self.config)

        session1 = manager.create_session("concurrent-test")
        session1["counter"] = 1
        await session1.save()

        session2 = manager.create_session("concurrent-test")
        await session2.load()
        session2["counter"] = 2
        await session2.save()

        session3 = manager.create_session("concurrent-test")
        await session3.load()
        assert session3["counter"] == 2

    async def test_file_session_large_data(self):
        """Test session with large data"""
        manager = FileSessionManager(self.config)
        session = manager.create_session("large-data-test")

        large_data = {"data": "x" * 10000, "list": list(range(1000))}
        session["large"] = large_data
        await session.save()

        new_session = manager.create_session("large-data-test")
        await new_session.load()
        assert new_session["large"] == large_data

    async def test_file_session_key_generation(self):
        """Test session key generation"""
        manager = FileSessionManager(self.config)
        session = manager.create_session()

        assert session.session_key is None

        session["test"] = "value"
        await session.save()

        assert session.session_key is not None
        assert isinstance(session.session_key, str)


class TestSessionMiddlewareFileIntegration:
    """Test session middleware with file backend integration"""

    def setup_method(self):
        """Set up test configuration with temporary directory"""
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Clean up temporary directory"""
        import shutil

        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    @pytest.mark.skip(
        reason="File session backend needs architectural fix for cookie/session key separation"
    )
    def test_session_middleware_with_file_manager_instance(self):
        """Test file session manager via middleware with instance"""
        app = NexiosApp(config=MakeConfig(secret_key="test-secret-key"))

        file_config = SessionConfig(session_file_storage_path=self.temp_dir)
        file_manager = FileSessionManager(file_config)

        app.add_middleware(
            SessionMiddleware(
                config=SessionConfig(session_cookie_name="file_session"),
                manager=file_manager,
            )
        )

        @app.get("/set-session")
        async def set_session(request: Request, response: Response):
            request.session["user_id"] = 123
            return response.json({"status": "session_set"})

        @app.get("/get-session")
        async def get_session(request: Request, response: Response):
            user_id = request.session.get("user_id")
            return response.json({"user_id": user_id})

        from nexios.testclient import TestClient

        client = TestClient(app)

        res1 = client.get("/set-session")
        assert res1.status_code == 200

        res2 = client.get("/get-session", cookies=res1.cookies)
        assert res2.status_code == 200
        assert res2.json() == {"user_id": 123}
