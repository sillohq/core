"""
Content negotiation middleware and the per-request Accepts helpers.

The negotiation functions themselves are covered in test_accepts_negotiation;
this exercises them through a live request, including the strict variant that
rejects clients it cannot satisfy with a 406.
"""

import pytest

from sillo import SilloApp
from sillo import json
from sillo.http.accepts import (
    Accepts,
    AcceptsInfo,
    AcceptsMiddleware,
    ContentNegotiationMiddleware,
    StrictContentNegotiationMiddleware,
    get_accepted_content_types,
    get_accepted_charsets,
    get_accepted_encodings,
    get_accepted_languages,
    get_accepts_from_request,
    get_accepts_info,
    get_best_accepted_content_type,
    get_best_accepted_language,
)
from sillo.testclient import TestClient


# ── AcceptsInfo over a live request ──────────────────────────────────────


@pytest.fixture
def client():
    app = SilloApp()

    @app.get("/info")
    async def info(ctx):
        return json(get_accepts_info(ctx))

    @app.get("/types")
    async def types(ctx):
        return json(
            {
                "types": get_accepted_content_types(ctx),
                "languages": get_accepted_languages(ctx),
                "charsets": get_accepted_charsets(ctx),
                "encodings": get_accepted_encodings(ctx),
            }
        )

    @app.get("/best")
    async def best(ctx):
        return json(
            {
                "type": get_best_accepted_content_type(
                    ctx, ["application/json", "text/html"]
                ),
                "language": get_best_accepted_language(ctx, ["en", "fr"]),
            }
        )

    @app.get("/wrapper")
    async def wrapper(ctx):
        accepts = get_accepts_from_request(ctx)
        return json({"has_accepts": accepts is not None})

    # These helpers read state the middleware attaches to the request.
    app.use(AcceptsMiddleware())
    return TestClient(app)


def test_accepts_info_is_a_dict(client):
    resp = client.get("/info", headers={"Accept": "application/json"})
    assert isinstance(resp.json(), dict)


def test_accepted_types_are_listed(client):
    resp = client.get(
        "/types",
        headers={
            "Accept": "application/json, text/html;q=0.8",
            "Accept-Language": "en, fr;q=0.5",
            "Accept-Charset": "utf-8",
            "Accept-Encoding": "gzip",
        },
    )
    data = resp.json()
    assert "application/json" in data["types"]
    assert "en" in data["languages"]


def test_missing_accept_headers_yield_empty_lists(client):
    data = client.get("/types").json()
    assert isinstance(data["types"], list)


def test_best_match_through_a_request(client):
    resp = client.get(
        "/best",
        headers={"Accept": "text/html", "Accept-Language": "fr"},
    )
    data = resp.json()
    assert data["type"] == "text/html"
    assert data["language"] == "fr"


def test_the_accepts_wrapper_is_available(client):
    assert client.get("/wrapper").json()["has_accepts"] is True


# ── AcceptsInfo directly ─────────────────────────────────────────────────


def test_accepts_info_exposes_each_header():
    app = SilloApp()
    captured = {}

    @app.get("/x")
    async def x(ctx):
        info = AcceptsInfo(ctx)
        captured["accept"] = info.accept
        captured["language"] = info.accept_language
        captured["charset"] = info.accept_charset
        captured["encoding"] = info.accept_encoding
        captured["types"] = info.get_accepted_types()
        captured["languages"] = info.get_accepted_languages()
        captured["charsets"] = info.get_accepted_charsets()
        captured["encodings"] = info.get_accepted_encodings()
        return json({})

    app.use(AcceptsMiddleware())
    TestClient(app).get(
        "/x",
        headers={
            "Accept": "application/json",
            "Accept-Language": "en",
            "Accept-Charset": "utf-8",
            "Accept-Encoding": "gzip",
        },
    )

    # With the middleware installed, `accept` is the parsed header rather
    # than the raw string.
    assert [i.value for i in captured["accept"]] == ["application/json"]
    assert "application/json" in captured["types"]
    assert "en" in captured["languages"]
    assert "utf-8" in captured["charsets"]
    assert "gzip" in captured["encodings"]


# ── AcceptsMiddleware ────────────────────────────────────────────────────


def _app_with(middleware):
    app = SilloApp()

    @app.get("/x")
    async def x(ctx):
        return json({"ok": True})

    app.use(middleware)
    return TestClient(app)


def test_accepts_middleware_passes_requests_through():
    client = _app_with(AcceptsMiddleware())
    assert client.get("/x", headers={"Accept": "application/json"}).status_code == 200


def test_accepts_middleware_sets_vary():
    client = _app_with(AcceptsMiddleware(set_vary_header=True))
    resp = client.get("/x", headers={"Accept": "application/json"})
    assert "vary" in {k.lower() for k in resp.headers}


def test_accepts_middleware_can_omit_vary():
    client = _app_with(AcceptsMiddleware(set_vary_header=False))
    assert client.get("/x").status_code == 200


def test_accepts_middleware_with_custom_defaults():
    client = _app_with(
        AcceptsMiddleware(
            default_content_type="text/html",
            default_language="fr",
            default_charset="iso-8859-1",
        )
    )
    assert client.get("/x").status_code == 200


def test_accepts_middleware_without_an_accept_header():
    client = _app_with(AcceptsMiddleware())
    assert client.get("/x").status_code == 200


# ── ContentNegotiationMiddleware ─────────────────────────────────────────


def test_content_negotiation_passes_requests_through():
    client = _app_with(ContentNegotiationMiddleware())
    assert client.get("/x", headers={"Accept": "application/json"}).status_code == 200


def test_content_negotiation_with_a_wildcard():
    client = _app_with(ContentNegotiationMiddleware())
    assert client.get("/x", headers={"Accept": "*/*"}).status_code == 200


# ── StrictContentNegotiationMiddleware ───────────────────────────────────


def test_strict_negotiation_accepts_a_supported_type():
    client = _app_with(
        StrictContentNegotiationMiddleware(available_types=["application/json"])
    )
    assert client.get("/x", headers={"Accept": "application/json"}).status_code == 200


def test_strict_negotiation_rejects_an_unsupported_type():
    """A client that cannot consume any representation we offer gets 406.

    Note the endpoint must not offer the default content type, or negotiation
    falls back onto it and the request is served after all.
    """
    client = _app_with(
        StrictContentNegotiationMiddleware(available_types=["text/csv"])
    )
    resp = client.get("/x", headers={"Accept": "application/xml"})
    assert resp.status_code == 406
    assert "text/csv" in resp.text


def test_strict_negotiation_honours_a_wildcard():
    client = _app_with(
        StrictContentNegotiationMiddleware(available_types=["application/json"])
    )
    assert client.get("/x", headers={"Accept": "*/*"}).status_code == 200


def test_strict_negotiation_checks_language_too():
    client = _app_with(
        StrictContentNegotiationMiddleware(
            available_types=["application/json"], available_languages=["en"]
        )
    )
    resp = client.get(
        "/x", headers={"Accept": "application/json", "Accept-Language": "en"}
    )
    assert resp.status_code == 200


def test_strict_negotiation_with_no_accept_header():
    client = _app_with(
        StrictContentNegotiationMiddleware(available_types=["application/json"])
    )
    assert client.get("/x").status_code in (200, 406)


# ── the Accepts factory ──────────────────────────────────────────────────


def test_accepts_factory_builds_a_middleware():
    assert Accepts() is not None


def test_accepts_factory_takes_defaults():
    assert Accepts(default_content_type="text/html", default_language="fr") is not None
