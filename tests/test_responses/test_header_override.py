"""Replacing headers rather than appending them.

``set_header`` and ``set_headers`` shipped with the flag spelled ``overide``
-- one 'r' short -- on four response classes and throughout the published
documentation. The correct spelling is now the real parameter and the
misspelling is a deprecated keyword alias.

The alias is not politeness. The flag exists to *replace* a header, and the
failure mode of losing it is a duplicate ``Content-Type`` or two
``Access-Control-Allow-Origin`` values, which no client reports and no test
notices until something downstream picks the wrong one.
"""

from __future__ import annotations

import warnings

import pytest

from sillo.core.http import Request
from sillo.core.http.response import BaseResponse, Responder


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
    responder = Responder(Request(scope, None))
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


class TestTheDeprecatedSpelling:
    def test_overide_still_replaces(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            response = BaseResponse()
            response.set_header("x-thing", "first")
            response.set_header("x-thing", "second", overide=True)

        assert header_values(response, "x-thing") == ["second"]

    def test_overide_all_still_replaces(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            response = BaseResponse()
            response.set_header("x-one", "1")
            response.set_headers({"x-two": "2"}, overide_all=True)

        assert header_keys(response) == ["x-two"]

    def test_overide_false_is_honoured_rather_than_ignored(self):
        """``overide=False`` is a real answer, not an absent one.

        Reading the alias as "unset when falsy" would silently upgrade an
        explicit False to the correct parameter's default -- which happens to
        be the same here, and would not be if the default ever changed.
        """
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            response = BaseResponse()
            response.set_header("x-thing", "first")
            response.set_header("x-thing", "second", overide=False)

        assert header_values(response, "x-thing") == ["first", "second"]

    def test_using_it_warns(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            BaseResponse().set_header("x", "1", overide=True)

        deprecations = [w for w in caught if w.category is DeprecationWarning]
        assert len(deprecations) == 1

    def test_the_warning_names_both_spellings(self):
        """A deprecation that does not say what to write instead is a
        nuisance rather than a migration path."""
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            BaseResponse().set_header("x", "1", overide=True)

        message = str(caught[-1].message)
        assert "overide" in message
        assert "override" in message

    def test_the_warning_points_at_the_caller(self):
        """``stacklevel`` has to reach past the helper *and* the method, or
        the warning names a line inside sillo and tells the user nothing."""
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            BaseResponse().set_header("x", "1", overide=True)

        assert caught[-1].filename == __file__


class TestResponder:
    """The Responder wrapper forwards to the underlying response, and used to
    drop the flag on the way."""

    def test_override_replaces_through_the_responder(self):
        responder = make_responder()
        responder.set_header("x-thing", "first")
        responder.set_header("x-thing", "second", override=True)

        assert header_values(responder.get_response(), "x-thing") == ["second"]

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

        assert header_keys(responder.get_response()) == ["x-three"]

    def test_the_deprecated_spelling_works_through_the_responder(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            responder = make_responder()
            responder.set_header("x-thing", "first")
            responder.set_header("x-thing", "second", overide=True)

        assert header_values(responder.get_response(), "x-thing") == ["second"]

    def test_without_override_all_the_responder_appends(self):
        responder = make_responder()
        responder.set_header("x-one", "1")
        responder.set_headers({"x-two": "2"})

        keys = header_keys(responder.get_response())
        assert "x-one" in keys
        assert "x-two" in keys


class TestTheSourceUsesTheCorrectSpelling:
    """The framework must not trip its own deprecation warning."""

    def test_no_internal_call_site_uses_the_misspelling(self):
        """Read the syntax, not the text.

        A regex over lines also matches the shim's own docstring, which quotes
        ``overide=True`` in order to explain it. Only an actual keyword
        argument in a call counts.
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
