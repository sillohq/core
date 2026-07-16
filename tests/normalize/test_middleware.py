from sillo import silloApp
from sillo.http import Request, Response
from sillo.normalize import NormalizeMiddleware, SlashAction, Normalize
from sillo.testclient import TestClient


class TestNormalizeMiddleware:
    def test_remove_trailing_slash_inline(self):
        app = silloApp()
        app.use(NormalizeMiddleware(slash_action=SlashAction.REMOVE))

        @app.get("/test")
        async def test_route(request: Request, response: Response):
            return response.json({"path": request.url.path})

        client = TestClient(app)
        response = client.get("/test/")
        assert response.status_code == 200
        assert response.json()["path"] == "/test"

    def test_add_trailing_slash_inline(self):
        app = silloApp()
        app.use(NormalizeMiddleware(slash_action=SlashAction.ADD))

        @app.get("/test/")
        async def test_route(request: Request, response: Response):
            return response.json({"path": request.url.path})

        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 200
        assert response.json()["path"] == "/test/"

    def test_double_slash_normalization(self):
        app = silloApp()
        app.use(NormalizeMiddleware(slash_action=SlashAction.IGNORE))

        @app.get("/api/test")
        async def test_route(request: Request, response: Response):
            return response.json({"path": request.url.path})

        client = TestClient(app)
        response = client.get("/api/test")
        assert response.status_code == 200

    def test_skip_file_extensions(self):
        app = silloApp()
        app.use(NormalizeMiddleware(slash_action=SlashAction.IGNORE))

        @app.get("/style.css")
        async def css_route(request: Request, response: Response):
            return response.text("body{}")

        client = TestClient(app)
        response = client.get("/style.css")
        assert response.status_code == 200

    def test_normalize_factory_function(self):
        mw = Normalize(slash_action=SlashAction.ADD, redirect_status_code=308)
        assert isinstance(mw, NormalizeMiddleware)
        assert mw.slash_action == SlashAction.ADD
        assert mw.redirect_status_code == 308

    def test_normalize_case_enabled(self):
        app = silloApp()
        app.use(NormalizeMiddleware(slash_action=SlashAction.IGNORE, normalize_case=True))

        @app.get("/api/test")
        async def test_route(request: Request, response: Response):
            return response.json({"path": request.url.path})

        client = TestClient(app)
        response = client.get("/API/TEST")
        assert response.status_code == 200
