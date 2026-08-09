"""Documentation presenters for the generated OpenAPI document.

A presenter turns the OpenAPI document into a browsable page. sillo ships
:class:`Atlas` — its own reference, and the default at ``/docs`` — plus
:class:`Swagger`, :class:`ReDoc` and :class:`Scalar`. Anything else is a
class with a ``render`` method, so a third-party viewer needs no
registration hook and no changes here.

    app = SilloApp(docs=[Atlas(path="/docs"), Scalar(path="/reference")])

``docs=[]`` serves no documentation UI at all. The raw document stays at
``openapi_url`` regardless — presenters render it, they do not produce it.
"""

from __future__ import annotations

import html
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any


def _escape(value: str) -> str:
    """Escape a value for an HTML text node or a double-quoted attribute."""
    return html.escape(str(value), quote=True)


def _script_json(value: Any) -> str:
    """Serialize a value for embedding inside a ``<script>`` block.

    ``json.dumps`` escapes for JSON, not for HTML: a string containing
    ``</script>`` closes the tag early and drops the rest of the page into
    the document as markup. Splitting the sequence keeps the JSON identical
    to a parser while making it inert to the HTML tokenizer.
    """
    return json.dumps(value).replace("</", "<\\/")


if TYPE_CHECKING:  # pragma: no cover - typing only
    from sillo.openapi.config import OpenAPIConfig

__all__ = [
    "Atlas",
    "DocsContext",
    "DocsUI",
    "ReDoc",
    "Scalar",
    "Swagger",
    "default_docs",
]


@dataclass(frozen=True)
class DocsContext:
    """What a presenter is given at request time.

    Attributes:
        openapi_url: Path to the OpenAPI document, already prefixed with the
            request's ``root_path``. Use this rather than building a URL, or
            the page breaks when the application is mounted under a prefix.
        title: The API title from the OpenAPI ``info`` block.
        version: The API version from the OpenAPI ``info`` block.
        description: The API description, or ``""`` when unset.
        config: The full :class:`OpenAPIConfig`, for anything the fields
            above do not cover.
    """

    openapi_url: str
    title: str
    version: str
    description: str
    config: OpenAPIConfig


class DocsUI:
    """Base class for a documentation presenter.

    Subclasses set :attr:`path` and implement :meth:`render`. The class
    attributes are defaults; ``__init__`` accepts overrides so one presenter
    class can be mounted more than once at different paths.

    Attributes:
        path: Where the page is served. Must begin with ``/``.
        name: Short identifier, used in error messages and by
            :meth:`SilloApp.get_docs_ui`.
    """

    path: str = "/docs"
    name: str = "docs"

    def __init__(
        self,
        *,
        path: str | None = None,
        title: str | None = None,
        favicon_url: str | None = None,
    ) -> None:
        """Initialize a presenter.

        Args:
            path: Where to serve the page. Defaults to the class's
                :attr:`path`.
            title: Browser tab title. Defaults to the API title at render
                time, so it tracks ``SilloApp(title=...)`` unless overridden.
            favicon_url: Icon for the page. ``None`` omits the link tag.

        Raises:
            ValueError: If ``path`` does not begin with ``/``.
        """
        if path is not None:
            if not path.startswith("/"):
                raise ValueError(
                    f"{type(self).__name__} path must start with '/', got {path!r}"
                )
            self.path = path
        self.title = title
        self.favicon_url = favicon_url

    def resolve_title(self, ctx: DocsContext) -> str:
        """The page title: this presenter's override, else the API title."""
        return self.title or ctx.title

    def render(self, ctx: DocsContext) -> str:
        """Return the complete HTML page for this viewer.

        Args:
            ctx: The rendering context. ``ctx.openapi_url`` is already
                mount-aware.

        Returns:
            An HTML document as a string.

        Raises:
            NotImplementedError: Always, on the base class.
        """
        raise NotImplementedError(
            f"{type(self).__name__} must implement render(ctx) -> str"
        )

    def _favicon_tag(self) -> str:
        """A ``<link rel=icon>`` tag, or an empty string when unset."""
        if not self.favicon_url:
            return ""
        # The type follows the extension: a browser handed an SVG labelled
        # image/png may refuse to render it.
        media = "image/svg+xml" if self.favicon_url.endswith(".svg") else "image/png"
        return f'<link rel="icon" href="{_escape(self.favicon_url)}" type="{media}">'

    def __repr__(self) -> str:
        return f"{type(self).__name__}(path={self.path!r})"


DEFAULT_FAVICON = "https://docs.sillo.build/favicon.svg"

#: Atlas is pinned to a released tag rather than a branch. An unpinned CDN
#: URL means every application's documentation changes the moment Atlas
#: does — a bad surprise in production, and an unreproducible bug report.
ATLAS_VERSION = "v0.8.0"
ATLAS_JS = (
    f"https://cdn.jsdelivr.net/gh/sillohq/atlas@{ATLAS_VERSION}"
    "/dist/atlas.standalone.js"
)

SWAGGER_JS = "https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"
SWAGGER_CSS = "https://unpkg.com/swagger-ui-dist@5/swagger-ui.css"
REDOC_JS = "https://cdn.redoc.ly/redoc/latest/bundles/redoc.standalone.js"
SCALAR_JS = "https://cdn.jsdelivr.net/npm/@scalar/api-reference"


class Atlas(DocsUI):
    """Atlas — sillo's own OpenAPI reference, and the default at ``/docs``.

    A three-pane reference with a request builder that actually sends,
    ranked search, and snippets in nine languages. Zero dependencies, and
    it carries its own styles, so the page is one script tag.

    ``ui_config`` is merged into the ``createApiReference`` call, so options
    this class has never heard of still work::

        Atlas(theme="dark", ui_config={"deepLinking": False})

    ``js_url`` points at a pinned tag on jsDelivr. Override it to
    self-host — a deployment with no outbound network or a strict
    ``Content-Security-Policy`` cannot reach a CDN, and the failure is a
    blank page rather than an error.
    """

    path = "/docs"
    name = "atlas"

    def __init__(
        self,
        *,
        path: str | None = None,
        title: str | None = None,
        favicon_url: str | None = DEFAULT_FAVICON,
        js_url: str = ATLAS_JS,
        theme: str = "auto",
        ui_config: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the Atlas presenter.

        Args:
            path: Where to serve the page. Defaults to ``"/docs"``.
            title: Browser tab title. Defaults to the API title.
            favicon_url: Icon for the page, or ``None`` for no icon.
            js_url: URL of the Atlas standalone bundle.
            theme: ``"auto"`` follows the reader's operating system.
            ui_config: Extra options merged into the mount call. ``url`` is
                set by this class.
        """
        super().__init__(path=path, title=title, favicon_url=favicon_url)
        self.js_url = js_url
        self.theme = theme
        self.ui_config = dict(ui_config or {})

    def render(self, ctx: DocsContext) -> str:
        """Render the Atlas page."""
        options: dict[str, Any] = {
            "theme": self.theme,
            **self.ui_config,
            # Set last: this identifies the document, and a caller
            # overriding it has only broken their own page.
            "url": ctx.openapi_url,
        }
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{_escape(self.resolve_title(ctx))}</title>
    {self._favicon_tag()}
    <style>html, body {{ margin: 0; padding: 0; height: 100%; }}</style>
</head>
<body>
    <div id="app"></div>
    <script src="{_escape(self.js_url)}"></script>
    <script>
        Atlas.createApiReference('#app', {_script_json(options)});
    </script>
</body>
</html>"""


class Swagger(DocsUI):
    """Swagger UI.

    ``ui_config`` is passed straight through to ``SwaggerUIBundle``, so
    options this class has never heard of still work::

        Swagger(ui_config={"persistAuthorization": True, "docExpansion": "none"})

    ``js_url`` and ``css_url`` point at a CDN by default. Override both to
    serve the assets yourself, which is what a deployment with no outbound
    network or a strict CSP needs.
    """

    path = "/docs"
    name = "swagger"

    def __init__(
        self,
        *,
        path: str | None = None,
        title: str | None = None,
        favicon_url: str | None = DEFAULT_FAVICON,
        js_url: str = SWAGGER_JS,
        css_url: str = SWAGGER_CSS,
        ui_config: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the Swagger UI presenter.

        Args:
            path: Where to serve the page. Defaults to ``"/docs"``.
            title: Browser tab title. Defaults to the API title.
            favicon_url: Icon for the page, or ``None`` for no icon.
            js_url: URL of ``swagger-ui-bundle.js``.
            css_url: URL of ``swagger-ui.css``.
            ui_config: Extra options merged into the ``SwaggerUIBundle``
                call. ``url`` and ``dom_id`` are set by this class and are
                overwritten if supplied.
        """
        super().__init__(path=path, title=title, favicon_url=favicon_url)
        self.js_url = js_url
        self.css_url = css_url
        self.ui_config = dict(ui_config or {})

    def render(self, ctx: DocsContext) -> str:
        """Render the Swagger UI page."""
        options: dict[str, Any] = {
            "layout": "BaseLayout",
            "deepLinking": True,
            **self.ui_config,
            # Set last: these two identify the document and the mount point,
            # and a caller overriding them has only broken the page.
            "url": ctx.openapi_url,
            "dom_id": "#swagger-ui",
        }
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{_escape(self.resolve_title(ctx))}</title>
    <link rel="stylesheet" href="{self.css_url}">
    {self._favicon_tag()}
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="{self.js_url}"></script>
    <script>
        window.onload = function() {{
            window.ui = SwaggerUIBundle({_script_json(options)});
        }};
    </script>
</body>
</html>"""


class ReDoc(DocsUI):
    """ReDoc.

    ``ui_config`` is passed to ``Redoc.init`` as its options object::

        ReDoc(ui_config={"hideDownloadButton": True, "expandResponses": "200"})
    """

    path = "/redoc"
    name = "redoc"

    def __init__(
        self,
        *,
        path: str | None = None,
        title: str | None = None,
        favicon_url: str | None = DEFAULT_FAVICON,
        js_url: str = REDOC_JS,
        ui_config: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the ReDoc presenter.

        Args:
            path: Where to serve the page. Defaults to ``"/redoc"``.
            title: Browser tab title. Defaults to the API title.
            favicon_url: Icon for the page, or ``None`` for no icon.
            js_url: URL of ``redoc.standalone.js``.
            ui_config: Options object handed to ``Redoc.init``.
        """
        super().__init__(path=path, title=title, favicon_url=favicon_url)
        self.js_url = js_url
        self.ui_config = dict(ui_config or {})

    def render(self, ctx: DocsContext) -> str:
        """Render the ReDoc page."""
        options: dict[str, Any] = {"scrollYOffset": 50, **self.ui_config}
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{_escape(self.resolve_title(ctx))}</title>
    {self._favicon_tag()}
    <style>body {{ margin: 0; padding: 0; }}</style>
</head>
<body>
    <div id="redoc"></div>
    <script src="{self.js_url}"></script>
    <script>
        Redoc.init(
            {_script_json(ctx.openapi_url)},
            {_script_json(options)},
            document.getElementById('redoc')
        );
    </script>
</body>
</html>"""


class Scalar(DocsUI):
    """Scalar API Reference.

    ``theme`` is Scalar's built-in palette name — ``"default"``,
    ``"purple"``, ``"moon"``, ``"solarized"`` and so on. Anything else goes
    through ``ui_config``::

        Scalar(theme="purple", ui_config={"hideDownloadButton": True})
    """

    path = "/reference"
    name = "scalar"

    def __init__(
        self,
        *,
        path: str | None = None,
        title: str | None = None,
        favicon_url: str | None = DEFAULT_FAVICON,
        js_url: str = SCALAR_JS,
        theme: str = "default",
        ui_config: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the Scalar presenter.

        Args:
            path: Where to serve the page. Defaults to ``"/reference"``.
            title: Browser tab title. Defaults to the API title.
            favicon_url: Icon for the page, or ``None`` for no icon.
            js_url: URL of the Scalar API reference bundle.
            theme: Scalar palette name.
            ui_config: Extra configuration merged into Scalar's
                configuration object. ``url`` is set by this class.
        """
        super().__init__(path=path, title=title, favicon_url=favicon_url)
        self.js_url = js_url
        self.theme = theme
        self.ui_config = dict(ui_config or {})

    def render(self, ctx: DocsContext) -> str:
        """Render the Scalar API reference page."""
        options: dict[str, Any] = {
            "theme": self.theme,
            **self.ui_config,
            "url": ctx.openapi_url,
        }
        # Current Scalar bundles mount through Scalar.createApiReference().
        # The older forms — a `<script id="api-reference">` carrying the spec
        # in its body, or configured through data-url/data-configuration —
        # are not what the unversioned CDN build reads, and the failure is a
        # blank page with nothing in the console.
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{_escape(self.resolve_title(ctx))}</title>
    {self._favicon_tag()}
    <style>body {{ margin: 0; padding: 0; }}</style>
</head>
<body>
    <div id="app"></div>
    <script src="{self.js_url}"></script>
    <script>
        Scalar.createApiReference('#app', {_script_json(options)});
    </script>
</body>
</html>"""


def default_docs(swagger_url: str = "/docs", redoc_url: str = "/redoc") -> list[DocsUI]:
    """The presenters mounted when ``docs`` is not given.

    ``/docs`` is :class:`Atlas`, sillo's own reference. Swagger UI is still
    shipped and one line away::

        app = SilloApp(docs=[Swagger(path="/docs"), ReDoc()])

    Args:
        swagger_url: Path for the primary viewer. Named for the argument it
            still backs — ``SilloApp(swagger_docs=...)`` — which predates
            there being a choice of viewer.
        redoc_url: Path for ReDoc.

    Returns:
        A fresh list — callers mutate their own copy, and a default list
        shared between applications would leak presenters between them.
    """
    return [Atlas(path=swagger_url), ReDoc(path=redoc_url)]
