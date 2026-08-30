"""
Comprehensive tests for dependency injection in sillo.
Tests basic, nested, deeply nested dependencies, app-level, router-level, and nested router-level dependencies.
"""

from typing import Callable

import pytest

from sillo import SilloApp
from sillo import json
from sillo.core.dependencies import Depend
from sillo.core.http import HttpContext
from sillo.core.routing import Router
from sillo.testclient import TestClient

# ========== Basic Dependency Tests ==========


def test_basic_dependency_injection(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test basic dependency injection with a simple function"""
    app = SilloApp()

    def get_user_id():
        return "user_123"

    @app.get("/user")
    async def get_user(
        ctx: HttpContext, user_id: str = Depend(get_user_id)
    ):
        return json({"user_id": user_id})

    with test_client_factory(app) as client:
        resp = client.get("/user")
        assert resp.status_code == 200
        assert resp.json()["user_id"] == "user_123"


def test_async_dependency_injection(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test async dependency injection"""
    app = SilloApp()

    async def async_get_user_id():
        return "async_user_456"

    @app.get("/async-user")
    async def get_async_user(
        ctx: HttpContext, user_id: str = Depend(async_get_user_id)
    ):
        return json({"user_id": user_id})

    with test_client_factory(app) as client:
        resp = client.get("/async-user")
        assert resp.status_code == 200
        assert resp.json()["user_id"] == "async_user_456"


# ========== Nested Dependency Tests ==========


def test_nested_dependencies(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test nested dependencies where one dependency depends on another"""
    app = SilloApp()

    def get_user_id():
        return "user_123"

    def get_user_context(user_id: str = Depend(get_user_id)):
        return {"user_id": user_id, "context": "test_context"}

    @app.get("/nested-user")
    async def get_nested_user(
        ctx: HttpContext,
        user_context: dict = Depend(get_user_context),
    ):
        return json({"user_context": user_context})

    with test_client_factory(app) as client:
        resp = client.get("/nested-user")
        assert resp.status_code == 200
        assert resp.json()["user_context"]["user_id"] == "user_123"
        assert resp.json()["user_context"]["context"] == "test_context"


def test_async_nested_dependencies(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test nested dependencies with async functions"""
    app = SilloApp()

    async def async_get_user_id():
        return "async_user_789"

    def get_user_context(user_id: str = Depend(async_get_user_id)):
        return {"user_id": user_id, "context": "async_context"}

    @app.get("/async-nested-user")
    async def get_async_nested_user(
        ctx: HttpContext,
        user_context: dict = Depend(get_user_context),
    ):
        return json({"user_context": user_context})

    with test_client_factory(app) as client:
        resp = client.get("/async-nested-user")
        assert resp.status_code == 200
        assert resp.json()["user_context"]["user_id"] == "async_user_789"
        assert resp.json()["user_context"]["context"] == "async_context"


# ========== Deeply Nested Dependency Tests ==========


def test_deeply_nested_dependencies(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test deeply nested dependencies (3+ levels)"""
    app = SilloApp()

    def get_base_value():
        return "base_value"

    def get_middle_value(base: str = Depend(get_base_value)):
        return {"base": base, "middle": "middle_value"}

    def get_user_context(middle: dict = Depend(get_middle_value)):
        return {"user_id": "deep_user", "context": middle, "level": "deep"}

    @app.get("/deep-nested")
    async def get_deep_nested(
        ctx: HttpContext,
        user_context: dict = Depend(get_user_context),
    ):
        return json({"user_context": user_context})

    with test_client_factory(app) as client:
        resp = client.get("/deep-nested")
        assert resp.status_code == 200
        data = resp.json()["user_context"]
        assert data["user_id"] == "deep_user"
        assert data["context"]["base"] == "base_value"
        assert data["context"]["middle"] == "middle_value"
        assert data["level"] == "deep"


def test_async_deeply_nested_dependencies(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test deeply nested dependencies with mixed sync/async functions"""
    app = SilloApp()

    async def async_get_base_value():
        return "async_base"

    def get_middle_value(base: str = Depend(async_get_base_value)):
        return {"base": base, "middle": "sync_middle"}

    async def async_get_user_context(middle: dict = Depend(get_middle_value)):
        return {"user_id": "async_deep_user", "context": middle, "level": "async_deep"}

    @app.get("/async-deep-nested")
    async def get_async_deep_nested(
        ctx: HttpContext,
        user_context: dict = Depend(async_get_user_context),
    ):
        return json({"user_context": user_context})

    with test_client_factory(app) as client:
        resp = client.get("/async-deep-nested")
        assert resp.status_code == 200
        data = resp.json()["user_context"]
        assert data["user_id"] == "async_deep_user"
        assert data["context"]["base"] == "async_base"
        assert data["context"]["middle"] == "sync_middle"
        assert data["level"] == "async_deep"


# ========== Dependencies with Query Parameter Extractor Tests ==========


def test_dependency_with_query_extractor(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test dependency uses Query extractor (exercises request tunnelling through DI)."""
    from sillo import Query

    app = SilloApp()

    def get_filtered_user(limit: str = Query(default="10")):
        return {"user_id": "query_user", "limit": limit}

    @app.get("/query-user")
    async def get_query_user(
        ctx: HttpContext,
        user_data: dict = Depend(get_filtered_user),
    ):
        return json({"user_data": user_data})

    with test_client_factory(app) as client:
        resp = client.get("/query-user?limit=25")
        assert resp.status_code == 200
        data = resp.json()["user_data"]
        assert data["user_id"] == "query_user"
        assert data["limit"] == "25"


def test_dependency_with_mixed_extractor_and_dependencies(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test dependency uses both Query extractor and other DI dependencies."""
    from sillo import Query

    app = SilloApp()

    def get_user_id():
        return "mixed_user_123"

    def get_user_with_extractor(
        limit: str = Query(default="20"), user_id: str = Depend(get_user_id)
    ):
        return {
            "user_id": user_id,
            "limit": limit,
        }

    @app.get("/mixed-extractor")
    async def get_mixed_extractor(
        ctx: HttpContext,
        user_data: dict = Depend(get_user_with_extractor),
    ):
        return json({"user_data": user_data})

    with test_client_factory(app) as client:
        resp = client.get("/mixed-extractor?limit=5")
        assert resp.status_code == 200
        data = resp.json()["user_data"]
        assert data["user_id"] == "mixed_user_123"
        assert data["limit"] == "5"


# ========== App-Level Dependency Tests ==========


def test_app_level_dependencies(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test dependencies defined at the app level"""

    def get_app_config():
        return {"app_name": "test_app", "version": "1.0"}

    app = SilloApp(dependencies=[Depend(get_app_config)])

    @app.get("/app-config")
    async def get_app_config_endpoint(
        ctx: HttpContext, config: dict = Depend(get_app_config)
    ):
        return json({"config": config})

    with test_client_factory(app) as client:
        resp = client.get("/app-config")
        assert resp.status_code == 200
        assert resp.json()["config"]["app_name"] == "test_app"
        assert resp.json()["config"]["version"] == "1.0"


def test_app_level_async_dependencies(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test async dependencies at the app level"""

    async def async_get_app_config():
        return {"app_name": "async_app", "version": "2.0", "async": True}

    app = SilloApp(dependencies=[Depend(async_get_app_config)])

    @app.get("/async-app-config")
    async def get_async_app_config(
        ctx: HttpContext,
        config: dict = Depend(async_get_app_config),
    ):
        return json({"config": config})

    with test_client_factory(app) as client:
        resp = client.get("/async-app-config")
        assert resp.status_code == 200
        data = resp.json()["config"]
        assert data["app_name"] == "async_app"
        assert data["version"] == "2.0"
        assert data["async"] is True


# ========== Router-Level Dependency Tests ==========


def test_router_level_dependencies(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test dependencies defined at the router level"""
    app = SilloApp()

    def get_router_config():
        return {"router_name": "test_router", "prefix": "/api"}

    router = Router(prefix="/api", dependencies=[Depend(get_router_config)])

    @router.get("/router-config")
    async def get_router_config_endpoint(
        ctx: HttpContext, config: dict = Depend(get_router_config)
    ):
        return json({"config": config})

    app.mount_router(router)

    with test_client_factory(app) as client:
        resp = client.get("/api/router-config")
        assert resp.status_code == 200
        assert resp.json()["config"]["router_name"] == "test_router"
        assert resp.json()["config"]["prefix"] == "/api"


def test_router_level_dependencies_with_app_dependencies(
    test_client_factory: Callable[[SilloApp], TestClient],
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

    app = SilloApp(dependencies=[Depend(get_app_config)])
    router = Router(prefix="/api", dependencies=[Depend(get_router_config)])

    @router.get("/combined-config")
    async def get_combined_config_endpoint(
        ctx: HttpContext, config: dict = Depend(get_combined_config)
    ):
        return json({"config": config})

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
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test dependencies in nested routers"""
    app = SilloApp()

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
        ctx: HttpContext,
        config: dict = Depend(get_combined_nested_config),
    ):
        return json({"config": config})

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
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test dependencies in deeply nested routers (3+ levels)"""
    app = SilloApp()

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
    app = SilloApp(dependencies=[Depend(get_app_config)])

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
        ctx: HttpContext,
        config: dict = Depend(get_combined_deep_config),
    ):
        return json({"config": config})

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
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test complex scenario with app, router, and nested dependencies"""
    app = SilloApp()

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
    app = SilloApp(dependencies=[Depend(get_database_connection)])

    # API router with dependencies
    api_router = Router(prefix="/api", dependencies=[Depend(get_api_config)])

    # Auth router (nested)
    auth_router = Router(prefix="/auth", dependencies=[Depend(get_auth_service)])

    # Users router (nested under auth)
    users_router = Router(prefix="/users", dependencies=[Depend(get_user_service)])

    @users_router.get("/profile")
    async def get_user_profile(
        ctx: HttpContext,
        config: dict = Depend(get_user_handler_config),
    ):
        return json({"config": config})

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


def test_generator_dependencies(test_client_factory: Callable[[SilloApp], TestClient]):
    """Test generator-based dependencies"""
    app = SilloApp()

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
        ctx: HttpContext, db: dict = Depend(get_database_connection)
    ):
        return json({"db": db})

    with test_client_factory(app) as client:
        resp = client.get("/generator-test")
        assert resp.status_code == 200
        data = resp.json()["db"]
        assert data["db"] == "connected"
        assert len(data["pool"]["connections"]) == 1


def test_async_generator_dependencies(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test async generator-based dependencies"""
    app = SilloApp()

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
        ctx: HttpContext,
        db: dict = Depend(async_get_database_connection),
    ):
        return json({"db": db})

    with test_client_factory(app) as client:
        resp = client.get("/async-generator-test")
        assert resp.status_code == 200
        data = resp.json()["db"]
        assert data["db"] == "async_connected"
        assert len(data["pool"]["connections"]) == 1


def test_generator_dependency_cleanup(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Ensure generator dependencies run cleanup after request."""
    app = SilloApp()
    cleanup_state = {"closed": False}

    def get_resource():
        resource = {"conn": "open"}
        try:
            yield resource
        finally:
            cleanup_state["closed"] = True

    @app.get("/yield-cleanup")
    async def yield_cleanup(
        ctx: HttpContext, res: dict = Depend(get_resource)
    ):
        assert res["conn"] == "open"
        return json({"ok": True})

    with test_client_factory(app) as client:
        resp = client.get("/yield-cleanup")
        assert resp.status_code == 200
        assert cleanup_state["closed"] is True


def test_nested_yield_dependencies(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Test nested dependencies that both use yield."""
    app = SilloApp()
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
        ctx: HttpContext, inner=Depend(inner_dep)
    ):
        return json({"inner": inner})

    with test_client_factory(app) as client:
        resp = client.get("/nested-yield")
        assert resp.status_code == 200
        data = resp.json()["inner"]
        assert data["inner"] is True
        assert data["outer"]["outer"] is True
        assert flags["inner_closed"] is True
        assert flags["outer_closed"] is True


def test_async_yield_dependencies_cleanup(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Ensure async generator dependencies properly cleanup."""
    app = SilloApp()
    state = {"closed": False}

    async def async_dep():
        try:
            yield {"resource": "async_ready"}
        finally:
            state["closed"] = True

    @app.get("/async-yield-cleanup")
    async def async_yield_endpoint(
        ctx: HttpContext, data=Depend(async_dep)
    ):
        return json(data)

    with test_client_factory(app) as client:
        resp = client.get("/async-yield-cleanup")
        assert resp.status_code == 200
        assert resp.json()["resource"] == "async_ready"
        assert state["closed"] is True


def test_deep_yield_dependency_chain(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Deep chain of async+sync yield dependencies ensuring teardown order."""
    app = SilloApp()
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
        ctx: HttpContext, c=Depend(dep_c)
    ):
        return json({"result": c})

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


# ========== Depend(get_request=True) Tests ==========


def test_depend_get_request_in_handler(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Depend(get_request=True) in handler injects raw HttpContext."""
    app = SilloApp()

    @app.get("/request-injected")
    async def handler(
        ctx: HttpContext,
        injected: HttpContext = Depend(get_request=True),
    ):
        # Same object, reached two ways — that is what this asserts.
        assert injected is ctx
        return json({"path": injected.url.path, "method": injected.method})

    with test_client_factory(app) as client:
        resp = client.get("/request-injected")
        assert resp.status_code == 200
        data = resp.json()
        assert data["path"] == "/request-injected"
        assert data["method"] == "GET"


def test_depend_get_request_in_subdependency(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Depend(get_request=True) in a sub-dependency receives HttpContext."""
    app = SilloApp()

    def get_auth_info(ctx: HttpContext = Depend(get_request=True)):
        return {"token": ctx.headers.get("authorization", "none")}

    @app.get("/auth-info")
    async def handler(
        ctx: HttpContext,
        auth: dict = Depend(get_auth_info),
    ):
        return json({"auth": auth})

    with test_client_factory(app) as client:
        resp = client.get("/auth-info", headers={"Authorization": "Bearer abc123"})
        assert resp.status_code == 200
        assert resp.json()["auth"]["token"] == "Bearer abc123"


def test_depend_get_request_with_other_deps(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Depend(get_request=True) combined with other Depend deps."""
    app = SilloApp()

    def get_user_id():
        return "user_42"

    def get_full_context(
        ctx: HttpContext = Depend(get_request=True),
        user_id: str = Depend(get_user_id),
    ):
        return {
            "user_id": user_id,
            "path": ctx.url.path,
            "method": ctx.method,
        }

    @app.post("/full-context")
    async def handler(
        ctx: HttpContext,
        resolved: dict = Depend(get_full_context),
    ):
        return json({"ctx": resolved})

    with test_client_factory(app) as client:
        resp = client.post("/full-context")
        assert resp.status_code == 200
        data = resp.json()["ctx"]
        assert data["user_id"] == "user_42"
        assert data["path"] == "/full-context"
        assert data["method"] == "POST"


def test_depend_get_request_and_normal_dep_in_handler(
    test_client_factory: Callable[[SilloApp], TestClient],
):
    """Mix Depend(get_request=True) and Depend(callable) in same handler."""
    app = SilloApp()

    def get_db():
        return "db_connected"

    @app.get("/mixed-handler")
    async def handler(
        ctx: HttpContext,
        injected: HttpContext = Depend(get_request=True),
        db: str = Depend(get_db),
    ):
        return json({
            "path": injected.url.path,
            "db": db,
        })

    with test_client_factory(app) as client:
        resp = client.get("/mixed-handler")
        assert resp.status_code == 200
        data = resp.json()
        assert data["path"] == "/mixed-handler"
        assert data["db"] == "db_connected"
