"""Building a ``URL`` from an ASGI scope, and replacing parts of one.

The scope branch has four ways of deciding the authority -- a Host header, no
server at all, a server on the scheme's default port, and one on any other
port -- and only the first is common. The other three decide whether a
redirect, an absolute link or a signed URL points at the right place, and they
differ in exactly one character.
"""

from __future__ import annotations

import pytest

from sillo.objects.routing import URL


def scope(**overrides):
    base = {
        "scheme": "http",
        "path": "/things",
        "query_string": b"",
        "headers": [],
        "server": ("example.test", 80),
    }
    base.update(overrides)
    return base


class TestFromAScope:
    def test_a_host_header_wins(self):
        """The Host header is what the client actually asked for; the server
        tuple is the socket it landed on, which behind a proxy is not the
        same thing."""
        url = URL(scope=scope(headers=[(b"host", b"public.example")]))

        assert str(url) == "http://public.example/things"

    def test_the_host_header_is_preferred_over_the_server_tuple(self):
        url = URL(
            scope=scope(
                headers=[(b"host", b"public.example")],
                server=("internal.local", 8080),
            )
        )

        assert "public.example" in str(url)
        assert "internal.local" not in str(url)

    def test_no_host_and_no_server_leaves_a_bare_path(self):
        """Nothing available can name the authority, so inventing one would
        be a guess that ends up in a redirect."""
        url = URL(scope=scope(headers=[], server=None))

        assert str(url) == "/things"

    @pytest.mark.parametrize(
        ("scheme", "port"),
        [("http", 80), ("https", 443), ("ws", 80), ("wss", 443)],
    )
    def test_a_default_port_is_left_out(self, scheme, port):
        """``https://host:443/`` is correct and wrong: it compares unequal to
        the canonical form everywhere it is used as a key."""
        url = URL(scope=scope(scheme=scheme, headers=[], server=("example.test", port)))

        assert str(url) == f"{scheme}://example.test/things"

    @pytest.mark.parametrize(
        ("scheme", "port"),
        [("http", 8080), ("https", 8443), ("ws", 9000), ("wss", 9443)],
    )
    def test_a_non_default_port_is_kept(self, scheme, port):
        url = URL(scope=scope(scheme=scheme, headers=[], server=("example.test", port)))

        assert str(url) == f"{scheme}://example.test:{port}/things"

    def test_a_query_string_is_appended(self):
        url = URL(scope=scope(headers=[], query_string=b"a=1&b=2"))

        assert str(url).endswith("/things?a=1&b=2")

    def test_a_query_string_is_appended_to_a_bare_path_too(self):
        url = URL(scope=scope(headers=[], server=None, query_string=b"a=1"))

        assert str(url) == "/things?a=1"

    def test_an_empty_query_string_adds_no_question_mark(self):
        url = URL(scope=scope(headers=[], query_string=b""))

        assert "?" not in str(url)

    def test_a_non_host_header_is_ignored(self):
        url = URL(scope=scope(headers=[(b"accept", b"text/html")], server=("srv", 80)))

        assert str(url) == "http://srv/things"


class TestMutuallyExclusiveSources:
    def test_url_and_scope_together_are_refused(self):
        with pytest.raises(AssertionError, match="both"):
            URL("http://example.test/", scope=scope())

    def test_scope_and_components_together_are_refused(self):
        with pytest.raises(AssertionError, match="both"):
            URL(scope=scope(), path="/other")

    def test_url_and_components_together_are_refused(self):
        with pytest.raises(AssertionError, match="both"):
            URL("http://example.test/", path="/other")


class TestReplacingTheAuthority:
    """``replace`` rebuilds the netloc by hand whenever any of its four parts
    is named, because ``SplitResult`` exposes them read-only."""

    def test_the_hostname_can_be_swapped(self):
        url = URL("http://old.test/path").replace(hostname="new.test")

        assert str(url) == "http://new.test/path"

    def test_the_port_can_be_swapped(self):
        url = URL("http://example.test:8080/path").replace(port=9090)

        assert ":9090" in str(url)

    def test_the_port_can_be_removed(self):
        url = URL("http://example.test:8080/path").replace(port=None)

        assert ":8080" not in str(url)

    def test_a_username_is_added(self):
        url = URL("http://example.test/path").replace(username="ada")

        assert "ada@example.test" in str(url)

    def test_a_username_and_password_are_added(self):
        url = URL("http://example.test/path").replace(
            username="ada", password="secret"
        )

        assert "ada:secret@example.test" in str(url)

    def test_existing_credentials_survive_a_hostname_change(self):
        """``replace(hostname=...)`` changes the hostname and nothing else.

        Username and password default to the current ones, so moving a URL to
        another host keeps the credentials attached to it -- which is what
        makes `replace` composable, and worth stating because the netloc is
        rebuilt from scratch and could easily have lost them.
        """
        url = URL("http://ada:secret@old.test/path").replace(hostname="new.test")

        assert "new.test" in str(url)
        assert "ada:secret@" in str(url)

    def test_the_hostname_is_recovered_from_the_right_of_the_at_sign(self):
        """When no hostname is given it is parsed back out of the netloc, and
        the credentials in front of the ``@`` must not be mistaken for it."""
        url = URL("http://ada:secret@example.test:8080/path").replace(port=9090)

        assert "example.test:9090" in str(url)
        assert "ada:secret@" in str(url)

    def test_the_existing_port_is_preserved_when_only_the_user_changes(self):
        url = URL("http://example.test:8080/path").replace(username="ada")

        assert ":8080" in str(url)

    def test_an_ipv6_host_keeps_its_brackets(self):
        """The rsplit that strips a port must not cut inside an IPv6 literal,
        which is why the closing bracket is checked first."""
        url = URL("http://[::1]:8080/path").replace(username="ada")

        assert "[::1]" in str(url)

    def test_a_bare_ipv6_host_survives(self):
        url = URL("http://[::1]/path").replace(username="ada")

        assert "[::1]" in str(url)

    def test_replacing_a_plain_component_leaves_the_authority_alone(self):
        url = URL("http://example.test/old").replace(path="/new")

        assert str(url) == "http://example.test/new"


class TestQueryParameters:
    def test_include_query_params_adds_them(self):
        url = URL("http://example.test/path").include_query_params(page=2)

        assert "page=2" in str(url)

    def test_include_query_params_stringifies_both_sides(self):
        url = URL("http://example.test/path").include_query_params(**{"n": 1})

        assert "n=1" in str(url)

    def test_remove_query_params_takes_a_single_key(self):
        url = URL("http://example.test/p?a=1&b=2").remove_query_params("a")

        assert "a=1" not in str(url)
        assert "b=2" in str(url)

    def test_remove_query_params_takes_several(self):
        url = URL("http://example.test/p?a=1&b=2&c=3").remove_query_params(["a", "b"])

        assert "c=3" in str(url)
        assert "a=1" not in str(url)
        assert "b=2" not in str(url)

    def test_removing_an_absent_key_is_not_an_error(self):
        url = URL("http://example.test/p?a=1").remove_query_params("nope")

        assert "a=1" in str(url)

    def test_a_blank_value_is_kept_rather_than_dropped(self):
        """``?flag=`` is meaningfully different from no ``flag`` at all, and
        `parse_qsl` discards it unless asked not to."""
        url = URL("http://example.test/p?flag=&a=1").remove_query_params("a")

        assert "flag=" in str(url)


class TestEqualityAndRepr:
    def test_two_urls_with_the_same_text_are_equal(self):
        assert URL("http://example.test/p") == URL("http://example.test/p")

    def test_a_url_equals_its_own_string(self):
        assert URL("http://example.test/p") == "http://example.test/p"

    def test_different_urls_are_not_equal(self):
        assert URL("http://example.test/a") != URL("http://example.test/b")

    def test_str_returns_the_url(self):
        assert str(URL("http://example.test/p")) == "http://example.test/p"

    def test_repr_masks_a_password(self):
        """A URL with credentials in it reaches logs and tracebacks by way of
        repr more often than by anything deliberate."""
        rendered = repr(URL("http://ada:hunter2@example.test/p"))

        assert "hunter2" not in rendered
        assert "********" in rendered

    def test_repr_without_a_password_is_the_url(self):
        rendered = repr(URL("http://example.test/p"))

        assert "example.test" in rendered
        assert "********" not in rendered
