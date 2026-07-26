"""
The URL, URLPath, and RouteParam datastructures.

These are pure datastructures with no request context, so they are exercised
directly rather than through a route.
"""

import pytest

from sillo.objects.routing import URL, RouteParam, URLPath


# ── URL components ───────────────────────────────────────────────────────


@pytest.fixture
def url():
    return URL("https://ada:secret@example.com:8443/a/b?x=1&y=2#frag")


def test_scheme(url):
    assert url.scheme == "https"


def test_netloc(url):
    assert url.netloc == "ada:secret@example.com:8443"


def test_path(url):
    assert url.path == "/a/b"


def test_query_excludes_the_question_mark(url):
    assert url.query == "x=1&y=2"


def test_fragment_excludes_the_hash(url):
    assert url.fragment == "frag"


def test_username(url):
    assert url.username == "ada"


def test_password(url):
    assert url.password == "secret"


def test_hostname_excludes_credentials_and_port(url):
    assert url.hostname == "example.com"


def test_port(url):
    assert url.port == 8443


def test_is_secure_for_https(url):
    assert url.is_secure is True


def test_is_secure_for_http():
    assert URL("http://example.com/").is_secure is False


def test_absent_components_are_none():
    plain = URL("http://example.com/path")
    assert plain.username is None
    assert plain.password is None
    assert plain.port is None
    assert plain.fragment == ""


def test_str_round_trips():
    raw = "https://example.com/a?b=1"
    assert str(URL(raw)) == raw


# ── URL mutation ─────────────────────────────────────────────────────────


def test_replace_swaps_a_component(url):
    assert URL("http://example.com/a").replace(scheme="https").scheme == "https"


def test_replace_returns_a_new_url(url):
    replaced = url.replace(path="/other")
    assert replaced is not url
    assert replaced.path == "/other"
    assert url.path == "/a/b", "the original must be untouched"


def test_include_query_params_adds_a_parameter():
    result = URL("http://example.com/a?x=1").include_query_params(y="2")
    assert "x=1" in result.query and "y=2" in result.query


def test_include_query_params_overrides_an_existing_one():
    result = URL("http://example.com/a?x=1").include_query_params(x="9")
    assert result.query == "x=9"


# ── URLPath ──────────────────────────────────────────────────────────────


def test_urlpath_is_a_string():
    p = URLPath("/items/1")
    assert isinstance(p, str)
    assert p == "/items/1"


def test_urlpath_make_absolute_url():
    absolute = URLPath("/items/1").make_absolute_url("http://example.com")
    assert str(absolute) == "http://example.com/items/1"


def test_urlpath_make_absolute_url_strips_a_trailing_slash():
    absolute = URLPath("/items").make_absolute_url("http://example.com/")
    assert str(absolute) == "http://example.com/items"


# ── RouteParam ───────────────────────────────────────────────────────────


@pytest.fixture
def params():
    return RouteParam({"id": "7", "tag": ["a", "b"]})


def test_getitem(params):
    assert params["id"] == "7"


def test_get_with_a_default(params):
    assert params.get("missing", "fallback") == "fallback"


def test_get_returns_none_by_default(params):
    assert params.get("missing") is None


def test_keys_values_items(params):
    assert set(params.keys()) == {"id", "tag"}
    assert "7" in list(params.values())
    assert ("id", "7") in list(params.items())


def test_len(params):
    assert len(params) == 2


def test_iteration(params):
    assert set(iter(params)) == {"id", "tag"}


def test_get_lists_returns_every_pair(params):
    """Despite the name, this is an alias for items(), not a per-key lookup."""
    assert ("tag", ["a", "b"]) in list(params.get_lists())


def test_attribute_access(params):
    assert params.id == "7"


def test_repr_mentions_the_contents(params):
    assert "id" in repr(params)


def test_call_returns_the_mapping(params):
    assert params() == {"id": "7", "tag": ["a", "b"]}


def test_empty_route_param():
    empty = RouteParam({})
    assert len(empty) == 0
    assert empty.get("anything") is None
