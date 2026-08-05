---
title: Documentation UI
description: Choosing which API documentation viewers to serve — Atlas, Swagger UI, ReDoc, Scalar — configuring them, self-hosting their assets, and writing your own.
head:
  - tag: meta
    attrs:
      property: og:title
      content: Documentation UI in sillo
  - tag: meta
    attrs:
      property: og:description
      content: Atlas, Swagger UI, ReDoc and Scalar as pluggable presenters, plus writing your own.
---

#  Documentation UI

sillo generates one OpenAPI document and can render it through any number
of viewers. Which ones you get is a list you pass at construction:

```python
from sillo import silloApp
from sillo.openapi.ui import Atlas, Swagger, ReDoc, Scalar

app = silloApp(
    title="Myapp",
    docs=[
        Atlas(path="/docs"),
        ReDoc(path="/redoc"),
        Scalar(path="/reference", theme="purple"),
    ],
)
```

Leave `docs` unset and you get **Atlas** at `/docs` and ReDoc at `/redoc`.

##  Turning documentation off

```python
app = silloApp(docs=[])
```

No viewer is mounted and `/docs` is a 404.

The **document itself is still served** at `openapi_url`. Presenters
render the document; they do not produce it. If you want the schema gone
too, that is a separate decision:

```python
app = silloApp(docs=[], openapi_url="/internal/openapi.json")
```

<aside>

**A public API with the viewer disabled still publishes its schema.**
`/openapi.json` describes every route, parameter and model. Moving it
somewhere unguessable is not access control — if the schema should not be
public, put the route behind authentication or generate it into a file at
build time.

</aside>

##  The viewers

###  Atlas

```python
Atlas(path="/docs", theme="auto")
```

[Atlas](https://github.com/sillohq/atlas) is sillo's own reference, and
what `docs` defaults to — so this line is what you get for free.

Three panes: operations on the left, detail in the middle, a request
builder on the right.

- **`⌘K` search that ranks rather than filters.** Typing `user` puts
  `GET /users` above a passing mention of "user" twelve operations down.
- **A request builder that sends.** The form is seeded from the schema, so
  an operation is runnable the moment you open it. Real timing, status,
  size, headers, and a response viewer. Credentials persist across reloads.
- **Snippets in nine languages** — cURL, HTTPie, Python (httpx and
  requests), JavaScript fetch, Node axios, Go, PHP, Ruby — generated from
  *the same request the Send button makes*, so a copied snippet cannot
  describe something else.
- **The whole `info` block.** Licence, terms, contact and external
  documentation as links, every base URL, and every security scheme with
  its OAuth scopes.
- **Light and dark**, following the operating system.

79 KB with no dependencies and its styles inlined, so the page is one
script tag — against roughly 1.4 MB for Swagger UI.

<aside>

**It sends requests to the origin you are on.** A document declaring
`http://localhost:8000` is right on the author's machine and wrong on a
colleague's port 8001, on a LAN address, or behind a proxy. When the
document was fetched from the same origin as the page — that is, when your
API is serving its own documentation — Atlas offers that origin as *This
server* and selects it. The declared servers stay in the dropdown.

</aside>

####  Pinning and self-hosting

The bundle is served from a **pinned tag** on jsDelivr, never a branch. An
unpinned URL would mean every sillo application's documentation changes the
moment Atlas does — a bad surprise in production, and an unreproducible bug
report.

```python
from sillo.openapi.ui import ATLAS_VERSION

print(ATLAS_VERSION)     # the tag this sillo release points at
```

To serve it yourself — which a deployment with no outbound network or a
strict `Content-Security-Policy` needs — download
`dist/atlas.standalone.js` from that tag and point at your own copy:

```python
Atlas(js_url="/static/atlas.standalone.js")
```

The failure without this is a blank page rather than an error, because the
script never loads.

###  Swagger UI

```python
Swagger(path="/docs")
```

Interactive, with a *Try it out* button per operation. The previous
default — still shipped, and one line away if you prefer it.

###  ReDoc

```python
ReDoc(path="/redoc")
```

Three-column reference layout. Read-only — no request execution — which
makes it the better choice for a published reference.

###  Scalar

```python
Scalar(path="/reference", theme="purple")
```

A modern reference with a built-in client. `theme` takes Scalar's palette
names: `"default"`, `"alternate"`, `"moon"`, `"purple"`, `"solarized"`.

##  Configuring a viewer

Each presenter takes a `ui_config` dict that is passed through to the
viewer's own initialization, so options sillo has never heard of still
work:

```python
Atlas(theme="dark", ui_config={"deepLinking": False})

Swagger(ui_config={
    "persistAuthorization": True,   # keep the bearer token across reloads
    "docExpansion": "none",         # collapse everything by default
    "filter": True,                 # show the search box
    "tryItOutEnabled": True,
})

ReDoc(ui_config={"hideDownloadButton": True, "expandResponses": "200,201"})

Scalar(theme="moon", ui_config={"hideDownloadButton": True})
```

`url` and `dom_id` are set by the presenter and cannot be overridden —
replacing them only ever produces a page that loads the viewer and shows
nothing.

###  Title and favicon

```python
Atlas(title="Myapp — Internal API", favicon_url="/static/favicon.svg")
Atlas(favicon_url=None)                      # no icon at all
```

`title` defaults to the API title, so `silloApp(title="Myapp")` already
names the tab correctly. The favicon defaults to sillo's own, and its
media type follows the file extension — an `.svg` is labelled
`image/svg+xml` rather than handed to the browser as a PNG.

##  Self-hosting the assets

Every viewer loads its JavaScript from a public CDN by default. Override
the URLs to serve them yourself:

```python
Atlas(js_url="/static/atlas.standalone.js")
Swagger(
    js_url="/static/swagger-ui-bundle.js",
    css_url="/static/swagger-ui.css",
)
ReDoc(js_url="/static/redoc.standalone.js")
Scalar(js_url="/static/scalar.js")
```

This is what a deployment with no outbound network needs, and what a
strict `Content-Security-Policy` needs — a policy without
`script-src https://unpkg.com` blocks the default page, and the symptom is
a blank viewer rather than an error.

It also pins the version. `redoc/latest` is whatever ReDoc shipped this
morning.

##  Several viewers, or the same one twice

Nothing stops you mounting one presenter more than once with different
configuration:

```python
app = silloApp(docs=[
    Swagger(path="/docs", title="API"),
    Swagger(path="/internal/docs", ui_config={"tryItOutEnabled": True}),
    ReDoc(path="/reference"),
])
```

Two presenters claiming the same path raise `ValueError` at construction
rather than letting one silently shadow the other.

##  Writing your own

A presenter is a class with a `path` and a `render(ctx)`. That is the
entire contract — no registration call, no entry point:

```python
from sillo.openapi.ui import DocsUI, DocsContext


class RapiDoc(DocsUI):
    path = "/rapidoc"
    name = "rapidoc"

    def render(self, ctx: DocsContext) -> str:
        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{ctx.title}</title>
    <script src="https://unpkg.com/rapidoc/dist/rapidoc-min.js"></script>
</head>
<body>
    <rapi-doc spec-url="{ctx.openapi_url}" theme="dark"></rapi-doc>
</body>
</html>"""


app = silloApp(docs=[RapiDoc()])
```

Subclassing `DocsUI` gets you the `path`/`title`/`favicon_url` handling
for free, but it is not required — any object with those two attributes
is accepted. Anything else raises `TypeError` at construction, naming
what it got.

###  What `render` receives

| Field | |
| --- | --- |
| `ctx.openapi_url` | Path to the document, **already prefixed with `root_path`** |
| `ctx.title` | API title from the OpenAPI `info` block |
| `ctx.version` | API version |
| `ctx.description` | API description, or `""` |
| `ctx.config` | The full `OpenAPIConfig`, for anything else |

<aside type="caution">

**Use `ctx.openapi_url`; do not build the URL yourself.** When the
application is mounted under a prefix, the document is at
`/api/v1/openapi.json`, not `/openapi.json`. A page that hardcodes the
latter renders an empty viewer with nothing in the console to explain it.

</aside>

##  Looking a viewer up

```python
swagger = app.get_docs_ui("swagger")
if swagger is not None:
    print(swagger.path)
```

Returns `None` when that viewer is not mounted, which is the useful case
— a health check or a startup log that reports where the docs are.

##  Migrating from `swagger_docs` and `redoc_docs`

The old arguments still work and still move the pages:

```python
app = silloApp(swagger_docs="/api-docs", redoc_docs="/api-redoc")
```

They are deprecated in favour of `docs`. Combining the two raises
`TypeError` rather than silently preferring one:

```python
silloApp(swagger_docs="/api-docs", docs=[Scalar()])
# TypeError: docs= cannot be combined with swagger_docs; set the path on
# the presenter instead, e.g. docs=[Swagger(path='/api-docs')]
```

The argument is still named `swagger_docs` because it predates there being
a choice of viewer; it now sets the path of whatever sits at `/docs`.

The translation is direct:

| Before | After |
| --- | --- |
| `swagger_docs="/api-docs"` | `docs=[Atlas(path="/api-docs"), ReDoc()]` |
| `redoc_docs="/api-redoc"` | `docs=[Swagger(), ReDoc(path="/api-redoc")]` |
| — no equivalent — | `docs=[]` |

Note the last row: turning the viewers off is something the old arguments
could not express at all.

##  Things that will bite you

1. **`docs=[]` does not hide `/openapi.json`.** The schema is a separate
   route with a separate setting.

2. **A strict CSP blocks the default CDN scripts**, and the failure is a
   blank page. Self-host the assets, or allow the CDN explicitly.

3. **Build the document URL from `ctx.openapi_url`** in a custom
   presenter, or the page breaks under a mount prefix and nowhere else.

4. **Duplicate paths raise at construction**, so a typo in one presenter's
   path surfaces at import rather than as the wrong viewer at runtime.

5. **`redoc/latest` and `swagger-ui-dist@5` float.** Pin them through
   `js_url` if you need the page to look the same next month. Atlas is
   already pinned to a released tag.

##  Related

- [OpenAPI Overview](/guides/openapi/) — how the document is generated
- [OpenAPI Customization](/guides/openapi/customizing-openapi-configuration/) — title, servers, security schemes
- [Static Files](/guides/static-files/) — serving self-hosted viewer assets
- [Protecting Routes](/guides/protecting-routes/) — putting the schema behind auth
