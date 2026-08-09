"""
Shield — HTTP security header middleware for sillo applications.
Provides comprehensive security features and headers.

Usage::

    from sillo.security import Shield
    from sillo import SilloApp

    app = SilloApp()
    app.use(Shield())
"""

from sillo.middleware.base import BaseMiddleware
from sillo.types import Request, Response


class Shield(BaseMiddleware):
    """Shield"""

    def __init__(
        self,
        # Content Security Policy
        csp_enabled: bool = True,
        csp_policy: dict[str, str | list[str]] | None = None,
        csp_report_only: bool = False,
        # HSTS
        hsts_enabled: bool = True,
        hsts_max_age: int = 31536000,
        hsts_include_subdomains: bool = True,
        hsts_preload: bool = False,
        # XSS Protection
        xss_protection: bool = True,
        xss_mode: str = "block",
        # Frame Options
        frame_options: str = "DENY",
        frame_options_allow_from: str | None = None,
        # Content Type Options
        content_type_options: bool = True,
        # Referrer Policy
        referrer_policy: str = "strict-origin-when-cross-origin",
        # Permissions Policy
        permissions_policy: dict[str, str | list[str]] | None = None,
        # SSL/HTTPS
        ssl_redirect: bool = False,
        ssl_host: str | None = None,
        ssl_permanent: bool = True,
        # Cache Control
        cache_control: str = "no-store, no-cache, must-revalidate, proxy-revalidate",
        # Clear Site Data
        clear_site_data: list[str] | None = None,
        # DNS Prefetch
        dns_prefetch_control: str = "off",
        # Download Options
        download_options: str = "noopen",
        # Cross-Origin Options
        cross_origin_opener_policy: str = "same-origin",
        cross_origin_embedder_policy: str = "require-corp",
        cross_origin_resource_policy: str = "same-origin",
        # Expect-CT
        expect_ct: bool = False,
        expect_ct_max_age: int = 86400,
        expect_ct_enforce: bool = False,
        expect_ct_report_uri: str | None = None,
        # Report-To
        report_to: dict[str, list[dict]] | None = None,
        # NEL (Network Error Logging)
        nel: dict | None = None,
        # Trusted Types
        trusted_types: bool = False,
        trusted_types_policies: list[str] | None = None,
        # Server
        hide_server: bool = True,
        server_header: str | None = None,
    ):
        """Init"""
        self.csp_enabled = csp_enabled
        self.csp_policy = csp_policy or {
            "default-src": ["'self'"],
            "script-src": ["'self'"],
            "style-src": ["'self'"],
            "img-src": ["'self'"],
            "connect-src": ["'self'"],
            "font-src": ["'self'"],
            "object-src": ["'none'"],
            "media-src": ["'self'"],
            "frame-src": ["'none'"],
            "base-uri": ["'self'"],
            "form-action": ["'self'"],
        }
        self.csp_report_only = csp_report_only

        self.hsts_enabled = hsts_enabled
        self.hsts_max_age = hsts_max_age
        self.hsts_include_subdomains = hsts_include_subdomains
        self.hsts_preload = hsts_preload

        self.xss_protection = xss_protection
        self.xss_mode = xss_mode

        self.frame_options = frame_options
        self.frame_options_allow_from = frame_options_allow_from

        self.content_type_options = content_type_options
        self.referrer_policy = referrer_policy
        self.permissions_policy = permissions_policy or {}

        self.ssl_redirect = ssl_redirect
        self.ssl_host = ssl_host
        self.ssl_permanent = ssl_permanent

        self.cache_control = cache_control
        self.clear_site_data = clear_site_data or []
        self.dns_prefetch_control = dns_prefetch_control
        self.download_options = download_options

        self.cross_origin_opener_policy = cross_origin_opener_policy
        self.cross_origin_embedder_policy = cross_origin_embedder_policy
        self.cross_origin_resource_policy = cross_origin_resource_policy

        self.expect_ct = expect_ct
        self.expect_ct_max_age = expect_ct_max_age
        self.expect_ct_enforce = expect_ct_enforce
        self.expect_ct_report_uri = expect_ct_report_uri

        self.report_to = report_to or {}
        self.nel = nel or {}

        self.trusted_types = trusted_types
        self.trusted_types_policies = trusted_types_policies or []

        self.hide_server = hide_server
        self.server_header = server_header

    def _build_csp_header(self) -> str:
        """Build Csp Header"""
        policies = []
        for directive, sources in self.csp_policy.items():
            if isinstance(sources, str):
                sources = [sources]
            policies.append(f"{directive} {' '.join(sources)}")
        return "; ".join(policies)

    def _build_permissions_policy(self) -> str:
        """Build Permissions Policy"""
        policies = []
        for feature, setting in self.permissions_policy.items():
            if isinstance(setting, str):
                policies.append(f"{feature}={setting}")
            elif isinstance(setting, list):
                policies.append(f"{feature}=({' '.join(setting)})")
        return ", ".join(policies)

    async def __call__(self, request: Request, response: Response, call_next):
        """Call"""
        if self.ssl_redirect and request.url.scheme != "https":
            redirect_url = (
                f"https://{self.ssl_host or request.url.hostname}{request.url.path}"
            )
            return response.redirect(
                url=redirect_url, status_code=301 if self.ssl_permanent else 302
            )

        await call_next()

        headers = dict(response.headers)

        if self.csp_enabled:
            header_name = (
                "Content-Security-Policy-Report-Only"
                if self.csp_report_only
                else "Content-Security-Policy"
            )
            headers[header_name] = self._build_csp_header()

        if self.hsts_enabled:
            hsts_value = f"max-age={self.hsts_max_age}"
            if self.hsts_include_subdomains:
                hsts_value += "; includeSubDomains"
            if self.hsts_preload:
                hsts_value += "; preload"
            headers["Strict-Transport-Security"] = hsts_value

        if self.xss_protection:
            headers["X-XSS-Protection"] = f"1; mode={self.xss_mode}"

        if self.frame_options_allow_from:
            headers["X-Frame-Options"] = f"ALLOW-FROM {self.frame_options_allow_from}"
        else:
            headers["X-Frame-Options"] = self.frame_options

        if self.content_type_options:
            headers["X-Content-Type-Options"] = "nosniff"

        headers["Referrer-Policy"] = self.referrer_policy

        if self.permissions_policy:
            headers["Permissions-Policy"] = self._build_permissions_policy()

        headers["Cache-Control"] = self.cache_control

        if self.clear_site_data:
            headers["Clear-Site-Data"] = ", ".join(
                f'"{x}"' for x in self.clear_site_data
            )

        headers["X-DNS-Prefetch-Control"] = self.dns_prefetch_control

        headers["X-Download-Options"] = self.download_options

        headers["Cross-Origin-Opener-Policy"] = self.cross_origin_opener_policy
        headers["Cross-Origin-Embedder-Policy"] = self.cross_origin_embedder_policy
        headers["Cross-Origin-Resource-Policy"] = self.cross_origin_resource_policy

        if self.expect_ct:
            expect_ct_value = f"max-age={self.expect_ct_max_age}"
            if self.expect_ct_enforce:
                expect_ct_value += ", enforce"
            if self.expect_ct_report_uri:
                expect_ct_value += f', report-uri="{self.expect_ct_report_uri}"'
            headers["Expect-CT"] = expect_ct_value

        if self.report_to:
            headers["Report-To"] = str(self.report_to)

        if self.nel:
            headers["NEL"] = str(self.nel)

        if self.trusted_types:
            policy_value = "require-trusted-types-for 'script'"
            if self.trusted_types_policies:
                policy_value += (
                    f"; trusted-types {' '.join(self.trusted_types_policies)}"
                )
            if "Content-Security-Policy" in headers:
                headers["Content-Security-Policy"] += f"; {policy_value}"
            else:
                headers["Content-Security-Policy"] = policy_value

        if self.hide_server:
            headers.pop("Server", None)
        elif self.server_header:
            headers["Server"] = self.server_header
        response.set_headers(headers)
        return response
