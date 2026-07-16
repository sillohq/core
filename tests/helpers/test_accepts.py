from sillo import silloApp
from sillo.http import Request, Response
from sillo.helpers.accepts import (
    AcceptItem,
    AcceptsInfo,
    parse_accept_header,
    parse_accept_language,
    parse_accept_charset,
    parse_accept_encoding,
    negotiate_content_type,
    negotiate_language,
    negotiate_charset,
    negotiate_encoding,
    matches_media_type,
    get_best_match,
    get_accepts_info,
    create_vary_header,
    AcceptsMiddleware,
    Accepts,
    ContentNegotiationMiddleware,
)
from sillo.testclient import TestClient


class TestAcceptParsing:
    def test_parse_accept_header_basic(self):
        items = parse_accept_header("text/html, application/json;q=0.9")
        assert len(items) == 2
        assert items[0].value == "text/html"
        assert items[0].quality == 1.0
        assert items[1].value == "application/json"
        assert items[1].quality == 0.9

    def test_parse_accept_header_empty(self):
        assert parse_accept_header("") == []

    def test_parse_accept_header_single(self):
        items = parse_accept_header("text/html")
        assert len(items) == 1
        assert items[0].value == "text/html"

    def test_parse_accept_header_wildcard(self):
        items = parse_accept_header("*/*")
        assert len(items) == 1
        assert items[0].value == "*/*"

    def test_parse_accept_language(self):
        items = parse_accept_language("en-US,en;q=0.9,fr;q=0.7")
        assert len(items) == 3
        assert items[0].value == "en-US"

    def test_parse_accept_charset(self):
        items = parse_accept_charset("utf-8, iso-8859-1;q=0.5")
        assert len(items) == 2

    def test_parse_accept_encoding(self):
        items = parse_accept_encoding("gzip, deflate, br;q=0.9")
        assert len(items) == 3

    def test_accept_item_repr(self):
        item = AcceptItem("text/html", 1.0)
        assert "text/html" in repr(item)
        assert "1.0" in repr(item)


class TestMediaTypeMatching:
    def test_exact_match(self):
        assert matches_media_type("text/html", "text/html")

    def test_wildcard_match(self):
        assert matches_media_type("*/*", "text/html")
        assert matches_media_type("*/*", "application/json")

    def test_subtype_wildcard(self):
        assert matches_media_type("text/*", "text/html")
        assert matches_media_type("text/*", "text/plain")
        assert not matches_media_type("text/*", "application/json")

    def test_no_match(self):
        assert not matches_media_type("text/html", "application/json")


class TestContentNegotiation:
    def test_negotiate_content_type_exact(self):
        result = negotiate_content_type("text/html", ["application/json", "text/html"])
        assert result == "text/html"

    def test_negotiate_content_type_wildcard(self):
        result = negotiate_content_type("*/*", ["application/json", "text/html"])
        assert result == "application/json"

    def test_negotiate_content_type_no_match(self):
        result = negotiate_content_type("image/png", ["text/html", "application/json"])
        assert result is None

    def test_negotiate_language(self):
        result = negotiate_language("fr, en;q=0.9", ["en", "de", "fr"])
        assert result == "fr"

    def test_negotiate_charset(self):
        result = negotiate_charset("utf-8", ["utf-8", "iso-8859-1"])
        assert result == "utf-8"

    def test_get_best_match(self):
        result = get_best_match(
            "text/html, application/json;q=0.9",
            ["application/json", "text/plain", "text/html"],
        )
        assert result == "text/html"


class TestVaryHeader:
    def test_create_vary_new(self):
        result = create_vary_header(None, ["Accept", "Accept-Language"])
        assert result == "Accept, Accept-Language"

    def test_create_vary_existing(self):
        result = create_vary_header("Accept", ["Accept-Language", "Accept-Charset"])
        assert "Accept" in result
        assert "Accept-Language" in result
        assert "Accept-Charset" in result


class TestAcceptsMiddleware:
    def test_middleware_sets_content_type(self):
        app = silloApp()
        app.use(AcceptsMiddleware())

        @app.get("/test")
        async def test_route(request: Request, response: Response):
            return response.json({"ok": True})

        client = TestClient(app)
        response = client.get("/test")
        assert "Content-Type" in response.headers

    def test_middleware_sets_vary_header(self):
        app = silloApp()
        app.use(AcceptsMiddleware())

        @app.get("/test")
        async def test_route(request: Request, response: Response):
            return response.json({"ok": True})

        client = TestClient(app)
        response = client.get("/test", headers={"Accept": "application/json"})
        assert "Vary" in response.headers

    def test_accepts_factory(self):
        mw = Accepts(default_content_type="text/html")
        assert isinstance(mw, AcceptsMiddleware)
        assert mw.default_content_type == "text/html"

    def test_middleware_parses_accepts(self):
        app = silloApp()
        app.use(AcceptsMiddleware(store_accepts_info=True))

        @app.get("/test")
        async def test_route(request: Request, response: Response):
            info = getattr(request.state, "accepts_parsed", None)
            return response.json({"has_accepts": info is not None})

        client = TestClient(app)
        response = client.get("/test", headers={"Accept": "text/html"})
        assert response.json()["has_accepts"]


class TestAcceptsInfo:
    def test_accepted_types(self):
        app = silloApp()
        app.use(AcceptsMiddleware())

        @app.get("/test")
        async def test_route(request: Request, response: Response):
            info = AcceptsInfo(request)
            return response.json({"types": info.get_accepted_types()})

        client = TestClient(app)
        response = client.get("/test", headers={"Accept": "text/html, application/json"})
        assert "text/html" in response.json()["types"]


class TestContentNegotiationMiddleware:
    def test_negotiate_content_type_method(self):
        app = silloApp()

        @app.get("/test")
        async def test_route(request: Request, response: Response):
            return response.json({"ok": True})

        client = TestClient(app)
        response = client.get(
            "/test", headers={"Accept": "text/html, application/json"}
        )
        assert response.status_code == 200
