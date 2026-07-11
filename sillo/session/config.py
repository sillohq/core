from typing import Literal
from typing import Any, Optional

from sillo.config.base import MakeConfig


class SessionConfig(MakeConfig):
    """
    Typed configuration for Session middleware.
    All session settings should be passed here - only secret_key comes from app-level config.
    """

    def __init__(
        self,
        session_cookie_name: str = "session_id",
        session_expiration_time: int = 86400,
        session_permanent: bool = True,
        session_refresh_each_request: bool = True,
        session_cookie_secure: bool = True,
        session_cookie_httponly: bool = True,
        session_cookie_samesite: str = "lax",
        session_cookie_path: str = "/",
        session_cookie_domain: Optional[str] = None,
        session_file_storage_path: Optional[str] = None,
        manager: Optional[Any] = None,
        **kwargs: Any,
    ):
        config = {
            "session_cookie_name": session_cookie_name,
            "session_expiration_time": session_expiration_time,
            "session_permanent": session_permanent,
            "session_refresh_each_request": session_refresh_each_request,
            "session_cookie_secure": session_cookie_secure,
            "session_cookie_httponly": session_cookie_httponly,
            "session_cookie_samesite": session_cookie_samesite,
            "session_cookie_path": session_cookie_path,
            "session_cookie_domain": session_cookie_domain,
            "session_file_storage_path": session_file_storage_path,
            "manager": manager,
        }
        super().__init__(config=config, **kwargs)

    @property
    def session_cookie_name(self) -> str:
        return self._config.get("session_cookie_name", "session_id")

    @property
    def session_expiration_time(self) -> int:
        return self._config.get("session_expiration_time", 86400)

    @property
    def session_permanent(self) -> bool:
        return self._config.get("session_permanent", True)

    @property
    def session_refresh_each_request(self) -> bool:
        return self._config.get("session_refresh_each_request", True)

    @property
    def session_cookie_secure(self) -> bool:
        return self._config.get("session_cookie_secure", True)

    @property
    def session_cookie_httponly(self) -> bool:
        return self._config.get("session_cookie_httponly", True)

    @property
    def session_cookie_samesite(self) -> Literal["lax", "strict", "none"]:
        return self._config.get("session_cookie_samesite", "lax")

    @property
    def session_cookie_path(self) -> str:
        return self._config.get("session_cookie_path", "/")

    @property
    def session_cookie_domain(self) -> Optional[str]:
        return self._config.get("session_cookie_domain")

    @property
    def session_file_storage_path(self) -> Optional[str]:
        return self._config.get("session_file_storage_path")

    @property
    def manager(self) -> Optional[Any]:
        return self._config.get("manager")
