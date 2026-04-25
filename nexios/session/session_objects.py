from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, Optional


class Session:
    def __init__(self, interface, session_key: Optional[str] = None) -> None:
        self.interface = interface
        self.session_key = session_key
        self._session_cache: Dict[str, Any] = {}

        self.modified = False
        self.accessed = False
        self.deleted = False

        self._expiration_time: Optional[datetime] = None

    def __getitem__(self, key: str) -> Any:
        self.accessed = True
        return self._session_cache[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.modified = True
        self.accessed = True
        self._session_cache[key] = value

    def __delitem__(self, key: str) -> None:
        self.modified = True
        self.deleted = True
        del self._session_cache[key]

    def __contains__(self, key: str) -> bool:
        self.accessed = True
        return key in self._session_cache

    def __iter__(self) -> Iterable[str]:
        self.accessed = True
        return iter(self._session_cache)

    def __len__(self) -> int:
        self.accessed = True
        return len(self._session_cache)

    def get(self, key: str, default: Any = None) -> Any:
        self.accessed = True
        return self._session_cache.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.modified = True
        self.accessed = True
        self._session_cache[key] = value

    def delete(self, key: str) -> None:
        self.modified = True
        self.deleted = True
        if key in self._session_cache:
            del self._session_cache[key]

    def clear(self) -> None:
        self.accessed = True
        self.modified = True
        self.deleted = True
        self._session_cache.clear()

    def keys(self):
        self.accessed = True
        return self._session_cache.keys()

    def values(self):
        self.accessed = True
        return self._session_cache.values()

    def items(self):
        self.accessed = True
        return self._session_cache.items()

    def is_empty(self) -> bool:
        return len(self._session_cache) == 0

    def get_session_key(self) -> str:
        if self.session_key:
            return self.session_key
        return self.interface.generate_session_key()

    def set_expiration_time(self, expiration: datetime) -> None:
        self._expiration_time = expiration

    def get_expiration_time(self) -> Optional[datetime]:
        if self._expiration_time:
            return self._expiration_time

        config = getattr(self.interface, "config", None)

        if not config:
            self._expiration_time = datetime.now(timezone.utc) + timedelta(days=7)
            return self._expiration_time

        session_config = getattr(config, "session", None)

        if not session_config:
            self._expiration_time = datetime.now(timezone.utc) + timedelta(days=7)
            return self._expiration_time

        if not session_config.session_permanent:
            seconds = session_config.session_expiration_time or 86400
            self._expiration_time = datetime.now(timezone.utc) + timedelta(
                seconds=seconds
            )
            return self._expiration_time

        return None

    def has_expired(self) -> bool:
        expiration_time = self.get_expiration_time()
        if expiration_time and datetime.now(timezone.utc) > expiration_time:
            return True
        return False

    @property
    def should_set_cookie(self) -> bool:
        config = getattr(self.interface, "config", None)

        if not config or not getattr(config, "session", None):
            return self.modified

        session_config = config.session

        return self.modified or (
            session_config.session_permanent
            and session_config.session_refresh_each_request
        )

    async def load(self) -> None:
        return await self.interface.load(self)

    async def save(self) -> Optional[str]:
        return await self.interface.save(self)

    def __str__(self) -> str:
        return f"<Session {self._session_cache}>"
