"""Replacing headers rather than appending them.

``set_header`` and ``set_headers`` accept ``override`` and ``override_all``
to replace existing headers instead of appending duplicates.
"""

from __future__ import annotations

import warnings

import pytest

from sillo.core.http import HttpContext
from sillo.core.http.response import BaseResponse


def header_keys(response: BaseResponse) -> list[str]:
    return [key.decode("latin-1") for key, _ in response.raw_headers]


def header_values(response: BaseResponse, name: str) -> list[str]:
    return [
        value.decode("latin-1")
        for key, value in response.raw_headers
        if key.decode("latin-1") == name
    ]


def make_responder() -> Responder:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "query_string": b"",
    }
    responder = Responder(HttpContext(scope, None))
    responder.empty()
    return responder


class TestTheCorrectSpelling:
    def test_override_replaces_the_existing_header(self):
        response = BaseResponse()
        response.set_header("x-thing", "first")
        response.set_header("x-thing", "second", override=True)

        assert header_values(response, "x-thing") == ["second"]

    def test_without_override_the_header_is_appended(self):
        """The default is deliberate: ``Set-Cookie`` and ``Vary`` are
        legitimately repeated."""
        response = BaseResponse()
        response.set_header("x-thing", "first")
        response.set_header("x-thing", "second")

        assert header_values(response, "x-thing") == ["first", "second"]

    def test_override_all_replaces_every_header(self):
        response = BaseResponse()
        response.set_header("x-one", "1")
        response.set_header("x-two", "2")
        response.set_headers({"x-three": "3"}, override_all=True)

        assert header_keys(response) == ["x-three"]

    def test_the_correct_spelling_warns_about_nothing(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            response = BaseResponse()
            response.set_header("x", "1", override=True)
            response.set_headers({"y": "2"}, override_all=True)

        assert [w for w in caught if w.category is DeprecationWarning] == []


class TestPositionalCallersWereNeverAffected:
    """The flag has always been the third positional parameter, so renaming
    it could only ever break callers who named it."""

    def test_set_header_positionally(self):
        response = BaseResponse()
        response.set_header("x-thing", "first")
        response.set_header("x-thing", "second", True)

        assert header_values(response, "x-thing") == ["second"]

    def test_set_headers_positionally(self):
        response = BaseResponse()
        response.set_header("x-one", "1")
        response.set_headers({"x-two": "2"}, True)

        assert header_keys(response) == ["x-two"]


class TestResponder:
    """The Responder wrapper forwards to the underlying response, and used to
    drop the flag on the way."""

    def test_override_replaces_through_the_responder(self):
        responder = make_responder()
        responder.set_header("x-thing", "first")
        responder.set_header("x-thing", "second", override=True)

        assert header_values(responder, "x-thing") == ["second"]

    def test_override_all_replaces_through_the_responder(self):
        """The bug this covers: ``set_headers(headers, override_all=True)``
        called the inner ``set_headers(headers)`` without the flag, so the
        inner call took its *appending* branch. Asking a Responder to replace
        every header added to them instead, and the originals survived
        alongside the replacements.
        """
        responder = make_responder()
        responder.set_header("x-one", "1")
        responder.set_header("x-two", "2")
        responder.set_headers({"x-three": "3"}, override_all=True)

        assert header_keys(responder) == ["x-three"]

    def test_without_override_all_the_responder_appends(self):
        responder = make_responder()
        responder.set_header("x-one", "1")
        responder.set_headers({"x-two": "2"})

        keys = header_keys(responder)
        assert "x-one" in keys
        assert "x-two" in keys


class TestTheSourceUsesTheCorrectSpelling:
    """The framework must not trip its own deprecation warning."""

    def test_no_internal_call_site_uses_the_misspelling(self):
        """Read the syntax, not the text.

        Only an actual keyword argument in a call counts.
        """
        import ast
        from pathlib import Path

        package = Path(__file__).resolve().parents[2] / "sillo"
        offenders = []

        for path in package.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                for keyword in node.keywords:
                    if keyword.arg in ("overide", "overide_all"):
                        offenders.append(
                            f"{path.relative_to(package.parent)}:{node.lineno}"
                        )

        assert not offenders, (
            "these call sites still pass the misspelled keyword, so sillo "
            f"raises its own DeprecationWarning at users: {offenders}"
        )

    def test_the_scan_reads_real_files(self):
        from pathlib import Path

        package = Path(__file__).resolve().parents[2] / "sillo"
        assert len(list(package.rglob("*.py"))) > 50
