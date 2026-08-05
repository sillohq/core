"""Tests for the documentation presenter plugin system.

These assert on what a browser would receive — the page is served, it points
at the right document, the viewer's own script is on it — rather than on the
presenter having been constructed. A presenter that is mounted but renders a
page pointing at the wrong URL passes every "is it registered" check and
shows an empty viewer to the user.
"""

import json
import re

import pytest

from sillo import silloApp
from sillo.openapi.ui import (
    ATLAS_VERSION,
    SCALAR_JS,
    Atlas,
    DocsContext,
    DocsUI,
    ReDoc,
    Scalar,
    Swagger,
    default_docs,
)
from sillo.testclient import TestClient


def _scalar_config(html: str) -> dict:
    """Pull the options back out of Scalar's ``createApiReference`` call."""
    raw = re.search(r"createApiReference\('#app',\s*(\{.*?\})\);", html, re.S).group(1)
    return json.loads(raw.replace("<\\/", "</"))


def _ctx(openapi_url="/openapi.json", title="Test API"):
    """A context standing in for one built during a request."""
    from sillo.openapi.config import OpenAPIConfig

    config = OpenAPIConfig(title=title, version="9.9.9", description="d")
    return DocsContext(
        openapi_url=openapi_url,
        title=title,
        version="9.9.9",
        description="d",
        config=config,
    )


class TestDefaults:
    def test_default_mounts_atlas_and_redoc(self):
        # Atlas is sillo's own reference and the default at /docs. Swagger
        # is still shipped and one line away.
        app = silloApp()

        assert [ui.name for ui in app.docs] == ["atlas", "redoc"]
        assert [ui.path for ui in app.docs] == ["/docs", "/redoc"]

    def test_the_default_page_mounts_atlas(self):
        page = TestClient(silloApp()).get("/docs").text

        assert "Atlas.createApiReference" in page
        assert "SwaggerUIBundle" not in page

    def test_swagger_is_still_available(self):
        client = TestClient(silloApp(docs=[Swagger(path="/docs")]))

        assert "SwaggerUIBundle" in client.get("/docs").text

    def test_default_pages_are_served(self):
        client = TestClient(silloApp())

        assert client.get("/docs").status_code == 200
        assert client.get("/redoc").status_code == 200
        assert client.get("/openapi.json").status_code == 200

    def test_default_docs_returns_a_fresh_list(self):
        # A shared mutable default would leak presenters between applications.
        first = default_docs()
        first.append(Scalar())

        assert len(default_docs()) == 2


class TestSelectingViewers:
    def test_scalar_can_be_mounted(self):
        app = silloApp(docs=[Scalar(path="/reference")])
        client = TestClient(app)

        response = client.get("/reference")

        assert response.status_code == 200
        assert "@scalar/api-reference" in response.text

    def test_only_the_listed_viewers_are_mounted(self):
        client = TestClient(silloApp(docs=[Scalar(path="/reference")]))

        assert client.get("/reference").status_code == 200
        assert client.get("/docs").status_code == 404
        assert client.get("/redoc").status_code == 404

    def test_empty_list_serves_no_ui(self):
        client = TestClient(silloApp(docs=[]))

        assert client.get("/docs").status_code == 404
        assert client.get("/redoc").status_code == 404

    def test_empty_list_still_serves_the_document(self):
        # Turning off the viewers must not turn off the spec they render.
        client = TestClient(silloApp(docs=[]))

        response = client.get("/openapi.json")

        assert response.status_code == 200
        assert response.json()["openapi"].startswith("3.")

    def test_one_viewer_can_be_mounted_twice(self):
        app = silloApp(docs=[Swagger(path="/docs"), Swagger(path="/internal/docs")])
        client = TestClient(app)

        assert client.get("/docs").status_code == 200
        assert client.get("/internal/docs").status_code == 200

    def test_all_three_together(self):
        client = TestClient(silloApp(docs=[Swagger(), ReDoc(), Scalar()]))

        assert client.get("/docs").status_code == 200
        assert client.get("/redoc").status_code == 200
        assert client.get("/reference").status_code == 200


class TestEachViewerRendersItself:
    """Every presenter must point the viewer at the document.

    Checked per presenter because a copy-paste error between them produces a
    page that loads the viewer and shows nothing.
    """

    @pytest.mark.parametrize(
        "ui, marker",
        [
            (Swagger(), "SwaggerUIBundle"),
            (ReDoc(), "Redoc.init"),
            (Scalar(), "api-reference"),
        ],
        ids=["swagger", "redoc", "scalar"],
    )
    def test_page_loads_the_viewer_and_names_the_document(self, ui, marker):
        html = ui.render(_ctx(openapi_url="/openapi.json"))

        assert html.startswith("<!DOCTYPE html>")
        assert marker in html
        assert "/openapi.json" in html

    @pytest.mark.parametrize(
        "ui", [Swagger(), ReDoc(), Scalar()], ids=["swagger", "redoc", "scalar"]
    )
    def test_title_defaults_to_the_api_title(self, ui):
        assert "<title>Widgets</title>" in ui.render(_ctx(title="Widgets"))

    @pytest.mark.parametrize(
        "cls", [Swagger, ReDoc, Scalar], ids=["swagger", "redoc", "scalar"]
    )
    def test_title_can_be_overridden(self, cls):
        html = cls(title="Internal").render(_ctx(title="Widgets"))

        assert "<title>Internal</title>" in html

    @pytest.mark.parametrize(
        "cls", [Swagger, ReDoc, Scalar], ids=["swagger", "redoc", "scalar"]
    )
    def test_favicon_is_omitted_when_unset(self, cls):
        assert 'rel="icon"' not in cls(favicon_url=None).render(_ctx())


class TestMountPrefix:
    def test_the_page_points_at_the_prefixed_document(self):
        # Under a mount, '/openapi.json' is not where the document lives; a
        # page hardcoding it renders an empty viewer with no visible error.
        app = silloApp(docs=[Swagger()])
        client = TestClient(app, root_path="/api/v1")

        html = client.get("/docs").text

        assert "/api/v1/openapi.json" in html

    def test_context_carries_the_prefixed_url(self):
        app = silloApp()

        ctx = app._docs_context("/api/v1")

        assert ctx.openapi_url == "/api/v1/openapi.json"

    def test_no_prefix_leaves_the_url_alone(self):
        assert silloApp()._docs_context("").openapi_url == "/openapi.json"


class TestUIConfig:
    def test_swagger_options_reach_the_bundle_call(self):
        ui = Swagger(ui_config={"persistAuthorization": True, "docExpansion": "none"})

        html = ui.render(_ctx())

        assert '"persistAuthorization": true' in html
        assert '"docExpansion": "none"' in html

    def test_swagger_config_is_valid_json(self):
        # The options are interpolated into a <script>; malformed JSON breaks
        # the page rather than the render, so parse what we emit.
        html = Swagger(ui_config={"docExpansion": "none"}).render(_ctx())

        payload = re.search(r"SwaggerUIBundle\((\{.*?\})\);", html, re.DOTALL).group(1)
        options = json.loads(payload)

        assert options["url"] == "/openapi.json"
        assert options["dom_id"] == "#swagger-ui"
        assert options["docExpansion"] == "none"

    def test_url_cannot_be_overridden_by_ui_config(self):
        # Letting a caller replace 'url' only ever breaks their own page.
        ui = Swagger(ui_config={"url": "https://example.com/other.json"})

        html = ui.render(_ctx(openapi_url="/openapi.json"))
        payload = re.search(r"SwaggerUIBundle\((\{.*?\})\);", html, re.DOTALL).group(1)

        assert json.loads(payload)["url"] == "/openapi.json"

    def test_redoc_options_reach_init(self):
        html = ReDoc(ui_config={"hideDownloadButton": True}).render(_ctx())

        assert '"hideDownloadButton": true' in html

    def test_scalar_theme_is_applied(self):
        assert (
            "purple" in _scalar_config(Scalar(theme="purple").render(_ctx()))["theme"]
        )

    def test_scalar_config_is_valid_json(self):
        html = Scalar(ui_config={"hideDownloadButton": True}).render(_ctx())

        options = _scalar_config(html)

        assert options["url"] == "/openapi.json"
        assert options["hideDownloadButton"] is True

    def test_scalar_mounts_through_create_api_reference(self):
        # Current Scalar bundles mount this way. The legacy forms — the spec
        # in a <script id="api-reference"> body, or data-url/data-configuration
        # attributes — are ignored by the CDN build, and the failure is a
        # blank page with nothing in the console.
        html = Scalar().render(_ctx(openapi_url="/api/v1/openapi.json"))

        assert "Scalar.createApiReference('#app'," in html
        assert '<div id="app"></div>' in html
        assert _scalar_config(html)["url"] == "/api/v1/openapi.json"

    def test_scalar_loads_the_bundle_before_calling_it(self):
        # Scalar.createApiReference is defined by the bundle, so a call
        # placed above the <script src> runs against an undefined global.
        html = Scalar().render(_ctx())

        assert html.index(SCALAR_JS) < html.index("Scalar.createApiReference")


class TestSelfHosting:
    def test_swagger_assets_can_be_self_hosted(self):
        # The point of these knobs: a deployment with no outbound network.
        ui = Swagger(
            js_url="/static/swagger-ui-bundle.js",
            css_url="/static/swagger-ui.css",
        )

        html = ui.render(_ctx())

        assert "/static/swagger-ui-bundle.js" in html
        assert "/static/swagger-ui.css" in html
        assert "unpkg.com" not in html

    def test_redoc_script_can_be_self_hosted(self):
        html = ReDoc(js_url="/static/redoc.js").render(_ctx())

        assert "/static/redoc.js" in html
        assert "cdn.redoc.ly" not in html

    def test_scalar_script_can_be_self_hosted(self):
        html = Scalar(js_url="/static/scalar.js").render(_ctx())

        assert "/static/scalar.js" in html
        assert "jsdelivr" not in html


class TestCustomPresenter:
    """A viewer sillo does not ship needs no changes to sillo."""

    def test_a_third_party_presenter_is_served(self):
        class RapiDoc(DocsUI):
            path = "/rapidoc"
            name = "rapidoc"

            def render(self, ctx: DocsContext) -> str:
                return (
                    f"<!DOCTYPE html><html><head><title>{ctx.title}</title></head>"
                    f'<body><rapi-doc spec-url="{ctx.openapi_url}"></rapi-doc>'
                    f"</body></html>"
                )

        client = TestClient(silloApp(title="Widgets", docs=[RapiDoc()]))
        response = client.get("/rapidoc")

        assert response.status_code == 200
        assert 'spec-url="/openapi.json"' in response.text
        assert "<title>Widgets</title>" in response.text

    def test_a_duck_typed_presenter_is_accepted(self):
        # Not a DocsUI subclass: path plus render(ctx) is the whole contract.
        class Minimal:
            path = "/minimal"
            name = "minimal"

            def render(self, ctx):
                return "<html>ok</html>"

        client = TestClient(silloApp(docs=[Minimal()]))

        assert client.get("/minimal").text == "<html>ok</html>"

    def test_base_render_refuses_rather_than_serving_a_blank_page(self):
        class Incomplete(DocsUI):
            path = "/nope"

        with pytest.raises(NotImplementedError, match="Incomplete"):
            Incomplete().render(_ctx())


class TestEachRouteGetsItsOwnPresenter:
    def test_three_paths_render_three_different_viewers(self):
        # Registering routes in a loop is where a closure over the loop
        # variable makes every path render the last presenter. That failure
        # is invisible unless the pages are compared.
        client = TestClient(silloApp(docs=[Swagger(), ReDoc(), Scalar()]))

        swagger = client.get("/docs").text
        redoc = client.get("/redoc").text
        scalar = client.get("/reference").text

        assert "SwaggerUIBundle" in swagger
        assert "Redoc.init" in redoc and "SwaggerUIBundle" not in redoc
        assert "api-reference" in scalar and "SwaggerUIBundle" not in scalar

    def test_same_class_at_two_paths_keeps_its_own_config(self):
        app = silloApp(
            docs=[
                Swagger(path="/docs", title="Public"),
                Swagger(path="/internal", title="Internal"),
            ]
        )
        client = TestClient(app)

        assert "<title>Public</title>" in client.get("/docs").text
        assert "<title>Internal</title>" in client.get("/internal").text


class TestValidation:
    def test_duplicate_paths_are_rejected_at_construction(self):
        with pytest.raises(ValueError, match="/docs"):
            silloApp(docs=[Swagger(path="/docs"), Scalar(path="/docs")])

    def test_a_path_must_start_with_a_slash(self):
        with pytest.raises(ValueError, match="must start with"):
            Swagger(path="docs")

    def test_a_non_presenter_is_rejected(self):
        with pytest.raises(TypeError, match="render"):
            silloApp(docs=["/docs"])

    def test_an_object_without_render_is_rejected(self):
        class NoRender:
            path = "/x"

        with pytest.raises(TypeError, match="render"):
            silloApp(docs=[NoRender()])


class TestLegacyArguments:
    def test_swagger_docs_still_moves_the_page(self):
        client = TestClient(silloApp(swagger_docs="/api-docs"))

        assert client.get("/api-docs").status_code == 200
        assert client.get("/docs").status_code == 404

    def test_redoc_docs_still_moves_the_page(self):
        client = TestClient(silloApp(redoc_docs="/api-redoc"))

        assert client.get("/api-redoc").status_code == 200
        assert client.get("/redoc").status_code == 404

    def test_both_legacy_paths_together(self):
        app = silloApp(swagger_docs="/s", redoc_docs="/r")

        assert [ui.path for ui in app.docs] == ["/s", "/r"]

    def test_docs_with_moved_swagger_path_is_refused(self):
        # The two say the same thing; silently preferring one hides a typo.
        with pytest.raises(TypeError, match="swagger_docs"):
            silloApp(swagger_docs="/api-docs", docs=[Scalar()])

    def test_docs_with_moved_redoc_path_is_refused(self):
        with pytest.raises(TypeError, match="redoc_docs"):
            silloApp(redoc_docs="/api-redoc", docs=[Scalar()])

    def test_docs_with_default_legacy_paths_is_fine(self):
        # Passing the defaults explicitly is not a conflict.
        app = silloApp(swagger_docs="/docs", redoc_docs="/redoc", docs=[Scalar()])

        assert [ui.name for ui in app.docs] == ["scalar"]


class TestLookup:
    def test_a_mounted_presenter_is_found_by_name(self):
        app = silloApp(docs=[Swagger(path="/docs")])

        found = app.get_docs_ui("swagger")

        assert found is not None and found.path == "/docs"

    def test_an_absent_presenter_is_none(self):
        assert silloApp(docs=[]).get_docs_ui("swagger") is None


class TestDocsAreNotDocumented:
    def test_ui_routes_are_absent_from_the_schema(self):
        client = TestClient(silloApp(docs=[Swagger(), ReDoc(), Scalar()]))

        paths = client.get("/openapi.json").json()["paths"]

        for path in ("/docs", "/redoc", "/reference", "/openapi.json"):
            assert path not in paths

    def test_a_custom_presenter_is_absent_too(self):
        class Custom(DocsUI):
            path = "/custom-docs"
            name = "custom"

            def render(self, ctx):
                return "<html></html>"

        client = TestClient(silloApp(docs=[Custom()]))

        assert "/custom-docs" not in client.get("/openapi.json").json()["paths"]


class TestBuilderHelpers:
    """The pre-plugin generators still work, delegating to the presenters."""

    def test_swagger_generator_still_renders(self):
        app = silloApp(title="Widgets")

        html = app.openapi._generate_swagger_ui("/api/openapi.json")

        assert "SwaggerUIBundle" in html
        assert "/api/openapi.json" in html
        assert "<title>Widgets</title>" in html

    def test_redoc_generator_still_renders(self):
        app = silloApp(title="Widgets")

        html = app.openapi._generate_redoc_ui("/api/openapi.json")

        assert "Redoc.init" in html
        assert "/api/openapi.json" in html

    def test_generators_fall_back_to_the_configured_url(self):
        app = silloApp(openapi_url="/spec.json")

        assert "/spec.json" in app.openapi._generate_swagger_ui()


class TestEscaping:
    """Values interpolated into the page must not escape their context."""

    def test_a_title_cannot_break_out_of_the_title_tag(self):
        ui = Swagger(title="</title><script>alert(1)</script>")

        html = ui.render(_ctx())

        assert "<script>alert(1)</script>" not in html
        assert "&lt;/title&gt;" in html

    @pytest.mark.parametrize(
        "cls", [Swagger, ReDoc, Scalar], ids=["swagger", "redoc", "scalar"]
    )
    def test_every_viewer_escapes_the_title(self, cls):
        html = cls(title="<img src=x onerror=alert(1)>").render(_ctx())

        assert "<img src=x" not in html

    def test_config_cannot_close_the_script_tag(self):
        # json.dumps escapes for JSON, not for HTML: an embedded "</script>"
        # ends the block early and the rest of the page becomes markup.
        ui = Swagger(ui_config={"docExpansion": "</script><script>alert(1)"})

        html = ui.render(_ctx())

        assert "</script><script>alert(1)" not in html
        assert "<\\/script>" in html

    def test_redoc_config_cannot_close_the_script_tag(self):
        html = ReDoc(ui_config={"expandResponses": "</script>x"}).render(_ctx())

        assert "</script>x" not in html


class TestAtlas:
    """The default viewer."""

    def test_atlas_pins_a_released_tag(self):
        # An unpinned CDN URL means every application's documentation
        # changes the moment Atlas does.
        page = Atlas().render(_ctx())

        assert f"atlas@{ATLAS_VERSION}" in page
        assert "@main" not in page and "@latest" not in page

    def test_the_document_url_reaches_the_mount_call(self):
        page = Atlas().render(_ctx(openapi_url="/api/v1/openapi.json"))

        assert "/api/v1/openapi.json" in page
        assert "Atlas.createApiReference('#app'," in page

    def test_the_bundle_loads_before_it_is_called(self):
        # Atlas.createApiReference is defined by the bundle, so a call above
        # the <script src> runs against an undefined global.
        page = Atlas().render(_ctx())

        assert page.index("atlas.standalone.js") < page.index(
            "Atlas.createApiReference"
        )

    def test_the_favicon_is_the_sillo_one_and_typed_correctly(self):
        page = Atlas().render(_ctx())

        assert "https://docs.sillo.build/favicon.svg" in page
        # A browser handed an SVG labelled image/png may refuse to render it.
        assert 'type="image/svg+xml"' in page

    def test_the_favicon_can_be_removed(self):
        assert 'rel="icon"' not in Atlas(favicon_url=None).render(_ctx())

    def test_a_png_favicon_keeps_its_own_type(self):
        page = Atlas(favicon_url="https://example.com/icon.png").render(_ctx())

        assert 'type="image/png"' in page

    def test_the_bundle_can_be_self_hosted(self):
        # The point of the knob: a deployment with no outbound network.
        page = Atlas(js_url="/static/atlas.js").render(_ctx())

        assert "/static/atlas.js" in page
        assert "jsdelivr" not in page

    def test_ui_config_reaches_the_mount_call(self):
        page = Atlas(theme="dark", ui_config={"deepLinking": False}).render(_ctx())

        assert '"theme": "dark"' in page
        assert '"deepLinking": false' in page

    def test_url_cannot_be_overridden_by_ui_config(self):
        page = Atlas(ui_config={"url": "https://example.com/other.json"}).render(
            _ctx(openapi_url="/openapi.json")
        )
        payload = re.search(
            r"createApiReference\('#app', (\{.*?\})\);", page, re.DOTALL
        )

        assert json.loads(payload.group(1))["url"] == "/openapi.json"

    def test_a_hostile_title_cannot_break_out(self):
        page = Atlas(title="</title><script>alert(1)</script>").render(_ctx())

        assert "<script>alert(1)</script>" not in page
