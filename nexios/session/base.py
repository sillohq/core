import secrets
import typing
import warnings
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, Optional, Union

from nexios.config import MakeConfig, get_config


class BaseSessionInterface:
    modified = False
    accessed = False
    deleted = False

    def __init__(self, session_key: Optional[str] = None) -> None:
        self._session_cache: Dict[str, Any] = {}
        config = get_config()
        self.session_key = session_key
        if not config.secret_key:
            warnings.warn(
                "`secret_key` is not set, `secret_key`  is required to use session",
                RuntimeWarning,
            )
            return
        self.config = config
        self.session_config: MakeConfig = config.session

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

    def __iter__(self) -> Iterable[str]:
        self.accessed = True
        return iter(self._session_cache)

    def __len__(self) -> int:
        self.accessed = True
        return len(self._session_cache)

    def __contains__(self, key: str) -> bool:
        self.accessed = True
        return key in self._session_cache

    def set_session(self, key: str, value: str):
        self.modified = True
        self.accessed = True

        self._session_cache[key] = value

    def get_session(self, key: str):
        self.accessed = True

        return self._session_cache.get(key, None)

    def get_all(self):
        self.accessed = True
        return self._session_cache.items()

    def delete_session(self, key: str):
        self.modified = True
        self.deleted = True
        if key in self._session_cache:
            del self._session_cache[key]

    def keys(self):
        return self._session_cache.keys()

    def values(self):
        return self._session_cache.values()

    def is_empty(self):
        return self._session_cache.items().__len__() == 0

    async def save(self) -> None:
        raise NotImplementedError

    def get_cookie_name(self) -> str:
        """The name of the session cookie. Uses``app.config.SESSION_COOKIE_NAME``."""
        if not self.session_config:
            return "session_id"
        return self.session_config.session_cookie_name or "session_id"

    def get_cookie_domain(self) -> typing.Optional[str]:
        """Returns the domain for which the cookie is valid. Uses `config.SESSION_COOKIE_DOMAIN`."""
        if not self.session_config:
            return None
        return self.session_config.session_cookie_domain

    def get_cookie_path(self) -> Union[str, None]:
        """Returns the path for which the cookie is valid. Uses `config.SESSION_COOKIE_PATH`."""
        if not self.session_config:
            return None
        return self.session_config.session_cookie_path

    def get_cookie_httponly(self) -> typing.Optional[bool]:
        """Returns whether the session cookie should be HTTPOnly. Uses `session_config.session_cookie_httponly`."""
        if not self.session_config:
            return None
        return self.session_config.session_cookie_httponly

    def get_cookie_secure(self) -> typing.Optional[bool]:
        """Returns whether the session cookie should be secure. Uses `session_config.session_cookie_secure`."""
        if not self.session_config:
            return None
        return self.session_config.session_cookie_secure

    def get_cookie_samesite(self) -> typing.Optional[str]:
        """Returns the SameSite attribute for the cookie. Uses `session_config.session_cookie_samesite`."""
        if not self.session_config:
            return None
        return self.session_config.session_cookie_samesite

    def get_cookie_partitioned(self) -> typing.Optional[bool]:
        """Returns whether the cookie should be partitioned. Uses `session_config.session_cookie_partitioned`."""
        if not self.session_config:
            return None
        return self.session_config.session_cookie_partitioned

    def get_expiration_time(self) -> typing.Optional[datetime]:
        """Returns the expiration time for the session if one is set."""
        if not self.session_config:
            # No config - use default 7 day expiration
            if not hasattr(self, "_expiration_time"):
                self._expiration_time = datetime.now(timezone.utc) + timedelta(days=7)
            return self._expiration_time

        if not self.session_config.session_permanent:
            # Non-permanent session - calculate expiration if not set
            if not hasattr(self, "_expiration_time"):
                expiration_seconds = (
                    self.session_config.session_expiration_time or 86400
                )
                self._expiration_time = datetime.now(timezone.utc) + timedelta(
                    seconds=expiration_seconds
                )
            return self._expiration_time

        return None

    @property
    def should_set_cookie(self) -> bool:
        """Determines if the cookie should be set. Depends on `config.SESSION_REFRESH_EACH_REQUEST`."""

        if not self.session_config:
            return self.modified
        return self.modified or (
            self.session_config.session_permanent
            and self.session_config.session_refresh_each_request
        )

    def has_expired(self) -> bool:
        """Returns True if the session has expired."""
        expiration_time = self.get_expiration_time()
        if expiration_time and datetime.now(timezone.utc) > expiration_time:
            return True
        return False

    def get_session_key(self) -> str:
        """Returns the session key."""
        if self.session_key:
            return self.session_key
        return secrets.token_hex(32)

    def clear(self):
        self.accessed = True
        self.modified = True
        self.deleted = True
        self._session_cache.clear()

    def get(self, key: str, default: Any = None):
        return self._session_cache.get(key, default)

    def set_expiration_time(self, expiration: datetime) -> None:
        """Set the expiration time for the session."""
        self._expiration_time = expiration

    def __str__(self) -> str:
        return f"<Sesion {self._session_cache} >"

    def __del__(self) -> None:
        self.clear()
        self.session_key = None
        self.config = None
