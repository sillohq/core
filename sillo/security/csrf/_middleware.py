import re
import secrets
import typing
from typing import Any

from sillo.core.http import HttpContext
from sillo.helpers.signing import BadSignature, URLSafeSerializer
from sillo.middleware.bridge import _CachedRequest
from sillo.middleware.response_headers import ResponseHeaders
from sillo.responses import text
from sillo.types import ASGIApp, Message, Receive, Scope, Send

from .config import CSRFConfig

#: Body content types a token can be submitted in. ``multipart/form-data`` is
#: here because file-upload forms cannot set a header, so leaving it out meant
#: every upload form was a 403 with no way to pass.
_FORM_CONTENT_TYPES = (
    "application/x-www-form-urlencoded",
    "multipart/form-data",
)


class CSRFMiddleware:
    """
    Middleware to protect against Cross-Site HttpContext Forgery (CSRF) attacks for sillo.

    Uses the double-submit pattern: the same signed token is sent as a cookie
    and echoed back in a header or form field. A cross-site attacker can make
    the browser send the cookie but cannot read it, so cannot produce the copy.

    That only works if the page can read the cookie, which is why
    ``cookie_httponly`` defaults to ``False`` here — the token is not a
    credential, and hiding it from the page hides it from the code that has to
    send it back.
    """

    def __init__(
        self,
        config: CSRFConfig | None = None,
        **kwargs: Any,
    ) -> None:
        """Init

        Raises:
            TypeError: If *config* is not a :class:`CSRFConfig`.
            ValueError: If CSRF is enabled with no ``secret_key``. Without one
                there is nothing to sign with, and every request used to fail
                with ``AttributeError: no attribute 'serializer'`` from inside
                the request path rather than at startup.
        """
        # Bound on afterwards by `use()`: this is registered as a configured
        # instance, `app.use(CSRFMiddleware(config))`.
        self.app: ASGIApp | None = None

        if config is not None:
            if not isinstance(config, CSRFConfig):
                raise TypeError("config must be a CSRFConfig instance")
            self.csrf_config = config
        else:
            self.csrf_config = None

        self.use_csrf = False
        self.secret = None
        self.serializer: URLSafeSerializer | None = None

        if self.csrf_config:
            self._setup_csrf_config()

            if self.use_csrf and not self.secret:
                raise ValueError(
                    "CSRFConfig(enabled=True) needs a secret_key: tokens are "
                    "signed with it, and without one no token can be issued "
                    "or checked."
                )

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
        self.form_field = cfg.form_field  # ty:ignore[unresolved-attribute]
        self.secret = cfg.secret_key  # ty:ignore[unresolved-attribute]

        if self.secret and self.serializer is None:
            self.serializer = URLSafeSerializer(self.secret, "csrftoken")

    def _inner(self) -> ASGIApp:
        """Return the inner application, refusing to serve without one."""
        if self.app is None:
            raise RuntimeError(
                "CSRFMiddleware was constructed without an inner application "
                "and cannot serve requests. Register it with "
                "app.use(CSRFMiddleware(...))."
            )
        return self.app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Validate the CSRF token, then stamp it onto the reply."""
        app = self._inner()
        if scope["type"] != "http" or not self.csrf_config or not self.use_csrf:
            await app(scope, receive, send)
            return

        # A submitted token can arrive in the form body, which `validate()`
        # has to read to check it -- so the request is built with the same
        # buffer/replay wrapper the dispatch bridge uses, and the route
        # handler downstream still sees a body to read.
        ctx = _CachedRequest(scope, receive)

        async def send_with_csrf_cookie(message: Message) -> None:
            if message["type"] == "http.response.start":
                self.set_token_cookie(ctx, ResponseHeaders(message))
            await send(message)

        rejection = await self.validate(ctx)
        if rejection is not None:
            # `validate()` already minted a fresh `ctx.state.csrf_token` when
            # the submitted one was missing/invalid -- stamping it here too
            # means a client with no cookie yet (first request is a POST, or
            # an earlier `Set-Cookie` got dropped by a CDN/proxy) gets one on
            # the *rejection* and can retry, instead of 403-looping forever
            # because only the success path ever set the cookie.
            await rejection(scope, receive, send_with_csrf_cookie)
            return

        scope["_sillo_body_replay"] = ctx.wrapped_receive

        await app(scope, ctx.wrapped_receive, send_with_csrf_cookie)

    async def validate(self, ctx: HttpContext) -> Any | None:
        """Check the CSRF token, returning a 403 response to reject the request.

        Always sets ``ctx.state.csrf_token`` first, so the token is available
        (to a template, an API response, ...) whether or not this request
        needed one checked.
        """
        csrf_cookie = ctx.cookies.get(self.cookie_name)

        # Keep the token the visitor already holds. Minting a new one on every
        # ctx meant a second tab, a cached page or two requests in flight
        # each invalidated the others' token, and the form that was rendered a
        # moment ago answered 403.
        ctx.state.csrf_token = (
            csrf_cookie
            if self._token_is_valid(csrf_cookie)
            else self._generate_csrf_token()
        )

        if ctx.method.upper() not in self.safe_methods and self._requires_validation(
            ctx
        ):
            submitted_csrf_token = await self._submitted_token(ctx)

            if not csrf_cookie:
                return text("CSRF token missing from cookies", status_code=403)
            if not submitted_csrf_token:
                return text("CSRF token missing from headers", status_code=403)
            if not self._csrf_tokens_match(csrf_cookie, submitted_csrf_token):
                return text("CSRF token incorrect", status_code=403)

        return None

    def set_token_cookie(self, ctx: HttpContext, headers: ResponseHeaders) -> None:
        """Put the CSRF token on the outgoing response for the client to read."""
        csrf_token = getattr(ctx.state, "csrf_token", None)
        if not csrf_token:
            return

        headers.set_cookie(
            key=self.cookie_name,
            value=csrf_token,
            path=self.cookie_path,
            domain=self.cookie_domain,
            secure=self.cookie_secure,
            httponly=self.cookie_httponly,
            samesite=self.cookie_samesite,
        )

    def _requires_validation(self, ctx: HttpContext) -> bool:
        """Whether this unsafe request has to carry a token.

        An exempt URL is exempt. That reads as obvious and was not what the
        code did: the test was ``required(url) or (exempt(url) and ...)``, and
        since ``required_urls`` defaults to ``["*"]`` the first half was always
        true, so ``exempt_urls`` never excused anything and the second half was
        unreachable.

        ``sensitive_cookies`` narrows it further, for APIs authenticated by a
        header rather than by a cookie: name the cookies that carry ambient
        authority and a request without any of them cannot be a CSRF, so it
        does not need a token. Naming none keeps the safe default of treating
        every request as sensitive.
        """
        if self._url_is_exempt(ctx.url.path):
            return False

        if not self._url_is_required(ctx.url.path):
            return False

        return self._has_sensitive_cookies(ctx.cookies)

    async def _submitted_token(self, ctx: HttpContext) -> str | None:
        """Return the token the client echoed back, from header or form body."""
        submitted = ctx.headers.get(self.header_name)
        if submitted:
            return submitted

        content_type = ctx.headers.get("content-type", "")
        if not content_type.startswith(_FORM_CONTENT_TYPES):
            return None

        try:
            form = await ctx.form
        except Exception:
            # An unparseable body carries no token; that is a 403 below, not a
            # 500 out of the middleware.
            return None

        value = form.get(self.form_field)
        return value if isinstance(value, str) else None

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

    def _token_is_valid(self, token: str | None) -> bool:
        """Whether *token* is one this application signed."""
        if not token or self.serializer is None:
            return False
        try:
            self.serializer.loads(token)
        except BadSignature:
            return False
        return True

    def _csrf_tokens_match(self, token1: str, token2: str) -> bool:
        """Compare two CSRF tokens securely."""
        try:
            decoded1 = self.serializer.loads(token1)  # ty: ignore[unresolved-attribute]
            decoded2 = self.serializer.loads(token2)  # ty: ignore[unresolved-attribute]
        except BadSignature:
            return False

        if not isinstance(decoded1, str) or not isinstance(decoded2, str):
            return False

        return secrets.compare_digest(decoded1, decoded2)
