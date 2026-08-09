from sillo import SilloApp
from sillo.core.http import Request, Response
from sillo.http import ETag, ETagMiddleware, generate_etag_from_bytes
from sillo.testclient import TestClient


def test_etag_middleware_sets_etag_on_get():
    app = SilloApp()
    app.use(ETagMiddleware())

    @app.get("/test")
    async def handler(request: Request, response: Response):
        return response.json({"message": "Hello, World!"})

    client = TestClient(app)
    resp = client.get("/test")

    assert resp.status_code == 200
    assert resp.headers["etag"].startswith('W/"')


def test_etag_middleware_ignores_post_by_default():
    app = SilloApp()
    app.use(ETagMiddleware())

    @app.post("/test")
    async def handler(request: Request, response: Response):
        return response.json({"message": "Hello, World!"})

    client = TestClient(app)
    resp = client.post("/test", json={"data": "test"})

    assert resp.status_code == 200
    assert "etag" not in resp.headers


def test_etag_middleware_honors_existing_etag():
    app = SilloApp()
    app.use(ETag())

    @app.get("/test")
    async def handler(request: Request, response: Response):
        return response.json({"ok": True}).set_header("etag", '"custom-etag"')

    client = TestClient(app)
    resp = client.get("/test")

    assert resp.headers["etag"] == '"custom-etag"'


def test_etag_conditional_get_returns_304():
    app = SilloApp()
    app.use(ETagMiddleware())

    @app.get("/test")
    async def handler(request: Request, response: Response):
        return response.json({"message": "Hello, World!"})

    client = TestClient(app)
    first = client.get("/test")
    second = client.get("/test", headers={"if-none-match": first.headers["etag"]})

    assert second.status_code == 304
    assert second.headers["etag"] == first.headers["etag"]


def test_generate_etag_from_bytes_can_make_strong_tags():
    etag = generate_etag_from_bytes(b"hello", weak=False)

    assert etag.startswith('"')
    assert not etag.startswith("W/")
