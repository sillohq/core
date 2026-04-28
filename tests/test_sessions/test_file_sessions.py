"""
Tests for file-based session manager
"""

from nexios.http import Response
from nexios.http import Request
import json
import os
import tempfile

import pytest

from nexios import NexiosApp
from nexios.session import SessionConfig
from nexios.session.base import BaseSessionInterface
from nexios.session.file import FileSessionManager
from nexios.session.middleware import SessionMiddleware
from nexios.session.session_objects import Session
from nexios.testclient import TestClient


class TestFileSessionManager:
    """Test file-based session manager functionality"""

    def setup_method(self):
        """Set up test configuration with temporary directory"""
        self.temp_dir = tempfile.mkdtemp()
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
        """Test loading session with missing file"""
        manager = FileSessionManager(self.config)
        session = manager.create_session("non-existent-key")

        await session.load()
        assert session._session_cache == {}

    async def test_file_session_overwrite(self):
        """Test overwriting session data"""
        manager = FileSessionManager(self.config)
        session = manager.create_session("overwrite-key")

        session["version"] = 1
        await session.save()

        session["version"] = 2
        session["new_field"] = "added"
        await session.save()

        new_session = manager.create_session("overwrite-key")
        await new_session.load()

        assert new_session["version"] == 2
        assert new_session["new_field"] == "added"

    async def test_file_session_delete(self):
        """Test deleting session data"""
        manager = FileSessionManager(self.config)
        session = manager.create_session("delete-key")

        session["to_delete"] = "value"
        await session.save()

        file_path = manager._get_file_path("delete-key")
        assert os.path.exists(file_path)

        session.clear()
        await session.save()

        new_session = manager.create_session("delete-key")
        await new_session.load()
        assert new_session._session_cache == {}

    def test_file_session_storage_path_creation(self):
        """Test that storage path is created if not exists"""
        new_temp_dir = tempfile.mkdtemp()
        new_path = os.path.join(new_temp_dir, "nested", "storage")

        config = SessionConfig(session_file_storage_path=new_path)
        manager = FileSessionManager(config)

        assert os.path.exists(new_path)
        import shutil

        shutil.rmtree(new_temp_dir)

    async def test_file_session_complex_data(self):
        """Test file session with complex data types"""
        manager = FileSessionManager(self.config)
        session = manager.create_session("complex-key")

        complex_data = {
            "user": {"id": 1, "name": "Test"},
            "items": [1, 2, 3],
            "nested": {"a": {"b": "deep"}},
        }

        for key, value in complex_data.items():
            session[key] = value

        await session.save()

        new_session = manager.create_session("complex-key")
        await new_session.load()

        for key, value in complex_data.items():
            assert new_session[key] == value

    def test_file_session_multiple_sessions(self):
        """Test handling multiple sessions simultaneously"""
        manager = FileSessionManager(self.config)

        for i in range(5):
            session = manager.create_session(f"key-{i}")
            session[f"data_{i}"] = f"value_{i}"

    def test_file_session_json_format(self):
        """Test that session data is stored as valid JSON"""
        manager = FileSessionManager(self.config)
        session = manager.create_session("json-test")

        session["test"] = "value"

        file_path = manager._get_file_path("json-test")
        assert file_path.endswith(".json")


class TestFileSessionIntegration:
    """Integration tests for file-based sessions"""

    def setup_method(self):
        """Set up test configuration"""
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Clean up"""
        import shutil

        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_file_session_integration(self):
        """Test file session with middleware integration"""
        app = NexiosApp()

        @app.get("/file-session-test")
        async def file_session_test(request: Request, response: Response):
            counter = request.session.get("counter", 0)
            counter += 1
            request.session["counter"] = counter
            return response.json({"counter": request.session["counter"]})

        file_manager = FileSessionManager(
            SessionConfig(session_file_storage_path=self.temp_dir)
        )

        app.add_middleware(
            SessionMiddleware(
                config=SessionConfig(session_file_storage_path=self.temp_dir),
                manager=file_manager,
                secret_key="test-secret-key-for-file-sessions",
            )
        )

        client = TestClient(app)

        response1 = client.get("/file-session-test")
        assert response1.status_code == 200
        assert response1.json()["counter"] == 1

        response2 = client.get("/file-session-test",headers = {"Cookie": response1.headers["Set-Cookie"]})
        assert response2.status_code == 200
        assert response2.json()["counter"] == 2
