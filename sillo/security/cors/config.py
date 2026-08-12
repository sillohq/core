from collections.abc import Callable
from typing import Any


class CorsConfig:
    """
    Typed configuration for CORS middleware.
    """

    def __init__(
        self,
        allow_origins: list[str] | None = None,
        blacklist_origins: list[str] | None = None,
        allow_methods: list[str] | None = None,
        blacklist_headers: list[str] | None = None,
        allow_headers: list[str] | None = None,
        # Off unless asked for. Credentialed CORS lets another origin read a
        # response authenticated as the visitor, which is not something to
        # turn on by default — and combined with a wildcard origin it is the
        # difference between a public API and one every site can read as your
        # signed-in users.
        allow_credentials: bool = False,
        allow_origin_regex: str | None = None,
        expose_headers: list[str] | None = None,
        max_age: int = 600,
        strict_origin_checking: bool = False,
        dynamic_origin_validator: Callable[[str | None], bool] | None = None,
        debug: bool = False,
        custom_error_status: int = 400,
        custom_error_messages: dict[str, str] | None = None,
        **kwargs: Any,
    ):
        """Init"""
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
        config.update(kwargs)
        self._config: dict[str, Any] = config

    def __getattr__(self, name: str):
        if name == "_config":
            raise AttributeError(name)
        return self._config.get(name)

    def to_dict(self) -> dict[str, Any]:
        return dict(self._config)

    @property
    def allow_origins(self) -> list[str]:
        """Allow Origins"""
        return self._config["allow_origins"]

    @property
    def blacklist_origins(self) -> list[str]:
        """Blacklist Origins"""
        return self._config["blacklist_origins"]

    @property
    def allow_methods(self) -> list[str]:
        """Allow Methods"""
        return self._config["allow_methods"]

    @property
    def blacklist_headers(self) -> list[str]:
        """Blacklist Headers"""
        return self._config["blacklist_headers"]

    @property
    def allow_headers(self) -> list[str]:
        """Allow Headers"""
        return self._config["allow_headers"]

    @property
    def allow_credentials(self) -> bool:
        """Allow Credentials"""
        return self._config["allow_credentials"]

    @property
    def allow_origin_regex(self) -> str | None:
        """Allow Origin Regex"""
        return self._config["allow_origin_regex"]

    @property
    def expose_headers(self) -> list[str]:
        """Expose Headers"""
        return self._config["expose_headers"]

    @property
    def max_age(self) -> int:
        """Max Age"""
        return self._config["max_age"]

    @property
    def strict_origin_checking(self) -> bool:
        """Strict Origin Checking"""
        return self._config["strict_origin_checking"]

    @property
    def dynamic_origin_validator(self) -> Callable[[str | None], bool] | None:
        """Dynamic Origin Validator"""
        return self._config["dynamic_origin_validator"]

    @property
    def debug(self) -> bool:
        """Debug"""
        return self._config["debug"]

    @property
    def custom_error_status(self) -> int:
        """Custom Error Status"""
        return self._config["custom_error_status"]

    @property
    def custom_error_messages(self) -> dict[str, str]:
        """Custom Error Messages"""
        return self._config["custom_error_messages"]
