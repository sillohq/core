from pathlib import Path

from sillo import silloApp
from sillo.frontend import FrontendApp
from sillo.routing import Group
from sillo.testclient import TestClient

HERE = Path(__file__).parent


def _set_up_frontend_dir(name: str, index_content: bytes = b"<html><body>index</body></html>") -> Path:
    """Create a temporary frontend directory with an index.html and example files."""
    d = HERE / name
    d.mkdir(exist_ok=True)
    (d / "index.html").write_bytes(index_content)
    (d / "example.txt").write_bytes(b"frontend file")
    (d / "subdir").mkdir(exist_ok=True)
    (d / "subdir" / "nested.txt").write_bytes(b"nested file")
    return d


def _tear_down_frontend_dir(d: Path) -> None:
    """Remove the temporary frontend directory."""
    if d.exists():
        for child in sorted(d.rglob("*"), reverse=True):
            if child.is_file():
                child.unlink()
            elif child.is_dir():
                child.rmdir()
        d.rmdir()


def test_frontend_serves_existing_file():
    d = _set_up_frontend_dir(".test_frontend_basic")
    try:
        app = silloApp()
        spa = FrontendApp(directory=d, fallback="auto")
        app.add_route(Group(path="/", app=spa))

        with TestClient(app) as client:
            resp = client.get("/example.txt")
            assert resp.status_code == 200
            assert b"frontend file" in resp.content

            resp = client.get("/subdir/nested.txt")
            assert resp.status_code == 200
            assert b"nested file" in resp.content
    finally:
        _tear_down_frontend_dir(d)


def test_frontend_serves_index_at_root():
    d = _set_up_frontend_dir(".test_frontend_index_root")
    try:
        app = silloApp()
        spa = FrontendApp(directory=d, fallback="auto")
        app.add_route(Group(path="/", app=spa))

        with TestClient(app) as client:
            resp = client.get("/")
            assert resp.status_code == 200
            assert b"index" in resp.content
    finally:
        _tear_down_frontend_dir(d)


def test_frontend_spa_fallback_to_index():
    d = _set_up_frontend_dir(".test_frontend_spa_fallback")
    try:
        app = silloApp()
        spa = FrontendApp(directory=d, fallback="auto")
        app.add_route(Group(path="/", app=spa))

        with TestClient(app) as client:
            resp = client.get("/some/client/route")
            assert resp.status_code == 200
            assert b"index" in resp.content
    finally:
        _tear_down_frontend_dir(d)


def test_frontend_spa_fallback_to_404_html():
    d = _set_up_frontend_dir(
        ".test_frontend_spa_fallback_404",
        index_content=b"<html><body>app</body></html>",
    )
    (d / "404.html").write_bytes(b"<html><body>not found</body></html>")
    try:
        app = silloApp()
        spa = FrontendApp(directory=d, fallback="auto")
        app.add_route(Group(path="/", app=spa))

        with TestClient(app) as client:
            resp = client.get("/some/unknown/path")
            assert resp.status_code == 200
            assert b"not found" in resp.content
    finally:
        _tear_down_frontend_dir(d)


def test_frontend_no_fallback():
    d = _set_up_frontend_dir(".test_frontend_no_fallback")
    try:
        app = silloApp()
        spa = FrontendApp(directory=d, fallback=None)
        app.add_route(Group(path="/", app=spa))

        with TestClient(app) as client:
            resp = client.get("/nonexistent")
            assert resp.status_code == 404
    finally:
        _tear_down_frontend_dir(d)


def test_frontend_custom_fallback():
    d = _set_up_frontend_dir(".test_frontend_custom_fallback")
    (d / "app.html").write_bytes(b"<html><body>app shell</body></html>")
    try:
        app = silloApp()
        spa = FrontendApp(directory=d, fallback="app.html")
        app.add_route(Group(path="/", app=spa))

        with TestClient(app) as client:
            resp = client.get("/some/route")
            assert resp.status_code == 200
            assert b"app shell" in resp.content
    finally:
        _tear_down_frontend_dir(d)


def test_frontend_only_get_allowed():
    d = _set_up_frontend_dir(".test_frontend_methods")
    try:
        app = silloApp()
        spa = FrontendApp(directory=d, fallback="auto")
        app.add_route(Group(path="/", app=spa))

        with TestClient(app) as client:
            resp = client.post("/example.txt")
            assert resp.status_code == 405

            resp = client.put("/example.txt")
            assert resp.status_code == 405

            resp = client.delete("/example.txt")
            assert resp.status_code == 405
    finally:
        _tear_down_frontend_dir(d)


def test_frontend_route_precedence():
    d = _set_up_frontend_dir(".test_frontend_precedence")
    try:
        app = silloApp()

        @app.get("/api/hello")
        async def hello(request, response):
            return response.json({"msg": "hello"})

        app.frontend("/", directory=d, fallback="auto")

        with TestClient(app) as client:
            resp = client.get("/api/hello")
            assert resp.status_code == 200
            assert resp.json() == {"msg": "hello"}

            resp = client.get("/some/client/route")
            assert resp.status_code == 200
            assert b"index" in resp.content
    finally:
        _tear_down_frontend_dir(d)


def test_frontend_cache_control():
    d = _set_up_frontend_dir(".test_frontend_cache")
    try:
        app = silloApp()
        spa = FrontendApp(directory=d, fallback="auto", cache_control="public, max-age=3600")
        app.add_route(Group(path="/", app=spa))

        with TestClient(app) as client:
            resp = client.get("/example.txt")
            assert resp.status_code == 200
            assert resp.headers.get("cache-control") == "public, max-age=3600"

            resp = client.get("/unknown")
            assert resp.status_code == 200
            assert resp.headers.get("cache-control") == "public, max-age=3600"
    finally:
        _tear_down_frontend_dir(d)


def test_app_frontend_convenience():
    d = _set_up_frontend_dir(".test_app_frontend_convenience")
    try:
        app = silloApp()

        @app.get("/ping")
        async def ping(request, response):
            return response.json({"pong": True})

        app.frontend("/", directory=d, fallback="auto")

        with TestClient(app) as client:
            resp = client.get("/ping")
            assert resp.status_code == 200
            assert resp.json() == {"pong": True}

            resp = client.get("/example.txt")
            assert resp.status_code == 200
            assert b"frontend file" in resp.content

            resp = client.get("/client/route")
            assert resp.status_code == 200
            assert b"index" in resp.content
    finally:
        _tear_down_frontend_dir(d)


def test_frontend_mounted_at_subpath():
    d = _set_up_frontend_dir(".test_frontend_subpath")
    try:
        app = silloApp()
        spa = FrontendApp(directory=d, fallback="auto")
        app.add_route(Group(path="/app", app=spa))

        with TestClient(app) as client:
            resp = client.get("/app/example.txt")
            assert resp.status_code == 200
            assert b"frontend file" in resp.content

            resp = client.get("/app/some/route")
            assert resp.status_code == 200
            assert b"index" in resp.content
    finally:
        _tear_down_frontend_dir(d)

