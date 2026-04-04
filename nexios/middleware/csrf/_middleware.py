import re
import secrets
import typing
import warnings
from typing import Any, Dict, Optional, Union

from itsdangerous import BadSignature, URLSafeSerializer

from nexios.config import get_config
from nexios.config.base import MakeConfig
from nexios.http import Request, Response
from nexios.middleware.base import BaseMiddleware


class CSRFMiddleware(BaseMiddleware):
    """
    Middleware to protect against Cross-Site Request Forgery (CSRF) attacks for Nexios.
    """

    def __init__(
        self, config: Optional[Union[MakeConfig, Dict[str, Any]]] = None, **kwargs: Any
    ) -> None:

        # Handle config parameter (new approach)
        if config is not None:
            if isinstance(config, MakeConfig):
                self.config = config
            elif isinstance(config, dict):
                self.config = MakeConfig(config)
            else:
                raise TypeError("config must be a MakeConfig instance or dictionary")
        else:
            # Fallback to get_config() (old approach) with warning
            warnings.warn(
                "Using get_config() for CSRF middleware is deprecated. "
                "Please pass config directly to CSRFMiddleware constructor.",
                DeprecationWarning,
                stacklevel=2,
            )
            self.config = None

        self.use_csrf = False
        self.secret = None

        # Setup configuration if provided
        if self.config:
            self._setup_csrf_config()

    def _setup_csrf_config(self) -> None:
        """Setup CSRF configuration from config object."""
        # Check if CSRF is enabled
        self.use_csrf = (
            (
                getattr(self.config, "csrf_enabled", False)
                or getattr(self.config, "use_csrf", False)
                or getattr(self.config, "enabled", False)
            )
            if self.config
            else False
        )

        # Setup CSRF configuration attributes
        self.required_urls: typing.List[str] = (
            getattr(self.config, "csrf_required_urls", ["*"])
            or getattr(self.config, "required_urls", ["*"])
            or ["*"]
        )
        self.exempt_urls = getattr(self.config, "csrf_exempt_urls", None) or getattr(
            self.config, "exempt_urls", None
        )
        self.sensitive_cookies = getattr(
            self.config, "csrf_sensitive_cookies", None
        ) or getattr(self.config, "sensitive_cookies", None)
        self.safe_methods = set(
            getattr(self.config, "csrf_safe_methods", None)
            or getattr(self.config, "safe_methods", None)
            or [
                "GET",
                "HEAD",
                "OPTIONS",
                "TRACE",
            ]
        )
        self.cookie_name = getattr(
            self.config, "csrf_cookie_name", "csrftoken"
        ) or getattr(self.config, "cookie_name", "csrftoken")
        self.cookie_path = getattr(self.config, "csrf_cookie_path", "/") or getattr(
            self.config, "cookie_path", "/"
        )
        self.cookie_domain = getattr(
            self.config, "csrf_cookie_domain", None
        ) or getattr(self.config, "cookie_domain", None)
        self.cookie_secure = getattr(
            self.config, "csrf_cookie_secure", False
        ) or getattr(self.config, "cookie_secure", False)
        self.cookie_httponly = getattr(
            self.config, "csrf_cookie_httponly", True
        ) or getattr(self.config, "cookie_httponly", True)
        self.cookie_samesite: typing.Literal["lax", "none", "strict"] = getattr(
            self.config, "csrf_cookie_samesite", "lax"
        ) or getattr(self.config, "cookie_samesite", "lax")
        self.header_name = getattr(
            self.config, "csrf_header_name", "X-CSRFToken"
        ) or getattr(self.config, "header_name", "X-CSRFToken")

    async def process_request(
        self,
        request: Request,
        response: Response,
        call_next: typing.Callable[..., typing.Awaitable[typing.Any]],
    ):
        """
        Process the incoming request to validate the CSRF token for unsafe HTTP methods.
        """
        # Handle configuration setup if not done in __init__
        if not hasattr(self, "config") or self.config is None:
            warnings.warn(
                "Using get_config() for CSRF middleware is deprecated. "
                "Please pass config directly to CSRFMiddleware constructor.",
                DeprecationWarning,
                stacklevel=3,
            )
            try:
                app_config = get_config()
                self.use_csrf = app_config.csrf_enabled or False
                if self.use_csrf:
                    assert app_config.secret_key is not None, (
                        "Secret key is required for CSRF protection"
                    )
                    self.secret = app_config.secret_key
                    self.serializer = URLSafeSerializer(self.secret, "csrftoken")
                    self.required_urls = app_config.csrf_required_urls or ["*"]
                    self.exempt_urls = app_config.csrf_exempt_urls
                    self.sensitive_cookies = app_config.csrf_sensitive_cookies
                    self.safe_methods = set(
                        app_config.csrf_safe_methods
                        or [
                            "GET",
                            "HEAD",
                            "OPTIONS",
                            "TRACE",
                        ]
                    )
                    self.cookie_name = app_config.csrf_cookie_name or "csrftoken"
                    self.cookie_path = app_config.csrf_cookie_path or "/"
                    self.cookie_domain = app_config.csrf_cookie_domain
                    self.cookie_secure = app_config.csrf_cookie_secure or False
                    self.cookie_httponly = app_config.csrf_cookie_httponly or True
                    self.cookie_samesite = app_config.csrf_cookie_samesite or "lax"
                    self.header_name = app_config.csrf_header_name or "X-CSRFToken"
            except (RuntimeError, AssertionError):
                self.use_csrf = False
        elif self.use_csrf:
            # Always get secret key from get_config() at runtime, not from config passed to __init__
            try:
                app_config = get_config()
                self.secret = app_config.secret_key
                if self.secret:
                    self.serializer = URLSafeSerializer(self.secret, "csrftoken")
                else:
                    self.use_csrf = False
            except RuntimeError:
                self.use_csrf = False

        if not self.use_csrf:
            return await call_next()

        csrf_token = self._generate_csrf_token()
        request.state.csrf_token = csrf_token
        csrf_cookie = request.cookies.get(self.cookie_name)
        if request.method.upper() in self.safe_methods:
            return await call_next()

        if self._url_is_required(request.url.path) or (
            self._url_is_exempt(request.url.path)
            and self._has_sensitive_cookies(request.cookies)
        ):
            submitted_csrf_token = request.headers.get(self.header_name)
            if not submitted_csrf_token and request.headers.get(
                "content-type", ""
            ).startswith("application/x-www-form-urlencoded"):
                form = await request.form
                submitted_csrf_token = form.get("csrftoken")
            if not csrf_cookie:
                return response.text(
                    "CSRF token missing from cookies", status_code=403
                ).delete_cookie(self.cookie_name, self.cookie_path, self.cookie_domain)
            if not submitted_csrf_token:
                return response.text(
                    "CSRF token missing from headers", status_code=403
                ).delete_cookie(self.cookie_name, self.cookie_path, self.cookie_domain)
            if not self._csrf_tokens_match(csrf_cookie, submitted_csrf_token):  # type: ignore
                return response.text(
                    "CSRF token incorrect", status_code=403
                ).delete_cookie(self.cookie_name, self.cookie_path, self.cookie_domain)
        return await call_next()

    async def process_response(self, request: Request, response: Response):
        """
        Inject the CSRF token into the response for client-side usage if not already set.
        """
        if not self.use_csrf:
            return
        csrf_token = request.state.csrf_token

        response.set_cookie(
            key=self.cookie_name,
            value=csrf_token,
            path=self.cookie_path,
            domain=self.cookie_domain,
            secure=self.cookie_secure,
            httponly=self.cookie_httponly,
            samesite=self.cookie_samesite,
        )

    def _has_sensitive_cookies(self, cookies: typing.Dict[str, typing.Any]) -> bool:
        """Check if the request contains sensitive cookies."""
        if not self.sensitive_cookies:
            return True
        for sensitive_cookie in self.sensitive_cookies:
            if sensitive_cookie in cookies:
                return True
        return False

    def _url_is_required(self, url: str) -> bool:
        """Check if the URL requires CSRF validation."""

        if not self.required_urls:
            return False

        if "*" in self.required_urls:
            return True
        for required_url in self.required_urls:
            match = re.match(required_url, url)
            if match and match.group() == url:
                return True
        return False

    def _url_is_exempt(self, url: str) -> bool:
        """Check if the URL is exempt from CSRF validation."""
        if not self.exempt_urls:
            return False
        for exempt_url in self.exempt_urls:
            match = re.match(exempt_url, url)
            if match and match.group() == url:
                return True
        return False

    def _generate_csrf_token(self) -> str:
        """Generate a secure CSRF token."""
        return self.serializer.dumps(secrets.token_urlsafe(32))

    def _csrf_tokens_match(self, token1: str, token2: str) -> bool:
        """Compare two CSRF tokens securely."""
        try:
            decoded1 = self.serializer.loads(token1)
            decoded2 = self.serializer.loads(token2)
            return secrets.compare_digest(decoded1, decoded2)
        except BadSignature:
            return False
