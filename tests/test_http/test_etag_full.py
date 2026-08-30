"""``sillo.http.etag`` — ETag generation, parsing, comparison and the middleware.

The parsing and comparison helpers are where conditional requests go wrong, and
they are pure functions, so they are tested directly rather than through a
request. The middleware is driven end to end.
"""

import pytest

from sillo import SilloApp
from sillo import json
from sillo.core.http import HttpContext
from sillo.http.etag import (
    ETag,
    ETagMiddleware,
    _parse_etag_list,
    _response_body,
    compute_and_set_etag,
    etag_matches,
    generate_etag_from_bytes,
    is_fresh,
    normalize_etag,
)
from sillo.testclient import TestClient


class TestGenerating:
    def test_a_weak_tag_carries_the_prefix(self):
        assert generate_etag_from_bytes(b"body").startswith('W/"')

    def test_a_strong_tag_does_not(self):
        tag = generate_etag_from_bytes(b"body", weak=False)
        assert tag.startswith('"')
        assert not tag.startswith("W/")

    def test_the_same_bytes_give_the_same_tag(self):
        assert generate_etag_from_bytes(b"x") == generate_etag_from_bytes(b"x")

    def test_different_bytes_give_different_tags(self):
        assert generate_etag_from_bytes(b"x") != generate_etag_from_bytes(b"y")


class TestNormalising:
    def test_an_already_valid_strong_tag_is_unchanged(self):
        assert normalize_etag('"abc"') == '"abc"'

    def test_an_already_valid_weak_tag_is_unchanged(self):
        assert normalize_etag('W/"abc"') == 'W/"abc"'

    def test_a_bare_value_gains_quotes(self):
        assert normalize_etag("abc") == '"abc"'

    def test_a_weak_bare_value_gains_quotes_inside_the_prefix(self):
        assert normalize_etag("W/abc") == 'W/"abc"'

    def test_surrounding_whitespace_is_dropped(self):
        assert normalize_etag('  "abc"  ') == '"abc"'

    def test_whitespace_after_the_weak_prefix_is_left_alone(self):
        # _ETAG_TOKEN_RE permits `W/` followed by spaces, so the value already
        # matches and is returned untouched. Recorded as the current behaviour
        # rather than endorsed: weak comparison strips only the two-character
        # prefix, so `W/ "a"` and `"a"` do not compare equal.
        assert normalize_etag('W/  "abc"') == 'W/  "abc"'

    def test_an_unrepresentable_tag_is_refused(self):
        with pytest.raises(ValueError, match="Invalid ETag token"):
            normalize_etag('a"b')


class TestParsingHeaderLists:
    def test_a_missing_header_gives_an_empty_list(self):
        assert _parse_etag_list(None) == []

    def test_an_empty_header_gives_an_empty_list(self):
        assert _parse_etag_list("") == []

    def test_a_single_tag_is_parsed(self):
        assert _parse_etag_list('"abc"') == ['"abc"']

    def test_several_tags_are_parsed(self):
        assert _parse_etag_list('"a", "b"') == ['"a"', '"b"']

    def test_empty_entries_between_commas_are_skipped(self):
        assert _parse_etag_list('"a", , "b"') == ['"a"', '"b"']

    def test_an_unparseable_entry_is_skipped_rather_than_raising(self):
        assert _parse_etag_list('"a", x"y, "b"') == ['"a"', '"b"']

    def test_if_match_and_if_none_match_read_their_own_headers(self):
        from sillo.http.etag import parse_if_match, parse_if_none_match

        scope = {
            "type": "http", "method": "GET", "path": "/", "raw_path": b"/",
            "query_string": b"",
            "headers": [(b"if-match", b'"m"'), (b"if-none-match", b'"n"')],
            "client": ("127.0.0.1", 1), "server": ("t", 80),
            "scheme": "http", "http_version": "1.1", "root_path": "",
        }
        ctx = HttpContext(scope)

        assert parse_if_match(ctx) == ['"m"']
        assert parse_if_none_match(ctx) == ['"n"']


class TestMatching:
    def test_an_identical_tag_matches(self):
        assert etag_matches('"a"', ['"a"']) is True

    def test_a_different_tag_does_not(self):
        assert etag_matches('"a"', ['"b"']) is False

    def test_no_candidates_means_no_match(self):
        assert etag_matches('"a"', []) is False

    def test_an_invalid_subject_never_matches(self):
        assert etag_matches('a"b', ['"a"']) is False

    def test_an_invalid_candidate_is_skipped(self):
        assert etag_matches('"a"', ['x"y', '"a"']) is True

    def test_weak_comparison_ignores_the_prefix(self):
        assert etag_matches('W/"a"', ['"a"'], weak_compare=True) is True

    def test_strong_comparison_does_not(self):
        assert etag_matches('W/"a"', ['"a"'], weak_compare=False) is False

    def test_strong_comparison_still_matches_an_exact_pair(self):
        assert etag_matches('"a"', ['"a"'], weak_compare=False) is True


class TestFreshness:
    def _request(self, if_none_match=None):
        headers = []
        if if_none_match is not None:
            headers.append((b"if-none-match", if_none_match.encode()))
        return HttpContext(
            {
                "type": "http", "method": "GET", "path": "/", "raw_path": b"/",
                "query_string": b"", "headers": headers,
                "client": ("127.0.0.1", 1), "server": ("t", 80),
                "scheme": "http", "http_version": "1.1", "root_path": "",
            }
        )

    def test_a_response_with_no_etag_is_never_fresh(self):
        response = json({"a": 1})
        assert is_fresh(self._request('"a"'), response) is False

    def test_a_matching_client_tag_is_fresh(self):
        response = json({"a": 1})
        tag = compute_and_set_etag(response, b"body", override=True)
        assert is_fresh(self._request(tag), response) is True

    def test_a_non_matching_client_tag_is_not_fresh(self):
        response = json({"a": 1})
        compute_and_set_etag(response, b"body", override=True)
        assert is_fresh(self._request('"other"'), response) is False


class TestResponseBody:
    def test_bytes_pass_through(self):
        class R:
            body = b"abc"

        assert _response_body(R()) == b"abc"

    def test_a_memoryview_is_converted(self):
        class R:
            body = memoryview(b"abc")

        assert _response_body(R()) == b"abc"

    def test_a_string_is_encoded(self):
        class R:
            body = "abc"

        assert _response_body(R()) == b"abc"

    def test_an_unsupported_body_gives_none(self):
        class R:
            body = 42

        assert _response_body(R()) is None

    def test_a_missing_body_attribute_gives_none(self):
        class R:
            @property
            def body(self):
                raise AttributeError("no body here")

        assert _response_body(R()) is None


class TestMiddleware:
    def _app(self, **kwargs):
        app = SilloApp(debug=False)

        @app.get("/thing")
        async def thing(ctx: HttpContext):
            return json({"value": 1})

        @app.post("/thing")
        async def create(ctx: HttpContext):
            return json({"value": 1})

        app.use(ETagMiddleware(**kwargs))
        return app

    def test_a_get_response_gains_an_etag(self):
        with TestClient(self._app()) as client:
            assert "etag" in client.get("/thing").headers

    def test_the_etag_is_stable_across_requests(self):
        with TestClient(self._app()) as client:
            first = client.get("/thing").headers["etag"]
            assert client.get("/thing").headers["etag"] == first

    def test_a_matching_if_none_match_gets_304(self):
        with TestClient(self._app()) as client:
            tag = client.get("/thing").headers["etag"]
            conditional = client.get("/thing", headers={"If-None-Match": tag})

        assert conditional.status_code == 304
        # A 304 must not carry a body. This used to send the full original
        # body behind a `Content-Length: 0`, because the response being
        # mutated was a stream and `set_body` wrote a field it never reads.
        assert conditional.content == b""
        # The validator is one of the headers RFC 9110 requires a 304 to keep.
        assert conditional.headers["etag"] == tag

    def test_a_stale_if_none_match_gets_the_body(self):
        with TestClient(self._app()) as client:
            response = client.get("/thing", headers={"If-None-Match": '"stale"'})

        assert response.status_code == 200
        assert response.json() == {"value": 1}

    def test_a_method_outside_the_configured_set_is_untouched(self):
        with TestClient(self._app()) as client:
            assert "etag" not in client.post("/thing").headers

    def test_the_method_set_is_configurable(self):
        with TestClient(self._app(methods=("POST",))) as client:
            assert "etag" in client.post("/thing").headers

    def test_a_strong_tag_can_be_requested(self):
        with TestClient(self._app(weak=False)) as client:
            assert not client.get("/thing").headers["etag"].startswith("W/")

    def test_the_helper_builds_the_middleware(self):
        assert isinstance(ETag(), ETagMiddleware)
        assert ETag(weak=False).weak is False
        assert ETag(methods=("PUT",)).methods == ("PUT",)
        assert ETag(override=True).override is True
