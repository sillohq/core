"""
Tests for Shield (security headers middleware)
"""

from sillo import silloApp
from sillo.core.http import Request, Response
from sillo.security import Shield
from sillo.testclient import TestClient


def create_app():
    app = silloApp()
    app.use(Shield(csp_enabled=True))

    @app.get("/test")
    async def test_route(request: Request, response: Response):
        return response.json({"message": "OK"})

    @app.post("/data")
    async def data_route(request: Request, response: Response):
        return response.json({"received": True})

    return app


def test_security_middleware_basic():
    app = create_app()
    app.use(Shield())

    with TestClient(app) as client:
        resp = client.get("/test")
        assert resp.status_code == 200
        assert "Content-Security-Policy" in resp.headers
        assert "X-Content-Type-Options" in resp.headers
        assert "X-Frame-Options" in resp.headers
        assert "X-XSS-Protection" in resp.headers


def test_csp_headers_enabled():
    app = create_app()
    app.use(Shield(csp_enabled=True))

    with TestClient(app) as client:
        resp = client.get("/test")
        assert resp.status_code == 200
        csp = resp.headers["Content-Security-Policy"]
        assert "default-src 'self'" in csp
        assert "script-src 'self'" in csp
        assert "style-src 'self'" in csp
        assert "object-src 'none'" in csp


def test_csp_headers_disabled():
    app = create_app()
    app.http_middleware = []
    app.use(Shield(csp_enabled=False))

    with TestClient(app) as client:
        resp = client.get("/test")
        assert "Content-Security-Policy" not in resp.headers


def test_csp_report_only():
    app = create_app()
    app.http_middleware = []
    app.use(Shield(csp_enabled=True, csp_report_only=True))

    with TestClient(app) as client:
        resp = client.get("/test")
        assert "Content-Security-Policy-Report-Only" in resp.headers
        assert "Content-Security-Policy" not in resp.headers


def test_custom_csp_policy():
    app = create_app()
    custom_csp = {
        "default-src": ["'self'", "https://example.com"],
        "script-src": ["'self'", "'unsafe-inline'"],
        "img-src": ["'self'", "data:", "https:"],
    }
    app.use(Shield(csp_policy=custom_csp))

    with TestClient(app) as client:
        resp = client.get("/test")
        csp = resp.headers["Content-Security-Policy"]
        assert "default-src 'self' https://example.com" in csp
        assert "script-src 'self' 'unsafe-inline'" in csp
        assert "img-src 'self' data: https:" in csp


def test_hsts_headers_enabled():
    app = create_app()
    app.use(Shield(hsts_enabled=True))

    with TestClient(app) as client:
        resp = client.get("/test")
        hsts = resp.headers["Strict-Transport-Security"]
        assert "max-age=31536000" in hsts
        assert "includeSubDomains" in hsts


def test_hsts_headers_disabled():
    app = create_app()
    app.http_middleware = []
    app.use(Shield(hsts_enabled=False))

    with TestClient(app) as client:
        resp = client.get("/test")
        assert "Strict-Transport-Security" not in resp.headers


def test_hsts_custom_max_age():
    app = create_app()
    app.use(Shield(hsts_enabled=True, hsts_max_age=86400))

    with TestClient(app) as client:
        resp = client.get("/test")
        assert "max-age=86400" in resp.headers["Strict-Transport-Security"]


def test_hsts_preload():
    app = create_app()
    app.use(Shield(hsts_enabled=True, hsts_preload=True))

    with TestClient(app) as client:
        resp = client.get("/test")
        assert "preload" in resp.headers["Strict-Transport-Security"]


def test_xss_protection_enabled():
    app = create_app()
    app.use(Shield(xss_protection=True))

    with TestClient(app) as client:
        resp = client.get("/test")
        assert "1; mode=block" in resp.headers["X-XSS-Protection"]


def test_xss_protection_disabled():
    app = create_app()
    app.http_middleware = []
    app.use(Shield(xss_protection=False))

    with TestClient(app) as client:
        resp = client.get("/test")
        assert "X-XSS-Protection" not in resp.headers


def test_xss_protection_custom_mode():
    app = create_app()
    app.http_middleware = []
    app.use(Shield(xss_protection=True, xss_mode="sanitize"))

    with TestClient(app) as client:
        resp = client.get("/test")
        assert "1; mode=sanitize" in resp.headers["X-XSS-Protection"]


def test_frame_options_deny():
    app = create_app()
    app.use(Shield(frame_options="DENY"))

    with TestClient(app) as client:
        resp = client.get("/test")
        assert "DENY" in resp.headers["X-Frame-Options"]


def test_frame_options_sameorigin():
    app = create_app()
    app.use(Shield(frame_options="SAMEORIGIN"))

    with TestClient(app) as client:
        resp = client.get("/test")
        assert "SAMEORIGIN" in resp.headers["X-Frame-Options"]


def test_frame_options_allow_from():
    app = create_app()
    app.use(
        Shield(frame_options_allow_from="https://example.com")
    )

    with TestClient(app) as client:
        resp = client.get("/test")
        assert "ALLOW-FROM https://example.com" in resp.headers["X-Frame-Options"]


def test_content_type_options_enabled():
    app = create_app()
    app.use(Shield(content_type_options=True))

    with TestClient(app) as client:
        resp = client.get("/test")
        assert "nosniff" in resp.headers["X-Content-Type-Options"]


def test_content_type_options_disabled():
    app = create_app()
    app.http_middleware = []
    app.use(Shield(content_type_options=False))

    with TestClient(app) as client:
        resp = client.get("/test")
        assert "X-Content-Type-Options" not in resp.headers


def test_referrer_policy():
    app = create_app()
    app.use(
        Shield(referrer_policy="strict-origin-when-cross-origin")
    )

    with TestClient(app) as client:
        resp = client.get("/test")
        assert "strict-origin-when-cross-origin" in resp.headers["Referrer-Policy"]


def test_cache_control():
    app = create_app()
    app.use(Shield(cache_control="no-cache, no-store"))

    with TestClient(app) as client:
        resp = client.get("/test")
        assert "no-cache, no-store" in resp.headers["Cache-Control"]


def test_clear_site_data():
    app = create_app()
    app.use(Shield(clear_site_data=["cookies", "storage"]))

    with TestClient(app) as client:
        resp = client.get("/test")
        assert resp.headers["Clear-Site-Data"] == '"cookies", "storage"'


def test_dns_prefetch_control():
    app = create_app()
    app.use(Shield(dns_prefetch_control="off"))

    with TestClient(app) as client:
        resp = client.get("/test")
        assert "off" in resp.headers["X-DNS-Prefetch-Control"]


def test_download_options():
    app = create_app()
    app.use(Shield(download_options="noopen"))

    with TestClient(app) as client:
        resp = client.get("/test")
        assert "noopen" in resp.headers["X-Download-Options"]


def test_cross_origin_policies():
    app = create_app()
    app.use(
        Shield(
            cross_origin_opener_policy="same-origin",
            cross_origin_embedder_policy="require-corp",
            cross_origin_resource_policy="same-origin",
        )
    )

    with TestClient(app) as client:
        resp = client.get("/test")
        assert "same-origin" in resp.headers["Cross-Origin-Opener-Policy"]
        assert "require-corp" in resp.headers["Cross-Origin-Embedder-Policy"]


def test_expect_ct_enabled():
    app = create_app()
    app.use(Shield(expect_ct=True, expect_ct_max_age=86400))

    with TestClient(app) as client:
        resp = client.get("/test")
        expect_ct = resp.headers["Expect-CT"]
        assert "max-age=86400" in expect_ct


def test_expect_ct_disabled():
    app = create_app()
    app.use(Shield(expect_ct=False))

    with TestClient(app) as client:
        resp = client.get("/test")
        assert "Expect-CT" not in resp.headers


def test_permissions_policy():
    app = create_app()
    policy = {"camera": "none", "microphone": "none", "geolocation": "self"}
    app.use(Shield(permissions_policy=policy))

    with TestClient(app) as client:
        resp = client.get("/test")
        pp = resp.headers["Permissions-Policy"]
        assert "camera=none" in pp
        assert "microphone=none" in pp
        assert "geolocation=self" in pp


def test_server_header_hidden():
    app = create_app()
    app.use(Shield(hide_server=True))

    with TestClient(app) as client:
        resp = client.get("/test")
        assert "Server" not in resp.headers


def test_server_header_custom():
    app = create_app()
    app.use(
        Shield(server_header="Custom-Server/1.0", hide_server=False)
    )

    with TestClient(app) as client:
        resp = client.get("/test")
        assert resp.headers["Server"] == "Custom-Server/1.0"


def test_trusted_types_enabled():
    app = create_app()
    app.use(Shield(trusted_types=True))

    with TestClient(app) as client:
        resp = client.get("/test")
        csp = resp.headers["Content-Security-Policy"]
        assert "require-trusted-types-for 'script'" in csp


def test_trusted_types_with_policies():
    app = create_app()
    app.use(
        Shield(
            trusted_types=True, trusted_types_policies=["policy1", "policy2"]
        )
    )

    with TestClient(app) as client:
        resp = client.get("/test")
        csp = resp.headers["Content-Security-Policy"]
        assert "trusted-types policy1 policy2" in csp


def test_all_security_headers_present():
    app = create_app()
    app.use(Shield())

    with TestClient(app) as client:
        resp = client.get("/test")
        expected_headers = [
            "Strict-Transport-Security",
            "X-XSS-Protection",
            "X-Frame-Options",
            "X-Content-Type-Options",
            "Referrer-Policy",
            "X-DNS-Prefetch-Control",
            "X-Download-Options",
            "Cross-Origin-Opener-Policy",
            "Cross-Origin-Embedder-Policy",
            "Cross-Origin-Resource-Policy",
        ]
        for header in expected_headers:
            assert header in resp.headers, f"Missing: {header}"
