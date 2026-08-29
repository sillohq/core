"""``sillo.responses`` — the public home of every response builder.

The helpers themselves are exercised through routes all over this suite; what
is pinned here is the module's own contract: what it exports, that the root
package re-exports the same objects, and the behaviour of the builders that no
other test reaches — the status shorthands, the named redirects, ``raw``,
``xml`` and ``ndjson``.
"""

from typing import Callable

import pytest

import sillo
from sillo import SilloApp, responses
from sillo.core.http import HttpContext
from sillo.core.http.response import (
    BaseResponse,
    FileResponse,
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    StreamingResponse,
)
from sillo.exceptions import HTTPException, NotFoundException
from sillo.testclient import TestClient


class TestTheModuleSurface:
    """What ``sillo.responses`` promises to export."""

    def test_every_name_in_all_actually_exists(self):
        missing = [name for name in responses.__all__ if not hasattr(responses, name)]
        assert missing == []

    def test_the_response_classes_are_re_exported(self):
        """A handler may build one directly, or subclass it."""
        assert responses.BaseResponse is BaseResponse
        assert responses.JSONResponse is JSONResponse
        assert responses.PlainTextResponse is PlainTextResponse
        assert responses.HTMLResponse is HTMLResponse
        assert responses.FileResponse is FileResponse
        assert responses.StreamingResponse is StreamingResponse
        assert responses.RedirectResponse is RedirectResponse

    @pytest.mark.parametrize(
        "name",
        [
            "json",
            "text",
            "html",
            "xml",
            "raw",
            "empty",
            "created",
            "accepted",
            "no_content",
            "redirect",
            "permanent_redirect",
            "see_other",
            "temporary_redirect",
            "file",
            "download",
            "stream",
            "ndjson",
            "sse",
            "paginate",
            "apaginate",
            "abort",
            "not_found",
        ],
    )
    def test_the_root_package_re_exports_the_same_object(self, name):
        """``from sillo import json`` and ``from sillo.responses import json``
        must not be two different functions."""
        assert getattr(sillo, name) is getattr(responses, name)
        assert name in sillo.__all__


class TestBodies:
    def test_json_serializes_and_sets_the_content_type(self):
        r = responses.json({"a": 1})
        assert r.status_code == 200
        assert r.body == b'{"a":1}'
        assert "application/json" in r.headers["content-type"]

    def test_json_can_pretty_print(self):
        assert responses.json({"a": 1}, indent=2).body == b'{\n  "a": 1\n}'

    def test_text_is_text_plain(self):
        r = responses.text("hello")
        assert r.body == b"hello"
        assert "text/plain" in r.headers["content-type"]

    def test_html_is_text_html(self):
        r = responses.html("<b>hi</b>")
        assert r.body == b"<b>hi</b>"
        assert "text/html" in r.headers["content-type"]

    def test_xml_defaults_to_application_xml(self):
        r = responses.xml("<a/>")
        assert r.body == b"<a/>"
        assert r.headers["content-type"] == "application/xml"

    def test_xml_takes_a_more_specific_type(self):
        r = responses.xml("<svg/>", content_type="image/svg+xml")
        assert r.headers["content-type"] == "image/svg+xml"

    def test_raw_sends_bytes_under_the_type_you_name(self):
        r = responses.raw(b"\x00\x01", content_type="application/protobuf")
        assert r.body == b"\x00\x01"
        assert r.headers["content-type"] == "application/protobuf"

    def test_raw_defaults_to_octet_stream(self):
        assert responses.raw(b"x").headers["content-type"] == "application/octet-stream"

    def test_empty_is_a_204_with_no_body(self):
        r = responses.empty()
        assert r.status_code == 204
        assert r.body == b""

    def test_empty_takes_another_status(self):
        assert responses.empty(304).status_code == 304


class TestStatusShorthands:
    def test_created_is_201_with_the_representation(self):
        r = responses.created({"id": 7})
        assert r.status_code == 201
        assert r.body == b'{"id":7}'

    def test_created_sets_location_when_given_one(self):
        r = responses.created({"id": 7}, location="/items/7")
        assert r.headers["location"] == "/items/7"

    def test_created_without_a_body_is_still_201(self):
        r = responses.created(location="/items/7")
        assert r.status_code == 201
        assert r.body == b""
        assert r.headers["location"] == "/items/7"

    def test_accepted_is_202(self):
        r = responses.accepted({"job": "abc"})
        assert r.status_code == 202
        assert r.body == b'{"job":"abc"}'

    def test_accepted_without_a_body_is_still_202(self):
        r = responses.accepted()
        assert r.status_code == 202
        assert r.body == b""

    def test_no_content_is_204(self):
        r = responses.no_content()
        assert r.status_code == 204
        assert r.body == b""


class TestRedirects:
    def test_redirect_defaults_to_302(self):
        r = responses.redirect("/there")
        assert r.status_code == 302
        assert r.headers["location"] == "/there"

    def test_permanent_redirect_is_301_by_default(self):
        """301 lets a client turn the repeated request into a GET, which is
        what a moved page wants."""
        assert responses.permanent_redirect("/there").status_code == 301

    def test_permanent_redirect_can_preserve_the_method(self):
        """308 is the one that repeats the method and body as-is."""
        r = responses.permanent_redirect("/there", preserve_method=True)
        assert r.status_code == 308

    def test_see_other_is_303(self):
        """The post/redirect/get answer: follow this with a GET."""
        assert responses.see_other("/there").status_code == 303

    def test_temporary_redirect_is_307(self):
        assert responses.temporary_redirect("/there").status_code == 307

    def test_a_non_redirect_status_is_rejected(self):
        with pytest.raises(ValueError):
            responses.redirect("/there", status_code=200)


class TestNdjson:
    async def _collect(self, response) -> list[bytes]:
        return [chunk async for chunk in response.content_iterator]

    async def test_each_object_is_one_line(self):
        async def source():
            yield {"n": 1}
            yield {"n": 2}

        r = responses.ndjson(source())
        assert r.headers["content-type"] == "application/x-ndjson"
        assert await self._collect(r) == ['{"n":1}\n', '{"n":2}\n']

    async def test_strings_are_sent_as_they_are(self):
        """An already-encoded line is not double-encoded."""

        async def source():
            yield '{"pre":"encoded"}'

        assert await self._collect(responses.ndjson(source())) == [
            '{"pre":"encoded"}\n'
        ]

    async def test_a_custom_encoder_is_used(self):
        async def source():
            yield {"n": 1}

        r = responses.ndjson(source(), encoder=lambda item: f"n={item['n']}")
        assert await self._collect(r) == ["n=1\n"]

    async def test_types_json_cannot_take_are_encoded_for_you(self):
        """The framework encoder runs first, so a datetime does not raise."""
        from datetime import date

        async def source():
            yield {"on": date(2026, 1, 2)}

        assert await self._collect(responses.ndjson(source())) == [
            '{"on":"2026-01-02"}\n'
        ]


class TestStoppingEarly:
    def test_abort_raises_rather_than_returning(self):
        with pytest.raises(HTTPException) as exc_info:
            responses.abort(403, detail="Admins only")
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "Admins only"

    def test_abort_carries_its_headers(self):
        with pytest.raises(HTTPException) as exc_info:
            responses.abort(401, headers={"WWW-Authenticate": "Bearer"})
        assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}

    def test_not_found_raises_a_404(self):
        with pytest.raises(NotFoundException) as exc_info:
            responses.not_found(detail="no such widget")
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "no such widget"


class TestThroughARoute:
    """The builders reach the wire intact."""

    def test_the_new_builders_serve(
        self, test_client_factory: Callable[[SilloApp], TestClient]
    ):
        app = SilloApp()

        @app.post("/items")
        async def create_item(ctx: HttpContext):
            return responses.created({"id": 1}, location="/items/1")

        @app.post("/jobs")
        async def queue_job(ctx: HttpContext):
            return responses.accepted({"job": "j-1"})

        @app.delete("/items/{item_id:int}")
        async def delete_item(ctx: HttpContext, item_id: int):
            return responses.no_content()

        @app.get("/feed")
        async def feed(ctx: HttpContext):
            return responses.xml("<feed/>", content_type="application/atom+xml")

        @app.get("/blob")
        async def blob(ctx: HttpContext):
            return responses.raw(b"\x89PNG", content_type="image/png")

        @app.get("/old")
        async def old(ctx: HttpContext):
            return responses.permanent_redirect("/new")

        @app.post("/submit")
        async def submit(ctx: HttpContext):
            return responses.see_other("/thanks")

        with test_client_factory(app) as client:
            created_resp = client.post("/items")
            assert created_resp.status_code == 201
            assert created_resp.headers["location"] == "/items/1"
            assert created_resp.json() == {"id": 1}

            assert client.post("/jobs").status_code == 202

            deleted = client.delete("/items/1")
            assert deleted.status_code == 204
            assert deleted.content == b""

            feed_resp = client.get("/feed")
            assert feed_resp.headers["content-type"] == "application/atom+xml"
            assert feed_resp.text == "<feed/>"

            blob_resp = client.get("/blob")
            assert blob_resp.headers["content-type"] == "image/png"
            assert blob_resp.content == b"\x89PNG"

            moved = client.get("/old", follow_redirects=False)
            assert moved.status_code == 301
            assert moved.headers["location"] == "/new"

            other = client.post("/submit", follow_redirects=False)
            assert other.status_code == 303

    def test_ndjson_streams_every_line(
        self, test_client_factory: Callable[[SilloApp], TestClient]
    ):
        app = SilloApp()

        @app.get("/export")
        async def export(ctx: HttpContext):
            async def rows():
                for n in range(3):
                    yield {"n": n}

            return responses.ndjson(rows())

        with test_client_factory(app) as client:
            resp = client.get("/export")
            assert resp.status_code == 200
            assert resp.headers["content-type"] == "application/x-ndjson"
            assert resp.text.splitlines() == ['{"n":0}', '{"n":1}', '{"n":2}']
