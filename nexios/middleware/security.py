"""
Security middleware for Nexios applications.
Provides comprehensive security features and headers.
"""

from typing import Dict, List, Optional, Union

from nexios.middleware import BaseMiddleware
from nexios.types import Request, Response


class SecurityMiddleware(BaseMiddleware):
    def __init__(
        self,
        # Content Security Policy
        csp_enabled: bool = True,
        csp_policy: Optional[Dict[str, Union[str, List[str]]]] = None,
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
        frame_options_allow_from: Optional[str] = None,
        # Content Type Options
        content_type_options: bool = True,
        # Referrer Policy
        referrer_policy: str = "strict-origin-when-cross-origin",
        # Permissions Policy
        permissions_policy: Optional[Dict[str, Union[str, List[str]]]] = None,
        # SSL/HTTPS
        ssl_redirect: bool = False,
        ssl_host: Optional[str] = None,
        ssl_permanent: bool = True,
        # Cache Control
        cache_control: str = "no-store, no-cache, must-revalidate, proxy-revalidate",
        # Clear Site Data
        clear_site_data: Optional[List[str]] = None,
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
        expect_ct_report_uri: Optional[str] = None,
        # Report-To
        report_to: Optional[Dict[str, List[Dict]]] = None,
        # NEL (Network Error Logging)
        nel: Optional[Dict] = None,
        # Trusted Types
        trusted_types: bool = False,
        trusted_types_policies: Optional[List[str]] = None,
        # Server
        hide_server: bool = True,
        server_header: Optional[str] = None,
    ):
        """Initialize SecurityMiddleware with various security options.

        Args:
            csp_enabled: Enable Content Security Policy
            csp_policy: CSP directives
            csp_report_only: Use CSP in report-only mode
            hsts_enabled: Enable HTTP Strict Transport Security
            hsts_max_age: HSTS max age in seconds
            hsts_include_subdomains: Include subdomains in HSTS
            hsts_preload: Allow preloading of HSTS
            xss_protection: Enable X-XSS-Protection header
            xss_mode: XSS protection mode
            frame_options: X-Frame-Options header value
            frame_options_allow_from: Allow framing from specific origin
            content_type_options: Enable X-Content-Type-Options
            referrer_policy: Referrer-Policy header value
            permissions_policy: Permissions-Policy directives
            ssl_redirect: Enable HTTPS redirect
            ssl_host: Host to redirect to for HTTPS
            ssl_permanent: Use permanent redirect for HTTPS
            cache_control: Cache-Control header value
            clear_site_data: Clear-Site-Data header values
            dns_prefetch_control: X-DNS-Prefetch-Control header value
            download_options: X-Download-Options header value
            cross_origin_opener_policy: Cross-Origin-Opener-Policy value
            cross_origin_embedder_policy: Cross-Origin-Embedder-Policy value
            cross_origin_resource_policy: Cross-Origin-Resource-Policy value
            expect_ct: Enable Expect-CT header
            expect_ct_max_age: Expect-CT max age
            expect_ct_enforce: Enforce Expect-CT
            expect_ct_report_uri: Expect-CT report URI
            report_to: Report-To header configuration
            nel: NEL (Network Error Logging) configuration
            trusted_types: Enable Trusted Types
            trusted_types_policies: List of trusted type policies
            hide_server: Hide the Server header
            server_header: Custom Server header value
        """
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
        """Build the Content-Security-Policy header value."""
        policies = []
        for directive, sources in self.csp_policy.items():
            if isinstance(sources, str):
                sources = [sources]
            policies.append(f"{directive} {' '.join(sources)}")
        return "; ".join(policies)

    def _build_permissions_policy(self) -> str:
        """Build the Permissions-Policy header value."""
        policies = []
        for feature, setting in self.permissions_policy.items():
            if isinstance(setting, str):
                policies.append(f"{feature}={setting}")
            elif isinstance(setting, list):
                policies.append(f"{feature}=({' '.join(setting)})")
        return ", ".join(policies)

    async def __call__(self, request: Request, response: Response, call_next):
        """Process the request and add security headers."""
        # Handle HTTPS redirect
        if self.ssl_redirect and not request.url.scheme == "https":
            redirect_url = (
                f"https://{self.ssl_host or request.url.hostname}{request.url.path}"
            )
            return response.redirect(
                url=redirect_url, status_code=301 if self.ssl_permanent else 302
            )

        # Call the next middleware/route handler
        await call_next()

        # Add security headers
        headers = dict(response.headers)

        # Content-Security-Policy
        if self.csp_enabled:
            header_name = (
                "Content-Security-Policy-Report-Only"
                if self.csp_report_only
                else "Content-Security-Policy"
            )
            headers[header_name] = self._build_csp_header()

        # HSTS
        if self.hsts_enabled:
            hsts_value = f"max-age={self.hsts_max_age}"
            if self.hsts_include_subdomains:
                hsts_value += "; includeSubDomains"
            if self.hsts_preload:
                hsts_value += "; preload"
            headers["Strict-Transport-Security"] = hsts_value

        # XSS Protection
        if self.xss_protection:
            headers["X-XSS-Protection"] = f"1; mode={self.xss_mode}"

        # Frame Options
        if self.frame_options_allow_from:
            headers["X-Frame-Options"] = f"ALLOW-FROM {self.frame_options_allow_from}"
        else:
            headers["X-Frame-Options"] = self.frame_options

        # Content Type Options
        if self.content_type_options:
            headers["X-Content-Type-Options"] = "nosniff"

        # Referrer Policy
        headers["Referrer-Policy"] = self.referrer_policy

        # Permissions Policy
        if self.permissions_policy:
            headers["Permissions-Policy"] = self._build_permissions_policy()

        # Cache Control
        headers["Cache-Control"] = self.cache_control

        # Clear Site Data
        if self.clear_site_data:
            headers["Clear-Site-Data"] = ", ".join(
                f'"{x}"' for x in self.clear_site_data
            )

        # DNS Prefetch Control
        headers["X-DNS-Prefetch-Control"] = self.dns_prefetch_control

        # Download Options
        headers["X-Download-Options"] = self.download_options

        # Cross-Origin Policies
        headers["Cross-Origin-Opener-Policy"] = self.cross_origin_opener_policy
        headers["Cross-Origin-Embedder-Policy"] = self.cross_origin_embedder_policy
        headers["Cross-Origin-Resource-Policy"] = self.cross_origin_resource_policy

        # Expect-CT
        if self.expect_ct:
            expect_ct_value = f"max-age={self.expect_ct_max_age}"
            if self.expect_ct_enforce:
                expect_ct_value += ", enforce"
            if self.expect_ct_report_uri:
                expect_ct_value += f', report-uri="{self.expect_ct_report_uri}"'
            headers["Expect-CT"] = expect_ct_value

        # Report-To
        if self.report_to:
            headers["Report-To"] = str(self.report_to)

        # NEL
        if self.nel:
            headers["NEL"] = str(self.nel)

        # Trusted Types
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

        # Server header
        if self.hide_server:
            headers.pop("Server", None)
        elif self.server_header:
            headers["Server"] = self.server_header
        response.set_headers(headers)
        return response
