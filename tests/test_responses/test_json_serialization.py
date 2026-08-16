"""How ``JSONResponse`` turns content into JSON.

Two things changed here and both are easy to regress silently.

The response is now compact — no space after ``,`` or ``:`` — which is 11.5%
fewer bytes on a typical payload and matches what the websocket path already
did. And ``jsonable_encoder`` is no longer run up front: content that the
standard library can serialize on its own is serialized once instead of being
rebuilt node by node and then serialized. Anything it cannot is converted
exactly as before.

The tests below therefore care about two properties. The *data* must be
identical whichever path a payload takes — a fast path that quietly renders an
enum differently from the slow one would be a bug nobody notices until it is in
somebody's API. And the bytes must stay compact, because that is the part a
future edit would undo without any test failing on meaning.
"""

from __future__ import annotations

import datetime
import decimal
import enum
import json
import uuid

import pytest

from sillo.core.http.response import JSONResponse


class Colour(str, enum.Enum):
    RED = "red"


class Code(int, enum.Enum):
    OK = 200


def render(content, **kwargs) -> str:
    """Serialize *content* the way a response would."""
    return JSONResponse._serialize(
        content,
        kwargs.get("indent"),
        kwargs.get("ensure_ascii", True),
        kwargs.get("use_encoder", True),
        kwargs.get("custom_encoder"),
    )


def render_via_encoder(content) -> str:
    """Serialize by the slow path, which is what a custom encoder forces.

    Used as the reference: whatever the fast path produces has to mean the
    same as this.
    """
    return JSONResponse._serialize(content, None, True, True, {})


class TestTheOutputIsCompact:
    def test_no_space_after_a_separator(self):
        assert render({"a": 1, "b": 2}) == '{"a":1,"b":2}'

    def test_lists_too(self):
        assert render([1, 2, 3]) == "[1,2,3]"

    def test_a_realistic_payload_is_meaningfully_smaller(self):
        rows = {
            "data": [
                {"id": i, "title": f"Document {i}", "author": {"id": i % 7}}
                for i in range(200)
            ]
        }
        compact = render(rows)
        spaced = json.dumps(json.loads(compact))

        assert len(compact) < len(spaced)
        # The saving is the point; a token one would not be worth the change.
        assert 1 - len(compact) / len(spaced) > 0.10

    def test_indentation_is_still_readable_when_asked_for(self):
        # Compactness is the default, not a policy: someone who passed indent
        # wants it legible.
        rendered = render({"a": 1, "b": 2}, indent=2)

        assert "\n" in rendered
        assert ": " in rendered


class TestBothPathsAgree:
    """The fast path must never mean something different from the slow one."""

    @pytest.mark.parametrize(
        ("name", "payload"),
        [
            ("plain", {"a": 1, "b": [1, 2], "c": None, "d": True}),
            ("nested", {"data": [{"id": i, "x": {"y": i}} for i in range(3)]}),
            ("empty dict", {}),
            ("empty list", []),
            ("list at the root", [1, 2, 3]),
            ("unicode", {"name": "café ☕"}),
            ("str enum", {"colour": Colour.RED}),
            ("int enum", {"code": Code.OK}),
            ("non-string keys", {1: "one"}),
            ("tuple", {"pair": (1, 2)}),
            ("nested empties", {"a": {}, "b": [], "c": [{}]}),
            ("deep nesting", {"a": {"b": {"c": {"d": [1, {"e": 2}]}}}}),
        ],
    )
    def test_the_same_data_comes_out(self, name, payload):
        assert json.loads(render(payload)) == json.loads(render_via_encoder(payload))


class TestContentTheEncoderIsStillNeededFor:
    """These do not survive `json.dumps` alone, so they take the slow path."""

    def test_a_datetime_is_converted(self):
        rendered = render({"at": datetime.datetime(2026, 8, 16, 12, 30)})

        assert "2026" in rendered
        assert json.loads(rendered)["at"]

    def test_a_uuid_is_converted(self):
        identifier = uuid.UUID("12345678-1234-5678-1234-567812345678")

        assert str(identifier) in render({"id": identifier})

    def test_a_decimal_is_converted(self):
        assert "12.5" in render({"amount": decimal.Decimal("12.50")})

    def test_a_set_becomes_a_list(self):
        rendered = json.loads(render({"tags": {"a"}}))

        assert rendered == {"tags": ["a"]}

    def test_a_date_is_converted(self):
        assert "2026-08-16" in render({"on": datetime.date(2026, 8, 16)})


class TestOptionsAreHonoured:
    def test_ensure_ascii_false_keeps_the_characters(self):
        assert "café" in render({"n": "café"}, ensure_ascii=False)

    def test_ensure_ascii_true_escapes_them(self):
        assert "caf\\u00e9" in render({"n": "café"})

    def test_use_encoder_false_skips_conversion(self):
        # `default=str` is the whole contract of this flag.
        rendered = render({"at": datetime.datetime(2026, 8, 16)}, use_encoder=False)

        assert json.loads(rendered)["at"].startswith("2026-08-16")

    def test_a_custom_encoder_wins_over_the_fast_path(self):
        # The subtle one. A custom encoder for a type the standard library can
        # already serialize would be skipped entirely if the fast path ran
        # first, and the caller's rendering would silently not happen.
        rendered = render(
            {"n": 5}, custom_encoder={int: lambda value: f"<{value}>"}
        )

        assert json.loads(rendered)["n"] == "<5>"


class TestFailuresAreUnchanged:
    def test_nan_is_refused(self):
        with pytest.raises(ValueError, match="not JSON serializable"):
            JSONResponse({"x": float("nan")})

    def test_infinity_is_refused(self):
        with pytest.raises(ValueError, match="not JSON serializable"):
            JSONResponse({"x": float("inf")})

    def test_something_nothing_can_render_is_refused(self):
        with pytest.raises(ValueError, match="not JSON serializable"):
            JSONResponse({"x": object()})

    def test_a_circular_structure_does_not_hang(self):
        circular: dict = {}
        circular["self"] = circular

        with pytest.raises((ValueError, RecursionError)):
            JSONResponse(circular)


class TestThroughTheResponse:
    """The same properties, from the outside."""

    def test_the_body_is_compact(self):
        assert JSONResponse({"a": 1, "b": 2}).body == b'{"a":1,"b":2}'

    def test_the_content_type_is_still_json(self):
        response = JSONResponse({"a": 1})

        assert response.headers["content-type"] == "application/json"

    def test_a_status_code_passes_through(self):
        assert JSONResponse({"a": 1}, status_code=201).status_code == 201
