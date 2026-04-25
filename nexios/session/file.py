import json
import os
from typing import Any, Dict, Optional

from .base import BaseSessionInterface


class FileSessionManager(BaseSessionInterface):
    def __init__(self, config=None) -> None:
        super().__init__(config)
        self.storage_path = getattr(config, "session_file_storage_path", "__sessions")

        if self.storage_path and not os.path.exists(self.storage_path):
            os.makedirs(self.storage_path, exist_ok=True)

    def _get_file_path(self, session_key: str) -> str:
        return os.path.join(self.storage_path, f"{session_key}.json")

    def _load_session_data(self, session_key: str) -> Optional[Dict[str, Any]]:
        path = self._get_file_path(session_key)

        if os.path.exists(path):
            with open(path, "r") as file:
                try:
                    return json.load(file)
                except json.JSONDecodeError:
                    return None

        return None

    def _save_session_data(self, session_key: str, data: Dict[str, Any]) -> None:
        path = self._get_file_path(session_key)

        with open(path, "w") as file:
            json.dump(data, file)

    def _delete_session_file(self, session_key: str) -> None:
        path = self._get_file_path(session_key)

        if os.path.exists(path):
            os.remove(path)

    async def load(self, session):
        key = session.get_session_key()

        data = self._load_session_data(key)

        if data:
            session._session_cache.update(data)
        else:
            session._session_cache.clear()

    async def save(self, session):
        key = session.get_session_key()

        if session.deleted:
            self._delete_session_file(key)
            session.session_key = None
            return ""

        self._save_session_data(key, session._session_cache)

        session.session_key = key

        return key
