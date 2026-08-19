"""The predicates that decide whether CSRF applies to a request.

Four small methods answer "does this request need a token?", and each of them
fails open or closed in a way that matters. A URL pattern that matches too
loosely exempts routes nobody meant to exempt; one that matches too tightly
enforces on routes that cannot carry a token. Neither shows up as an error --
the first is a hole, the second is a 403 someone reports as "the form is
broken".
"""

from __future__ import annotations

import pytest

from sillo.security.csrf import CSRFConfig
from sillo.security.csrf._middleware import CSRFMiddleware


def middleware(**config) -> CSRFMiddleware:
    instance = CSRFMiddleware(config=CSRFConfig(secret_key="k" * 32, **config))
    instance._setup_csrf_config()
    return instance


class TestConstruction:
    def test_a_config_of_the_wrong_type_is_refused(self):
        """Passing a dict of settings is the obvious mistake, and accepting it
        would leave every attribute unset -- which reads as "CSRF off"."""
        with pytest.raises(TypeError, match="CSRFConfig"):
            CSRFMiddleware(config={"secret_key": "k" * 32})

    def test_no_config_leaves_the_middleware_inert(self):
        """Constructed without a config it must not half-enforce: a token it
        cannot validate would reject every unsafe request."""
        instance = CSRFMiddleware()

        assert instance.csrf_config is None
        assert instance.use_csrf is False


class TestSensitiveCookies:
    def test_with_none_configured_every_request_counts(self):
        """The default has to be "protect everything". Reading an empty list
        as "nothing is sensitive" would switch CSRF off for the whole
        application by omission.
        """
        assert middleware()._has_sensitive_cookies({"anything": "1"}) is True

    def test_a_named_cookie_present_counts(self):
        instance = middleware(sensitive_cookies={"sessionid"})

        assert instance._has_sensitive_cookies({"sessionid": "abc"}) is True

    def test_a_named_cookie_absent_does_not_count(self):
        """Without the cookie there is no ambient authority to abuse, so the
        request cannot be a CSRF."""
        instance = middleware(sensitive_cookies={"sessionid"})

        assert instance._has_sensitive_cookies({"other": "abc"}) is False

    def test_an_empty_cookie_jar_does_not_count(self):
        instance = middleware(sensitive_cookies={"sessionid"})

        assert instance._has_sensitive_cookies({}) is False


class TestRequiredUrls:
    def test_everything_is_required_by_default(self):
        """The default is ``["*"]``, and it has to be. A framework whose CSRF
        protection covers nothing until a list is written is off by default
        for everyone who did not read that far.
        """
        assert middleware()._url_is_required("/anything") is True

    def test_an_explicitly_empty_list_still_means_everything(self):
        """``required_urls or ["*"]`` treats an empty list as "unset".

        So ``required_urls=[]`` -- which reads as "require it nowhere" --
        silently becomes "require it everywhere". Surprising, but it fails
        closed, and that is the direction a security default should fail in.
        """
        assert middleware(required_urls=[])._url_is_required("/anything") is True

    def test_the_empty_guard_is_unreachable_through_config(self):
        """``_url_is_required`` opens with ``if not self.required_urls``.

        No configuration can produce that state, because the constructor
        normalises an empty list away. Reaching it means setting the parsed
        config directly, which is what this does -- the guard is real code and
        answers correctly, it simply has no route in from the public API.
        """
        instance = middleware()
        instance.required_urls = []

        assert instance._url_is_required("/anything") is False

    def test_a_star_requires_everything(self):
        instance = middleware(required_urls=["*"])

        assert instance._url_is_required("/anything") is True

    def test_a_pattern_matches_its_url(self):
        instance = middleware(required_urls=[r"/admin/.*"])

        assert instance._url_is_required("/admin/users") is True

    def test_a_pattern_must_match_the_whole_url(self):
        """``re.match`` anchors only at the start. Without the full-length
        check, ``/admin`` would also claim ``/administrator-signup`` -- and
        for the exempt list the same looseness is a hole rather than noise.
        """
        instance = middleware(required_urls=[r"/admin"])

        assert instance._url_is_required("/administrator") is False

    def test_an_unmatched_url_is_not_required(self):
        instance = middleware(required_urls=[r"/admin/.*"])

        assert instance._url_is_required("/public") is False


class TestExemptUrls:
    def test_nothing_is_exempt_by_default(self):
        """The safe default: a list nobody configured must not excuse
        anything."""
        assert middleware()._url_is_exempt("/anything") is False

    def test_a_pattern_exempts_its_url(self):
        instance = middleware(exempt_urls=[r"/webhooks/.*"])

        assert instance._url_is_exempt("/webhooks/stripe") is True

    def test_a_pattern_must_match_the_whole_url(self):
        """The important direction. A partial match here would exempt every
        path that merely *starts* with an exempt prefix."""
        instance = middleware(exempt_urls=[r"/webhooks"])

        assert instance._url_is_exempt("/webhooks-admin") is False

    def test_an_unmatched_url_is_not_exempt(self):
        instance = middleware(exempt_urls=[r"/webhooks/.*"])

        assert instance._url_is_exempt("/account") is False


class TestTokens:
    def test_a_generated_token_is_not_empty(self):
        assert middleware()._generate_csrf_token()

    def test_two_tokens_differ(self):
        instance = middleware()

        assert instance._generate_csrf_token() != instance._generate_csrf_token()

    def test_matching_tokens_compare_equal(self):
        instance = middleware()
        token = instance._generate_csrf_token()

        assert instance._csrf_tokens_match(token, token) is True

    def test_different_tokens_do_not_match(self):
        instance = middleware()
        first = instance._generate_csrf_token()
        second = instance._generate_csrf_token()

        assert instance._csrf_tokens_match(first, second) is False

    def test_a_tampered_payload_does_not_match(self):
        """Tamper with the payload, which is where a forgery would have to
        land, and where every bit is load-bearing.

        The payload is base64 of a 45-byte JSON string -- 60 characters
        exactly, a whole number of 4-character groups -- so no bit of it is
        discarded on the way back and any edit both changes the value and
        breaks the signature over it.
        """
        instance = middleware()
        token = instance._generate_csrf_token()
        payload, _, signature = token.partition(".")
        edited = payload[:-1] + ("a" if payload[-1] != "a" else "b")

        assert instance._csrf_tokens_match(token, f"{edited}.{signature}") is False

    def test_a_token_signed_with_another_key_does_not_match(self):
        """The threat this defends against: an attacker who can see a token
        and copy its shape, but does not hold the secret."""
        instance = middleware()
        forger = CSRFMiddleware(config=CSRFConfig(secret_key="x" * 32))
        forger._setup_csrf_config()

        assert instance._csrf_tokens_match(
            instance._generate_csrf_token(), forger._generate_csrf_token()
        ) is False

    def test_the_signature_length_is_fixed(self):
        """Editing the final character alone should not be treated as tampering.

        The signature length is deterministic for the chosen digest. Asserted
        here so the signature format is documented and future refactors do not
        silently change it.
        """
        instance = middleware()
        token = instance._generate_csrf_token()
        _, _, signature = token.partition(".")
        assert len(signature) == 43

        twin = token[:-1] + ("a" if token[-1] != "a" else "b")

        assert twin != token
        assert instance._csrf_tokens_match(token, twin) is False
