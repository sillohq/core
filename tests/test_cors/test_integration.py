"""
Integration tests for CORS middleware with realistic scenarios
"""

import pytest

from sillo import SilloApp
from sillo import json, text
from sillo.core.http import HttpContext
from sillo.security.cors import CorsConfig, CORSMiddleware
from sillo.testclient import TestClient


class TestCORSIntegration:
    """Integration tests for CORS middleware with realistic scenarios"""

    def test_real_world_web_app_scenario(self):
        """Test CORS in a realistic web application scenario"""
        cors_config = CorsConfig(
            allow_origins=[
                "https://myapp.com",
                "https://admin.myapp.com",
                "http://localhost:3000",
                "http://localhost:8080",
            ],
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=[
                "Content-Type",
                "Authorization",
                "X-Requested-With",
                "X-CSRF-Token",
                "X-Custom-App-Header",
            ],
            allow_credentials=True,
            expose_headers=["X-Request-ID", "X-Response-Time"],
            max_age=86400,  # 24 hours
        )

        app = SilloApp()

        # API routes like a real web app
        @app.get("/api/users")
        async def get_users(ctx: HttpContext):
            return json({"users": []})

        @app.get("/api/users/{user_id}")
        async def get_user(ctx: HttpContext, user_id):
            return json({"user": {"id": user_id, "name": "John"}})

        @app.post("/api/users")
        async def create_user(ctx: HttpContext):
            return json({"created": True})

        @app.put("/api/users/{user_id}")
        async def update_user(ctx: HttpContext, user_id):
            return json({"updated": True})

        @app.delete("/api/users/{user_id}")
        async def delete_user(ctx: HttpContext, user_id):
            return json({"deleted": True})

        @app.get("/api/posts")
        async def get_posts(ctx: HttpContext):
            return json({"posts": []})

        app.use(CORSMiddleware(config=cors_config))

        client = TestClient(app)

        # Test various scenarios that would happen in a real app

        # Frontend making requests
        scenarios = [
            # GET requests from main app
            ("GET", "/api/users", "https://myapp.com"),
            ("GET", "/api/posts", "https://myapp.com"),
            # Admin panel requests
            ("GET", "/api/users/123", "https://admin.myapp.com"),
            ("PUT", "/api/users/123", "https://admin.myapp.com"),
            # Development environment
            ("POST", "/api/users", "http://localhost:3000"),
            ("DELETE", "/api/users/456", "http://localhost:8080"),
        ]

        for method, path, origin in scenarios:
            response = client.request(method, path, headers={"Origin": origin})

            assert response.status_code == 200
            assert response.headers["Access-Control-Allow-Origin"] == origin
            assert response.headers["Access-Control-Allow-Credentials"] == "true"
            assert (
                response.headers["Access-Control-Expose-Headers"]
                == "X-Request-ID, X-Response-Time"
            )

    def test_cors_with_multiple_middleware_layers(self):
        """Test CORS with other middleware layers"""
        cors_config = CorsConfig(
            allow_origins=["http://example.com"],
            allow_methods=["GET", "POST"],
            allow_credentials=True,
        )

        app = SilloApp()

        # Middleware execution order tracking
        execution_order = []

        async def logging_middleware(ctx: HttpContext, call_next):
            execution_order.append("logging_before")
            result = await call_next()
            execution_order.append("logging_after")
            return result

        async def auth_middleware(ctx: HttpContext, call_next):
            execution_order.append("auth_before")
            result = await call_next()
            execution_order.append("auth_after")
            return result

        async def timing_middleware(ctx: HttpContext, call_next):
            execution_order.append("timing_before")
            result = await call_next()
            result.set_header("X-Response-Time", "100ms")
            execution_order.append("timing_after")
            return result

        @app.get("/multi-middleware")
        async def multi_middleware_route(ctx: HttpContext):
            execution_order.append("handler")
            return json({"message": "OK"})

        # Add middleware in specific order
        app.use(logging_middleware)
        app.use(auth_middleware)
        app.use(CORSMiddleware(config=cors_config))
        app.use(timing_middleware)

        client = TestClient(app)

        response = client.get(
            "/multi-middleware", headers={"Origin": "http://example.com"}
        )

        assert response.status_code == 200
        assert response.json() == {"message": "OK"}
        assert response.headers["Access-Control-Allow-Origin"] == "http://example.com"
        assert response.headers["Access-Control-Allow-Credentials"] == "true"
        assert response.headers["X-Response-Time"] == "100ms"

        # CORS middleware should execute among other middleware
        assert "logging_before" in execution_order
        assert "auth_before" in execution_order
        assert "timing_before" in execution_order
        assert "handler" in execution_order

    def test_cors_with_file_uploads(self):
        """Test CORS with file upload scenarios"""
        cors_config = CorsConfig(
            allow_origins=["https://files.myapp.com"],
            allow_methods=["POST", "OPTIONS"],
            allow_headers=[
                "Content-Type",
                "Authorization",
                "X-File-Name",
                "X-File-Size",
            ],
            allow_credentials=True,
            max_age=3600,
        )

        app = SilloApp()

        @app.post("/api/upload")
        async def upload_file(ctx: HttpContext):
            return json({"uploaded": True, "filename": "test.jpg"})

        app.use(CORSMiddleware(config=cors_config))

        client = TestClient(app)

        # Test preflight for file upload
        response = client.options(
            "/api/upload",
            headers={
                "Origin": "https://files.myapp.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type, X-File-Name, X-File-Size",
            },
        )

        assert response.status_code == 201
        assert (
            response.headers["Access-Control-Allow-Origin"] == "https://files.myapp.com"
        )
        assert response.headers["Access-Control-Allow-Methods"] == "POST"
        assert (
            response.headers["Access-Control-Allow-Headers"]
            == "content-type, x-file-name, x-file-size"
        )

        # Test actual upload
        upload_response = client.post(
            "/api/upload", headers={"Origin": "https://files.myapp.com"}
        )

        assert upload_response.status_code == 200
        assert (
            upload_response.headers["Access-Control-Allow-Origin"]
            == "https://files.myapp.com"
        )
        assert upload_response.headers["Access-Control-Allow-Credentials"] == "true"

    def test_cors_with_authentication_flow(self):
        """Test CORS with authentication-protected endpoints"""
        cors_config = CorsConfig(
            allow_origins=["https://dashboard.myapp.com"],
            allow_methods=["GET", "POST", "DELETE"],
            allow_headers=["Authorization", "Content-Type"],
            allow_credentials=True,
        )

        app = SilloApp()

        @app.post("/api/login")
        async def login(ctx: HttpContext):
            return json({"token": "abc123", "user": "john"})

        @app.get("/api/profile")
        async def get_profile(ctx: HttpContext):
            # Simulate auth check
            auth_header = ctx.headers.get("Authorization")
            if not auth_header:
                return json({"error": "Unauthorized"}, status_code=401)

            return json({"user": "john", "email": "john@example.com"})

        @app.delete("/api/account")
        async def delete_account(ctx: HttpContext):
            # Simulate auth check
            auth_header = ctx.headers.get("Authorization")
            if not auth_header:
                return json({"error": "Unauthorized"}, status_code=401)

            return json({"deleted": True})

        app.use(CORSMiddleware(config=cors_config))

        client = TestClient(app)

        # Test login (public endpoint)
        login_response = client.post(
            "/api/login", headers={"Origin": "https://dashboard.myapp.com"}
        )
        assert login_response.status_code == 200
        assert (
            login_response.headers["Access-Control-Allow-Origin"]
            == "https://dashboard.myapp.com"
        )

        # Test authenticated request
        profile_response = client.get(
            "/api/profile",
            headers={
                "Origin": "https://dashboard.myapp.com",
                "Authorization": "Bearer token123",
            },
        )
        assert profile_response.status_code == 200
        assert (
            profile_response.headers["Access-Control-Allow-Origin"]
            == "https://dashboard.myapp.com"
        )

        # Test preflight for delete operation
        delete_preflight = client.options(
            "/api/account",
            headers={
                "Origin": "https://dashboard.myapp.com",
                "Access-Control-Request-Method": "DELETE",
                "Authorization": "Bearer token123",
            },
        )
        assert delete_preflight.status_code == 201
        assert delete_preflight.headers["Access-Control-Allow-Methods"] == "DELETE"

    def test_cors_with_different_content_types(self):
        """Test CORS with various content types"""
        cors_config = CorsConfig(
            allow_origins=["https://api-client.com"],
            allow_methods=["POST", "PUT"],
            allow_headers=["Content-Type", "Authorization"],
            allow_credentials=True,
        )

        app = SilloApp()

        @app.post("/api/json")
        async def json_endpoint(ctx: HttpContext):
            return json({"received": "json"})

        @app.post("/api/text")
        async def text_endpoint(ctx: HttpContext):
            return text("text response")

        app.use(CORSMiddleware(config=cors_config))

        client = TestClient(app)

        # Test JSON request
        json_response = client.post(
            "/api/json",
            headers={
                "Origin": "https://api-client.com",
                "Content-Type": "application/json",
            },
        )
        assert json_response.status_code == 200
        assert (
            json_response.headers["Access-Control-Allow-Origin"]
            == "https://api-client.com"
        )

        # Test text request
        text_response = client.post(
            "/api/text",
            headers={"Origin": "https://api-client.com", "Content-Type": "text/plain"},
        )
        assert text_response.status_code == 200
        assert (
            text_response.headers["Access-Control-Allow-Origin"]
            == "https://api-client.com"
        )

    def test_cors_with_subdomain_wildcard(self):
        """Test CORS with subdomain wildcard patterns"""
        cors_config = CorsConfig(
            allow_origin_regex=r"https://.*\.myapp\.com",
            allow_methods=["GET", "POST"],
            allow_credentials=True,
            expose_headers=["X-Subdomain"],
        )

        app = SilloApp()

        @app.get("/api/data")
        async def subdomain_data(ctx: HttpContext):
            origin = ctx.origin
            response = json({"data": "test"})
            if origin:
                subdomain = origin.split(".")[0].replace("https://", "")
                response.set_header("X-Subdomain", subdomain)
            return response

        app.use(CORSMiddleware(config=cors_config))

        client = TestClient(app)

        # Test different subdomains
        subdomains = ["api", "admin", "app", "mobile"]

        for subdomain in subdomains:
            origin = f"https://{subdomain}.myapp.com"
            response = client.get("/api/data", headers={"Origin": origin})

            assert response.status_code == 200
            assert response.headers["Access-Control-Allow-Origin"] == origin
            assert response.headers["X-Subdomain"] == subdomain

    def test_cors_performance_with_many_origins(self):
        """Test CORS performance with many allowed origins"""
        # Create config with many origins
        many_origins = [f"https://app{i}.example.com" for i in range(100)]
        many_origins.extend([f"http://localhost:{port}" for port in range(3000, 3100)])

        cors_config = CorsConfig(
            allow_origins=many_origins,
            allow_methods=["GET"],
            allow_credentials=False,
        )

        app = SilloApp()

        @app.get("/performance-test")
        async def performance_route(ctx: HttpContext):
            return json({"message": "OK"})

        app.use(CORSMiddleware(config=cors_config))

        client = TestClient(app)

        # Test with one of the allowed origins
        test_origin = "https://app50.example.com"
        response = client.get("/performance-test", headers={"Origin": test_origin})

        assert response.status_code == 200
        assert response.headers["Access-Control-Allow-Origin"] == test_origin

    def test_cors_with_request_id_tracking(self):
        """Test CORS with request ID tracking middleware"""
        cors_config = CorsConfig(
            allow_origins=["https://tracking.myapp.com"],
            allow_methods=["GET", "POST"],
            allow_credentials=True,
            expose_headers=["X-Request-ID", "X-Trace-ID"],
        )

        app = SilloApp()

        # HttpContext ID middleware
        async def request_id_middleware(
            ctx: HttpContext, call_next
        ):
            import uuid

            request_id = str(uuid.uuid4())
            ctx.scope["request_id"] = request_id

            result = await call_next()

            result.set_header("X-Request-ID", request_id)
            result.set_header("X-Trace-ID", f"trace-{request_id[:8]}")

            return result

        @app.get("/tracked-request")
        async def tracked_route(ctx: HttpContext):
            request_id = ctx.scope.get("request_id")
            return json({"request_id": request_id, "message": "OK"})

        # Add middleware
        app.use(request_id_middleware)
        app.use(CORSMiddleware(config=cors_config))

        client = TestClient(app)

        response = client.get(
            "/tracked-request", headers={"Origin": "https://tracking.myapp.com"}
        )

        assert response.status_code == 200
        assert (
            response.headers["Access-Control-Allow-Origin"]
            == "https://tracking.myapp.com"
        )
        assert response.headers["Access-Control-Allow-Credentials"] == "true"
        assert (
            response.headers["Access-Control-Expose-Headers"]
            == "X-Request-ID, X-Trace-ID"
        )

        # Verify request ID is accessible
        request_id_header = response.headers["X-Request-ID"]
        request_id_body = response.json()["request_id"]
        assert request_id_header == request_id_body
        assert response.headers["X-Trace-ID"] == f"trace-{request_id_header[:8]}"
