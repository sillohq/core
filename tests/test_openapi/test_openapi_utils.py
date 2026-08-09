"""
``sillo.openapi.utils.get_openapi``: flatten a nested route tree to a list
of ``Route`` objects.

Routers hold routes, groups hold routers or routes, and groups nest — so the
recursion is what matters here, along with the tolerance for objects that
carry a ``routes`` attribute without being any of the known types.
"""

from sillo.core.routing import Route, Router
from sillo.core.routing.grouping import Group
from sillo.openapi.utils import get_openapi


async def handler(request, response):
    return response.json({})


def _route(path: str) -> Route:
    return Route(path, handler, methods=["get"])


def _paths(routes):
    return [r.raw_path for r in routes]


# ── leaves ───────────────────────────────────────────────────────────────


def test_a_bare_route_is_returned_as_a_single_item():
    route = _route("/users")
    assert get_openapi(route) == [route]


def test_an_unrecognised_object_gives_an_empty_list():
    assert get_openapi(object()) == []


def test_none_gives_an_empty_list():
    assert get_openapi(None) == []


def test_a_string_gives_an_empty_list():
    """Anything without a ``routes`` attribute falls through to empty rather
    than raising."""
    assert get_openapi("not-a-route") == []


# ── routers ──────────────────────────────────────────────────────────────


def test_a_router_yields_its_routes():
    router = Router(routes=[_route("/a"), _route("/b")])
    assert _paths(get_openapi(router)) == ["/a", "/b"]


def test_an_empty_router_yields_nothing():
    assert get_openapi(Router(routes=[])) == []


def test_a_router_inside_a_router_is_flattened():
    inner = Router(routes=[_route("/inner")])
    outer = Router(routes=[_route("/outer"), inner])
    assert set(_paths(get_openapi(outer))) == {"/outer", "/inner"}


def test_the_result_items_are_all_routes():
    router = Router(routes=[_route("/a"), Router(routes=[_route("/b")])])
    assert all(isinstance(r, Route) for r in get_openapi(router))


# ── groups ───────────────────────────────────────────────────────────────


def test_a_group_yields_the_routes_of_its_router():
    group = Group("/api", routes=[_route("/users"), _route("/posts")])
    assert set(_paths(get_openapi(group))) == {"/users", "/posts"}


def test_a_group_wrapping_an_explicit_router():
    router = Router(routes=[_route("/users")])
    group = Group("/api", app=router)
    assert _paths(get_openapi(group)) == ["/users"]


def test_an_empty_group_yields_nothing():
    assert get_openapi(Group("/api", routes=[])) == []


def test_nested_groups_are_flattened():
    inner = Group("/v1", routes=[_route("/users")])
    outer = Group("/api", routes=[inner, _route("/health")])
    assert set(_paths(get_openapi(outer))) == {"/users", "/health"}


def test_a_group_mounted_on_a_non_router_app_yields_nothing():
    """Mounting a raw ASGI app gives nothing to introspect, and that must be
    survivable rather than fatal."""

    async def raw_app(scope, receive, send):
        pass

    assert get_openapi(Group("/mounted", app=raw_app)) == []


# ── duck-typed containers ────────────────────────────────────────────────


def test_any_object_with_a_routes_attribute_is_walked():
    class Container:
        def __init__(self, routes):
            self.routes = routes

    container = Container([_route("/a"), _route("/b")])
    assert _paths(get_openapi(container)) == ["/a", "/b"]


def test_a_duck_typed_container_recurses():
    class Container:
        def __init__(self, routes):
            self.routes = routes

    nested = Container([Router(routes=[_route("/deep")])])
    assert _paths(get_openapi(nested)) == ["/deep"]


def test_a_container_with_an_empty_routes_attribute():
    class Container:
        routes = []

    assert get_openapi(Container()) == []


# ── application integration ──────────────────────────────────────────────


def test_flattening_a_real_application_router():
    from sillo import SilloApp
    from sillo.core.http import Request, Response

    app = SilloApp()

    @app.get("/users")
    async def users(request: Request, response: Response):
        return response.json([])

    @app.post("/users")
    async def create(request: Request, response: Response):
        return response.json({})

    assert "/users" in _paths(get_openapi(app.router))


def test_duplicate_paths_are_all_reported():
    """Flattening does not deduplicate — two routes on one path are two
    operations in the spec."""
    router = Router(routes=[_route("/same"), _route("/same")])
    assert len(get_openapi(router)) == 2
