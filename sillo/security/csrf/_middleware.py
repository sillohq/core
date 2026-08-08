import re
import secrets
import typing
from typing import Any

from itsdangerous import BadSignature, URLSafeSerializer

from sillo.core.http import Request, Response
from sillo.middleware.base import BaseMiddleware

from .config import CSRFConfig


class CSRFMiddleware(BaseMiddleware):
    """
    Middleware to protect against Cross-Site Request Forgery (CSRF) attacks for sillo.
    """

    def __init__(
        self,
        config: CSRFConfig | None = None,
        **kwargs: Any,
    ) -> None:
        """Init"""
        if config is not None:
            if not isinstance(config, CSRFConfig):
                raise TypeError("config must be a CSRFConfig instance")
            self.csrf_config = config
        else:
            self.csrf_config = None

        self.use_csrf = False
        self.secret = None

        if self.csrf_config:
            self._setup_csrf_config()
            if self.secret:
                self.serializer = URLSafeSerializer(self.secret, "csrftoken")

    def _setup_csrf_config(self) -> None:
        """Setup CSRF configuration from config object."""
        cfg = self.csrf_config
        self.use_csrf = cfg.enabled  # ty:ignore[unresolved-attribute]
        self.required_urls = cfg.required_urls  # ty:ignore[unresolved-attribute]
        self.exempt_urls = cfg.exempt_urls  # ty:ignore[unresolved-attribute]
        self.sensitive_cookies = cfg.sensitive_cookies  # ty:ignore[unresolved-attribute]
        self.safe_methods = set(cfg.safe_methods)  # ty:ignore[unresolved-attribute]
        self.cookie_name = cfg.cookie_name  # ty:ignore[unresolved-attribute]
        self.cookie_path = cfg.cookie_path  # ty:ignore[unresolved-attribute]
        self.cookie_domain = cfg.cookie_domain  # ty:ignore[unresolved-attribute]
        self.cookie_secure = cfg.cookie_secure  # ty:ignore[unresolved-attribute]
        self.cookie_httponly = cfg.cookie_httponly  # ty:ignore[unresolved-attribute]
        self.cookie_samesite = cfg.cookie_samesite  # ty:ignore[unresolved-attribute]
        self.header_name = cfg.header_name  # ty:ignore[unresolved-attribute]
        self.secret = cfg.secret_key  # ty:ignore[unresolved-attribute]

    async def process_request(
        self,
        request: Request,
        response: Response,
        call_next: typing.Callable[..., typing.Awaitable[typing.Any]],
    ):
        """Process Request"""
        if not self.csrf_config or not self.use_csrf:
            return await call_next()

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
            if not self._csrf_tokens_match(csrf_cookie, submitted_csrf_token):  # ty:ignore[invalid-argument-type]
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

    def _has_sensitive_cookies(self, cookies: dict[str, typing.Any]) -> bool:
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
        return self.serializer.dumps(secrets.token_urlsafe(32))  # ty: ignore[unresolved-attribute]

    def _csrf_tokens_match(self, token1: str, token2: str) -> bool:
        """Compare two CSRF tokens securely."""
        try:
            decoded1 = self.serializer.loads(token1)  # ty: ignore[unresolved-attribute]
            decoded2 = self.serializer.loads(token2)  # ty: ignore[unresolved-attribute]
            return secrets.compare_digest(decoded1, decoded2)
        except BadSignature:
            return False
