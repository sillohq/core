import typing
from typing import Any


class CSRFConfig:
    """
    Typed configuration for CSRF middleware.
    """

    def __init__(
        self,
        enabled: bool = False,
        required_urls: list[str] | None = None,
        exempt_urls: list[str] | None = None,
        sensitive_cookies: list[str] | None = None,
        safe_methods: list[str] | None = None,
        cookie_name: str = "csrftoken",
        cookie_path: str = "/",
        cookie_domain: str | None = None,
        cookie_secure: bool = False,
        cookie_httponly: bool = True,
        cookie_samesite: typing.Literal["lax", "none", "strict"] = "lax",
        header_name: str = "X-CSRFToken",
        secret_key: str | None = None,
        **kwargs: Any,
    ):
        """Init"""
        config = {
            "enabled": enabled,
            "required_urls": required_urls or ["*"],
            "exempt_urls": exempt_urls or [],
            "sensitive_cookies": sensitive_cookies or [],
            "safe_methods": safe_methods or ["GET", "HEAD", "OPTIONS", "TRACE"],
            "cookie_name": cookie_name,
            "cookie_path": cookie_path,
            "cookie_domain": cookie_domain,
            "cookie_secure": cookie_secure,
            "cookie_httponly": cookie_httponly,
            "cookie_samesite": cookie_samesite,
            "header_name": header_name,
            "secret_key": secret_key,
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
    def enabled(self) -> bool:
        """Enabled"""
        return self._config["enabled"]

    @property
    def required_urls(self) -> list[str]:
        """Required Urls"""
        return self._config["required_urls"]

    @property
    def exempt_urls(self) -> list[str]:
        """Exempt Urls"""
        return self._config["exempt_urls"]

    @property
    def sensitive_cookies(self) -> list[str]:
        """Sensitive Cookies"""
        return self._config["sensitive_cookies"]

    @property
    def safe_methods(self) -> list[str]:
        """Safe Methods"""
        return self._config["safe_methods"]

    @property
    def cookie_name(self) -> str:
        """Cookie Name"""
        return self._config["cookie_name"]

    @property
    def cookie_path(self) -> str:
        """Cookie Path"""
        return self._config["cookie_path"]

    @property
    def cookie_domain(self) -> str | None:
        """Cookie Domain"""
        return self._config["cookie_domain"]

    @property
    def cookie_secure(self) -> bool:
        """Cookie Secure"""
        return self._config["cookie_secure"]

    @property
    def cookie_httponly(self) -> bool:
        """Cookie Httponly"""
        return self._config["cookie_httponly"]

    @property
    def cookie_samesite(self) -> typing.Literal["lax", "none", "strict"]:
        """Cookie Samesite"""
        return self._config["cookie_samesite"]

    @property
    def header_name(self) -> str:
        """Header Name"""
        return self._config["header_name"]

    @property
    def secret_key(self) -> str | None:
        """Secret Key"""
        return self._config.get("secret_key")
