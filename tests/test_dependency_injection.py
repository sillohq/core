"""
Comprehensive tests for dependency injection in Nexios.
Tests basic, nested, deeply nested dependencies, with context, app-level, router-level, and nested router-level dependencies.
"""

from typing import Callable

import pytest

from nexios import NexiosApp
from nexios.dependencies import Context, Depend
from nexios.http import Request, Response
from nexios.routing import Router
from nexios.testclient import TestClient

# ========== Basic Dependency Tests ==========


def test_basic_dependency_injection(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test basic dependency injection with a simple function"""
    app = NexiosApp()

    def get_user_id():
        return "user_123"

    @app.get("/user")
    async def get_user(
        request: Request, response: Response, user_id: str = Depend(get_user_id)
    ):
        return response.json({"user_id": user_id})

    with test_client_factory(app) as client:
        resp = client.get("/user")
        assert resp.status_code == 200
        assert resp.json()["user_id"] == "user_123"


def test_async_dependency_injection(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test async dependency injection"""
    app = NexiosApp()

    async def async_get_user_id():
        return "async_user_456"

    @app.get("/async-user")
    async def get_async_user(
        request: Request, response: Response, user_id: str = Depend(async_get_user_id)
    ):
        return response.json({"user_id": user_id})

    with test_client_factory(app) as client:
        resp = client.get("/async-user")
        assert resp.status_code == 200
        assert resp.json()["user_id"] == "async_user_456"


# ========== Nested Dependency Tests ==========


def test_nested_dependencies(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test nested dependencies where one dependency depends on another"""
    app = NexiosApp()

    def get_user_id():
        return "user_123"

    def get_user_context(user_id: str = Depend(get_user_id)):
        return {"user_id": user_id, "context": "test_context"}

    @app.get("/nested-user")
    async def get_nested_user(
        request: Request,
        response: Response,
        user_context: dict = Depend(get_user_context),
    ):
        return response.json({"user_context": user_context})

    with test_client_factory(app) as client:
        resp = client.get("/nested-user")
        assert resp.status_code == 200
        assert resp.json()["user_context"]["user_id"] == "user_123"
        assert resp.json()["user_context"]["context"] == "test_context"


def test_async_nested_dependencies(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test nested dependencies with async functions"""
    app = NexiosApp()

    async def async_get_user_id():
        return "async_user_789"

    def get_user_context(user_id: str = Depend(async_get_user_id)):
        return {"user_id": user_id, "context": "async_context"}

    @app.get("/async-nested-user")
    async def get_async_nested_user(
        request: Request,
        response: Response,
        user_context: dict = Depend(get_user_context),
    ):
        return response.json({"user_context": user_context})

    with test_client_factory(app) as client:
        resp = client.get("/async-nested-user")
        assert resp.status_code == 200
        assert resp.json()["user_context"]["user_id"] == "async_user_789"
        assert resp.json()["user_context"]["context"] == "async_context"


# ========== Deeply Nested Dependency Tests ==========


def test_deeply_nested_dependencies(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test deeply nested dependencies (3+ levels)"""
    app = NexiosApp()

    def get_base_value():
        return "base_value"

    def get_middle_value(base: str = Depend(get_base_value)):
        return {"base": base, "middle": "middle_value"}

    def get_user_context(middle: dict = Depend(get_middle_value)):
        return {"user_id": "deep_user", "context": middle, "level": "deep"}

    @app.get("/deep-nested")
    async def get_deep_nested(
        request: Request,
        response: Response,
        user_context: dict = Depend(get_user_context),
    ):
        return response.json({"user_context": user_context})

    with test_client_factory(app) as client:
        resp = client.get("/deep-nested")
        assert resp.status_code == 200
        data = resp.json()["user_context"]
        assert data["user_id"] == "deep_user"
        assert data["context"]["base"] == "base_value"
        assert data["context"]["middle"] == "middle_value"
        assert data["level"] == "deep"


def test_async_deeply_nested_dependencies(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test deeply nested dependencies with mixed sync/async functions"""
    app = NexiosApp()

    async def async_get_base_value():
        return "async_base"

    def get_middle_value(base: str = Depend(async_get_base_value)):
        return {"base": base, "middle": "sync_middle"}

    async def async_get_user_context(middle: dict = Depend(get_middle_value)):
        return {"user_id": "async_deep_user", "context": middle, "level": "async_deep"}

    @app.get("/async-deep-nested")
    async def get_async_deep_nested(
        request: Request,
        response: Response,
        user_context: dict = Depend(async_get_user_context),
    ):
        return response.json({"user_context": user_context})

    with test_client_factory(app) as client:
        resp = client.get("/async-deep-nested")
        assert resp.status_code == 200
        data = resp.json()["user_context"]
        assert data["user_id"] == "async_deep_user"
        assert data["context"]["base"] == "async_base"
        assert data["context"]["middle"] == "sync_middle"
        assert data["level"] == "async_deep"


# ========== Dependencies with Context Tests ==========


def test_dependency_with_context(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test dependency that uses Context object"""
    app = NexiosApp()

    def get_user_from_context(ctx: Context = Context()):
        return {
            "user_id": "context_user",
            "request_path": ctx.request.url.path if ctx.request else None,
        }

    @app.get("/context-user")
    async def get_context_user(
        request: Request,
        response: Response,
        user_data: dict = Depend(get_user_from_context),
    ):
        return response.json({"user_data": user_data})

    with test_client_factory(app) as client:
        resp = client.get("/context-user")
        assert resp.status_code == 200
        data = resp.json()["user_data"]
        assert data["user_id"] == "context_user"
        assert data["request_path"] == "/context-user"


def test_dependency_with_mixed_context_and_dependencies(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test dependency that uses both Context and other dependencies"""
    app = NexiosApp()

    def get_user_id():
        return "mixed_user_123"

    def get_user_with_context(
        ctx: Context = Context(), user_id: str = Depend(get_user_id)
    ):
        return {
            "user_id": user_id,
            "request_method": ctx.request.method if ctx.request else None,
            "context_available": ctx is not None,
        }

    @app.post("/mixed-context")
    async def get_mixed_context(
        request: Request,
        response: Response,
        user_data: dict = Depend(get_user_with_context),
    ):
        return response.json({"user_data": user_data})

    with test_client_factory(app) as client:
        resp = client.post("/mixed-context")
        assert resp.status_code == 200
        data = resp.json()["user_data"]
        assert data["user_id"] == "mixed_user_123"
        assert data["request_method"] == "POST"
        assert data["context_available"] is True


# ========== App-Level Dependency Tests ==========


def test_app_level_dependencies(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test dependencies defined at the app level"""

    def get_app_config():
        return {"app_name": "test_app", "version": "1.0"}

    app = NexiosApp(dependencies=[Depend(get_app_config)])

    @app.get("/app-config")
    async def get_app_config_endpoint(
        request: Request, response: Response, config: dict = Depend(get_app_config)
    ):
        return response.json({"config": config})

    with test_client_factory(app) as client:
        resp = client.get("/app-config")
        assert resp.status_code == 200
        assert resp.json()["config"]["app_name"] == "test_app"
        assert resp.json()["config"]["version"] == "1.0"


def test_app_level_async_dependencies(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test async dependencies at the app level"""

    async def async_get_app_config():
        return {"app_name": "async_app", "version": "2.0", "async": True}

    app = NexiosApp(dependencies=[Depend(async_get_app_config)])

    @app.get("/async-app-config")
    async def get_async_app_config(
        request: Request,
        response: Response,
        config: dict = Depend(async_get_app_config),
    ):
        return response.json({"config": config})

    with test_client_factory(app) as client:
        resp = client.get("/async-app-config")
        assert resp.status_code == 200
        data = resp.json()["config"]
        assert data["app_name"] == "async_app"
        assert data["version"] == "2.0"
        assert data["async"] is True


# ========== Router-Level Dependency Tests ==========


def test_router_level_dependencies(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test dependencies defined at the router level"""
    app = NexiosApp()

    def get_router_config():
        return {"router_name": "test_router", "prefix": "/api"}

    router = Router(prefix="/api", dependencies=[Depend(get_router_config)])

    @router.get("/router-config")
    async def get_router_config_endpoint(
        request: Request, response: Response, config: dict = Depend(get_router_config)
    ):
        return response.json({"config": config})

    app.mount_router(router)

    with test_client_factory(app) as client:
        resp = client.get("/api/router-config")
        assert resp.status_code == 200
        assert resp.json()["config"]["router_name"] == "test_router"
        assert resp.json()["config"]["prefix"] == "/api"


def test_router_level_dependencies_with_app_dependencies(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test router-level dependencies combined with app-level dependencies"""

    def get_app_config():
        return {"app_name": "main_app"}

    def get_router_config():
        return {"router_name": "api_router"}

    def get_combined_config(
        app_config: dict = Depend(get_app_config),
        router_config: dict = Depend(get_router_config),
    ):
        return {**app_config, **router_config, "combined": True}

    app = NexiosApp(dependencies=[Depend(get_app_config)])
    router = Router(prefix="/api", dependencies=[Depend(get_router_config)])

    @router.get("/combined-config")
    async def get_combined_config_endpoint(
        request: Request, response: Response, config: dict = Depend(get_combined_config)
    ):
        return response.json({"config": config})

    app.mount_router(router)

    with test_client_factory(app) as client:
        resp = client.get("/api/combined-config")
        assert resp.status_code == 200
        data = resp.json()["config"]
        assert data["app_name"] == "main_app"
        assert data["router_name"] == "api_router"
        assert data["combined"] is True


# ========== Nested Router-Level Dependency Tests ==========


def test_nested_router_dependencies(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test dependencies in nested routers"""
    app = NexiosApp()

    def get_api_config():
        return {"api_version": "v1"}

    def get_users_config():
        return {"users_module": "active"}

    def get_combined_nested_config(
        api_config: dict = Depend(get_api_config),
        users_config: dict = Depend(get_users_config),
    ):
        return {**api_config, **users_config, "nested": True}

    # Main API router
    api_router = Router(prefix="/api", dependencies=[Depend(get_api_config)])

    # Users sub-router
    users_router = Router(prefix="/users", dependencies=[Depend(get_users_config)])

    @users_router.get("/config")
    async def get_nested_config(
        request: Request,
        response: Response,
        config: dict = Depend(get_combined_nested_config),
    ):
        return response.json({"config": config})

    api_router.mount_router(users_router)
    app.mount_router(api_router)

    with test_client_factory(app) as client:
        resp = client.get("/api/users/config")
        assert resp.status_code == 200
        data = resp.json()["config"]
        assert data["api_version"] == "v1"
        assert data["users_module"] == "active"
        assert data["nested"] is True


def test_deeply_nested_router_dependencies(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test dependencies in deeply nested routers (3+ levels)"""
    app = NexiosApp()

    def get_app_config():
        return {"app": "main"}

    def get_api_config():
        return {"api": "v1"}

    def get_v1_config():
        return {"version": "1.0"}

    def get_users_config():
        return {"users": "module"}

    def get_profiles_config():
        return {"profiles": "submodule"}

    def get_combined_deep_config(
        app_config: dict = Depend(get_app_config),
        api_config: dict = Depend(get_api_config),
        v1_config: dict = Depend(get_v1_config),
        users_config: dict = Depend(get_users_config),
        profiles_config: dict = Depend(get_profiles_config),
    ):
        return {
            **app_config,
            **api_config,
            **v1_config,
            **users_config,
            **profiles_config,
            "depth": "deep",
        }

    # App level
    app = NexiosApp(dependencies=[Depend(get_app_config)])

    # API router
    api_router = Router(prefix="/api", dependencies=[Depend(get_api_config)])

    # V1 router
    v1_router = Router(prefix="/v1", dependencies=[Depend(get_v1_config)])

    # Users router
    users_router = Router(prefix="/users", dependencies=[Depend(get_users_config)])

    # Profiles router (deepest level)
    profiles_router = Router(
        prefix="/profiles", dependencies=[Depend(get_profiles_config)]
    )

    @profiles_router.get("/deep-config")
    async def get_deep_config(
        request: Request,
        response: Response,
        config: dict = Depend(get_combined_deep_config),
    ):
        return response.json({"config": config})

    users_router.mount_router(profiles_router)
    v1_router.mount_router(users_router)
    api_router.mount_router(v1_router)
    app.mount_router(api_router)

    with test_client_factory(app) as client:
        resp = client.get("/api/v1/users/profiles/deep-config")
        assert resp.status_code == 200
        data = resp.json()["config"]
        assert data["app"] == "main"
        assert data["api"] == "v1"
        assert data["version"] == "1.0"
        assert data["users"] == "module"
        assert data["profiles"] == "submodule"
        assert data["depth"] == "deep"


# ========== Complex Mixed Scenario Tests ==========


def test_mixed_app_router_nested_dependencies(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test complex scenario with app, router, and nested dependencies"""
    app = NexiosApp()

    def get_database_connection():
        return {"db": "connected", "pool": "active"}

    def get_user_service(db: dict = Depend(get_database_connection)):
        return {"service": "user_service", "db": db}

    def get_auth_service():
        return {"auth": "enabled", "method": "jwt"}

    def get_api_config(
        db: dict = Depend(get_database_connection),
        user_service: dict = Depend(get_user_service),
    ):
        return {"api": "v1", "db": db, "user_service": user_service}

    def get_user_handler_config(
        auth: dict = Depend(get_auth_service), api: dict = Depend(get_api_config)
    ):
        return {"handler": "user_handler", "auth": auth, "api": api}

    # App-level dependencies
    app = NexiosApp(dependencies=[Depend(get_database_connection)])

    # API router with dependencies
    api_router = Router(prefix="/api", dependencies=[Depend(get_api_config)])

    # Auth router (nested)
    auth_router = Router(prefix="/auth", dependencies=[Depend(get_auth_service)])

    # Users router (nested under auth)
    users_router = Router(prefix="/users", dependencies=[Depend(get_user_service)])

    @users_router.get("/profile")
    async def get_user_profile(
        request: Request,
        response: Response,
        config: dict = Depend(get_user_handler_config),
    ):
        return response.json({"config": config})

    auth_router.mount_router(users_router)
    api_router.mount_router(auth_router)
    app.mount_router(api_router)

    with test_client_factory(app) as client:
        resp = client.get("/api/auth/users/profile")
        assert resp.status_code == 200
        data = resp.json()["config"]
        assert data["handler"] == "user_handler"
        assert data["auth"]["auth"] == "enabled"
        assert data["api"]["api"] == "v1"


def test_generator_dependencies(test_client_factory: Callable[[NexiosApp], TestClient]):
    """Test generator-based dependencies"""
    app = NexiosApp()

    def get_database_connection():
        db_pool = {"connections": []}
        try:
            # Simulate resource allocation
            db_pool["connections"].append("connection_1")
            yield {"db": "connected", "pool": db_pool}
        finally:
            # Cleanup
            db_pool["connections"].pop()

    @app.get("/generator-test")
    async def test_generator(
        request: Request, response: Response, db: dict = Depend(get_database_connection)
    ):
        return response.json({"db": db})

    with test_client_factory(app) as client:
        resp = client.get("/generator-test")
        assert resp.status_code == 200
        data = resp.json()["db"]
        assert data["db"] == "connected"
        assert len(data["pool"]["connections"]) == 1


def test_async_generator_dependencies(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test async generator-based dependencies"""
    app = NexiosApp()

    async def async_get_database_connection():
        db_pool = {"connections": []}
        try:
            # Simulate async resource allocation
            db_pool["connections"].append("async_connection_1")
            yield {"db": "async_connected", "pool": db_pool}
        finally:
            # Cleanup
            db_pool["connections"].pop()

    @app.get("/async-generator-test")
    async def test_async_generator(
        request: Request,
        response: Response,
        db: dict = Depend(async_get_database_connection),
    ):
        return response.json({"db": db})

    with test_client_factory(app) as client:
        resp = client.get("/async-generator-test")
        assert resp.status_code == 200
        data = resp.json()["db"]
        assert data["db"] == "async_connected"
        assert len(data["pool"]["connections"]) == 1


def test_generator_dependency_cleanup(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Ensure generator dependencies run cleanup after request."""
    app = NexiosApp()
    cleanup_state = {"closed": False}

    def get_resource():
        resource = {"conn": "open"}
        try:
            yield resource
        finally:
            cleanup_state["closed"] = True

    @app.get("/yield-cleanup")
    async def yield_cleanup(
        request: Request, response: Response, res: dict = Depend(get_resource)
    ):
        assert res["conn"] == "open"
        return response.json({"ok": True})

    with test_client_factory(app) as client:
        resp = client.get("/yield-cleanup")
        assert resp.status_code == 200
        assert cleanup_state["closed"] is True


def test_nested_yield_dependencies(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Test nested dependencies that both use yield."""
    app = NexiosApp()
    flags = {"inner_closed": False, "outer_closed": False}

    def outer_dep():
        try:
            yield {"outer": True}
        finally:
            flags["outer_closed"] = True

    def inner_dep(outer=Depend(outer_dep)):
        try:
            yield {"inner": True, "outer": outer}
        finally:
            flags["inner_closed"] = True

    @app.get("/nested-yield")
    async def nested_yield(
        request: Request, response: Response, inner=Depend(inner_dep)
    ):
        return response.json({"inner": inner})

    with test_client_factory(app) as client:
        resp = client.get("/nested-yield")
        assert resp.status_code == 200
        data = resp.json()["inner"]
        assert data["inner"] is True
        assert data["outer"]["outer"] is True
        assert flags["inner_closed"] is True
        assert flags["outer_closed"] is True


def test_async_yield_dependencies_cleanup(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Ensure async generator dependencies properly cleanup."""
    app = NexiosApp()
    state = {"closed": False}

    async def async_dep():
        try:
            yield {"resource": "async_ready"}
        finally:
            state["closed"] = True

    @app.get("/async-yield-cleanup")
    async def async_yield_endpoint(
        request: Request, response: Response, data=Depend(async_dep)
    ):
        return response.json(data)

    with test_client_factory(app) as client:
        resp = client.get("/async-yield-cleanup")
        assert resp.status_code == 200
        assert resp.json()["resource"] == "async_ready"
        assert state["closed"] is True


def test_deep_yield_dependency_chain(
    test_client_factory: Callable[[NexiosApp], TestClient],
):
    """Deep chain of async+sync yield dependencies ensuring teardown order."""
    app = NexiosApp()
    order = []

    def dep_a():
        order.append("setup_a")
        try:
            yield "A"
        finally:
            order.append("cleanup_a")

    async def dep_b(a=Depend(dep_a)):
        order.append("setup_b")
        try:
            yield f"B({a})"
        finally:
            order.append("cleanup_b")

    def dep_c(b=Depend(dep_b)):
        order.append("setup_c")
        try:
            yield f"C({b})"
        finally:
            order.append("cleanup_c")

    @app.get("/deep-yield")
    async def deep_yield_endpoint(
        request: Request, response: Response, c=Depend(dep_c)
    ):
        return response.json({"result": c})

    with test_client_factory(app) as client:
        resp = client.get("/deep-yield")
        assert resp.status_code == 200
        assert resp.json()["result"].startswith("C(B(A))")
        # Verify cleanup runs in reverse
        print("order", order)
        assert order == [
            "setup_a",
            "setup_b",
            "setup_c",
            "cleanup_c",
            "cleanup_b",
            "cleanup_a",
        ]
