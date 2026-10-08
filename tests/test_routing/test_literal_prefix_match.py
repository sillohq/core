"""The literal-prefix pre-check may only skip the regex for paths it could not match.

``Route.match`` rejects a path that does not start with the route's literal
prefix before running the compiled regex. That is sound because the regex
escapes literal text, so these tests hold it to the one thing that matters:
for every route shape and every path, the result equals what the regex alone
gives, including the awkward cases (regex metacharacters in the path, a
trailing newline that ``$`` tolerates, parameters at the start, mounts).
"""

from __future__ import annotations

import random

import pytest

from sillo import HttpContext, SilloApp
from sillo.core.routing.router import MatchStatus, Route
from sillo.core.routing.websocket import WebsocketRoute
from sillo.route_builder import RouteBuilder
from sillo.testclient import TestClient

TEMPLATES = [
    "/",
    "/health",
    "/users",
    "/users/{user_id:int}",
    "/users/{user_id}",
    "/users/{user_id:int}/posts/{post_id:int}",
    "/files/{path:path}",
    "/{slug}",
    "/{a}/{b}",
    "/v1.0/items",
    "/a.b/{x}",
    "/price+tax/{n:int}",
    "/(group)/x",
    "/q?x/{n}",
    "/café/{name}",
    "/with space/{x}",
    "/a{b",
    "/trailing/",
    "/{id:int}/detail",
]

PATHS = [
    "/",
    "",
    "/health",
    "/health/",
    "/healthz",
    "/users",
    "/users/",
    "/users/1",
    "/users/abc",
    "/users/1/posts/2",
    "/users/1/posts/x",
    "/files/a/b/c.txt",
    "/files/",
    "/files",
    "/anything",
    "/x/y",
    "/v1.0/items",
    "/v1x0/items",
    "/a.b/z",
    "/aXb/z",
    "/price+tax/3",
    "/priceetax/3",
    "/(group)/x",
    "/group/x",
    "/q?x/1",
    "/qx/1",
    "/café/bob",
    "/cafe/bob",
    "/with space/1",
    "/with%20space/1",
    "/a{b",
    "/a",
    "/trailing/",
    "/trailing",
    "/42/detail",
    "/health\n",
    "/users/1\n",
    "/users\n",
    "/\n",
    "/USERS",
    "/Users/1",
]


def regex_only(route: Route, path: str):
    """What matching did before the pre-check: the regex, nothing in front."""
    match = route.pattern.match(path)
    if not match:
        return MatchStatus.NONE, {}
    params = match.groupdict()
    for key, value in params.items():
        params[key] = route.route_info.convertor[key].convert(value)
    return (
        MatchStatus.FULL if "GET" in route.methods else MatchStatus.PARTIAL,
        params,
    )


async def handler(ctx: HttpContext):
    return "ok"


def scope_for(path: str, method: str = "GET"):
    return {
        "type": "http",
        "method": method,
        "path": path,
        "root_path": "",
        "headers": [],
    }


@pytest.mark.parametrize("template", TEMPLATES)
def test_http_route_matches_exactly_as_the_regex_alone_would(template):
    route = Route(template, handler, methods=["GET"])
    for path in PATHS:
        assert route.match(scope_for(path)) == regex_only(route, path), (template, path)


@pytest.mark.parametrize("template", TEMPLATES)
def test_method_mismatch_is_still_a_partial_match(template):
    route = Route(template, handler, methods=["GET"])
    for path in PATHS:
        got = route.match(scope_for(path, "DELETE"))
        want = regex_only(route, path)
        if want[0] == MatchStatus.FULL:
            want = (MatchStatus.PARTIAL, want[1])
        assert got == want, (template, path)


def test_the_prefix_is_exactly_the_text_before_the_first_parameter():
    prefix = lambda p: RouteBuilder.create_pattern(p).literal_prefix
    assert prefix("/users/{id:int}") == "/users/"
    assert prefix("/{slug}") == "/"
    assert prefix("/health") == "/health"
    assert prefix("/a.b/{x}") == "/a.b/"
    assert prefix("/files/{path:path}") == "/files/"


def test_randomised_paths_never_disagree():
    rng = random.Random(8102026)
    alphabet = [
        "/",
        "users",
        "1",
        "x",
        ".",
        "a",
        "files",
        "\n",
        "é",
        "%20",
        "-",
        "42",
        "health",
    ]
    routes = [Route(t, handler, methods=["GET"]) for t in TEMPLATES]
    for _ in range(4000):
        path = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 7)))
        for route in routes:
            assert route.match(scope_for(path)) == regex_only(route, path), (
                route.raw_path,
                path,
            )


def test_websocket_routes_use_the_same_rule():
    for template in TEMPLATES:
        route = WebsocketRoute(template, handler)
        for path in PATHS:
            scope = {"type": "websocket", "path": path, "root_path": "", "headers": []}
            got = route.match(scope)
            m = route.pattern.match(path)
            if m:
                params = m.groupdict()
                for key, value in params.items():
                    params[key] = route.route_info.convertor[key].convert(value)
                assert got == (MatchStatus.FULL, params), (template, path)
            else:
                assert got == (MatchStatus.NONE, {}), (template, path)


def test_an_app_with_many_routes_still_picks_the_first_match_in_order():
    app = SilloApp(debug=False)

    @app.get("/items/special")
    async def special(ctx: HttpContext):
        return {"which": "special"}

    @app.get("/items/{name}")
    async def by_name(ctx: HttpContext, name: str):
        return {"which": "param", "name": name}

    for i in range(60):
        app.get(f"/filler/{i}/x")(handler)

    @app.get("/{anything:path}")
    async def catch_all(ctx: HttpContext, anything: str):
        return {"which": "catch-all", "path": anything}

    client = TestClient(app)
    assert client.get("/items/special").json() == {"which": "special"}
    assert client.get("/items/other").json() == {"which": "param", "name": "other"}
    assert client.get("/filler/59/x").status_code == 200
    assert client.get("/nowhere/at/all").json()["which"] == "catch-all"
    assert client.delete("/items/special").status_code == 405


def test_a_route_with_its_own_match_is_always_asked():
    """The scan only skips routes that still use the stock `match`."""
    asked: list[str] = []

    class Greedy(Route):
        def match(self, scope):
            asked.append(scope["path"])
            return MatchStatus.FULL, {}

    app = SilloApp(debug=False)
    app.router.routes.append(Greedy("/never-the-prefix", handler, methods=["GET"]))
    resp = TestClient(app).get("/something/else")
    assert resp.status_code == 200 and asked == ["/something/else"]


def test_routes_added_after_the_first_request_are_scanned():
    app = SilloApp(debug=False)

    @app.get("/first")
    async def first(ctx: HttpContext):
        return {"n": 1}

    client = TestClient(app)
    assert client.get("/first").json() == {"n": 1}
    assert client.get("/later").status_code == 404

    @app.get("/later")
    async def later(ctx: HttpContext):
        return {"n": 2}

    assert client.get("/later").json() == {"n": 2}


def test_mounts_and_websockets_are_still_reached_past_many_routes():
    app = SilloApp(debug=False)
    for i in range(40):
        app.get(f"/pad/{i}")(handler)

    from sillo.core.routing.router import Router

    router = Router(prefix="/mounted")

    @router.get("/hello")
    async def hello(ctx: HttpContext):
        return {"hi": 1}

    app.mount_router(router)

    @app.ws_route("/live")
    async def live(ws):
        await ws.accept()
        await ws.send_text("up")
        await ws.close()

    client = TestClient(app)
    assert client.get("/mounted/hello").json() == {"hi": 1}
    with client.websocket_connect("/live") as socket:
        assert socket.receive_text() == "up"


def test_a_mount_rejects_a_path_outside_its_prefix_without_the_regex():
    from sillo.core.routing.grouping import Group

    mount = Group(app=SilloApp(debug=False), path="/mounted")
    outside = {"type": "http", "path": "/elsewhere/x", "root_path": "", "headers": []}
    inside = {"type": "http", "path": "/mounted/x", "root_path": "", "headers": []}
    assert mount.match(outside) == (MatchStatus.NONE, {})
    assert mount.match(inside)[0] == MatchStatus.FULL
