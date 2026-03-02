import re
import secrets
import typing
from typing import Any, List, Optional

from nexios.config.base import MakeConfig


class CSRFConfig(MakeConfig):
    """
    Typed configuration for CSRF middleware.
    """

    def __init__(
        self,
        enabled: bool = False,
        required_urls: Optional[List[str]] = None,
        exempt_urls: Optional[List[str]] = None,
        sensitive_cookies: Optional[List[str]] = None,
        safe_methods: Optional[List[str]] = None,
        cookie_name: str = "csrftoken",
        cookie_path: str = "/",
        cookie_domain: Optional[str] = None,
        cookie_secure: bool = False,
        cookie_httponly: bool = True,
        cookie_samesite: typing.Literal["lax", "none", "strict"] = "lax",
        header_name: str = "X-CSRFToken",
        **kwargs: Any,
    ):
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
        }
        super().__init__(config=config, **kwargs)

    @property
    def enabled(self) -> bool:
        return self._config["enabled"]

    @property
    def required_urls(self) -> List[str]:
        return self._config["required_urls"]

    @property
    def exempt_urls(self) -> List[str]:
        return self._config["exempt_urls"]

    @property
    def sensitive_cookies(self) -> List[str]:
        return self._config["sensitive_cookies"]

    @property
    def safe_methods(self) -> List[str]:
        return self._config["safe_methods"]

    @property
    def cookie_name(self) -> str:
        return self._config["cookie_name"]

    @property
    def cookie_path(self) -> str:
        return self._config["cookie_path"]

    @property
    def cookie_domain(self) -> Optional[str]:
        return self._config["cookie_domain"]

    @property
    def cookie_secure(self) -> bool:
        return self._config["cookie_secure"]

    @property
    def cookie_httponly(self) -> bool:
        return self._config["cookie_httponly"]

    @property
    def cookie_samesite(self) -> typing.Literal["lax", "none", "strict"]:
        return self._config["cookie_samesite"]

    @property
    def header_name(self) -> str:
        return self._config["header_name"]
