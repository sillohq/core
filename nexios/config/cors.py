from typing import Any, Callable, Dict, List, Optional

from nexios.config.base import MakeConfig


class CorsConfig(MakeConfig):
    """
    Typed configuration for CORS middleware.
    """

    def __init__(
        self,
        allow_origins: Optional[List[str]] = None,
        blacklist_origins: Optional[List[str]] = None,
        allow_methods: Optional[List[str]] = None,
        blacklist_headers: Optional[List[str]] = None,
        allow_headers: Optional[List[str]] = None,
        allow_credentials: bool = True,
        allow_origin_regex: Optional[str] = None,
        expose_headers: Optional[List[str]] = None,
        max_age: int = 600,
        strict_origin_checking: bool = False,
        dynamic_origin_validator: Optional[Callable[[Optional[str]], bool]] = None,
        debug: bool = False,
        custom_error_status: int = 400,
        custom_error_messages: Optional[Dict[str, str]] = None,
        **kwargs: Any,
    ):
        config = {
            "allow_origins": allow_origins or [],
            "blacklist_origins": blacklist_origins or [],
            "allow_methods": allow_methods
            or ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
            "blacklist_headers": blacklist_headers or [],
            "allow_headers": allow_headers or [],
            "allow_credentials": allow_credentials,
            "allow_origin_regex": allow_origin_regex,
            "expose_headers": expose_headers or [],
            "max_age": max_age,
            "strict_origin_checking": strict_origin_checking,
            "dynamic_origin_validator": dynamic_origin_validator,
            "debug": debug,
            "custom_error_status": custom_error_status,
            "custom_error_messages": None,
        }
        super().__init__(config=config, **kwargs)

    @property
    def allow_origins(self) -> List[str]:
        return self._config["allow_origins"]

    @property
    def blacklist_origins(self) -> List[str]:
        return self._config["blacklist_origins"]

    @property
    def allow_methods(self) -> List[str]:
        return self._config["allow_methods"]

    @property
    def blacklist_headers(self) -> List[str]:
        return self._config["blacklist_headers"]

    @property
    def allow_headers(self) -> List[str]:
        return self._config["allow_headers"]

    @property
    def allow_credentials(self) -> bool:
        return self._config["allow_credentials"]

    @property
    def allow_origin_regex(self) -> Optional[str]:
        return self._config["allow_origin_regex"]

    @property
    def expose_headers(self) -> List[str]:
        return self._config["expose_headers"]

    @property
    def max_age(self) -> int:
        return self._config["max_age"]

    @property
    def strict_origin_checking(self) -> bool:
        return self._config["strict_origin_checking"]

    @property
    def dynamic_origin_validator(self) -> Optional[Callable[[Optional[str]], bool]]:
        return self._config["dynamic_origin_validator"]

    @property
    def debug(self) -> bool:
        return self._config["debug"]

    @property
    def custom_error_status(self) -> int:
        return self._config["custom_error_status"]

    @property
    def custom_error_messages(self) -> Dict[str, str]:
        return self._config["custom_error_messages"]
