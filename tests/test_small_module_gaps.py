"""Small, self-contained gaps across many modules.

Each of these is a handful of lines — a ``__str__``, a fallback branch, an
abstract method's ``NotImplementedError`` — that no test happened to touch.
They are gathered here rather than scattered because none of them justifies a
file, and because the pattern is the same in every case: the module was
exercised through its happy path only.
"""

import pytest

from sillo.auth.backend import AuthenticationBackend
from sillo.core.routing._utils import get_route_path
from sillo.exceptions import HTTPException
from sillo.hashing.config import SCHEMES, get_default_scheme, is_scheme_available
from sillo.security.ratelimit.strategies.base import RateLimitStrategy


class TestAuthenticationBackendContract:
    async def test_the_base_authenticate_refuses_to_be_used(self):
        class Bare(AuthenticationBackend):
            pass

        with pytest.raises(NotImplementedError, match="must implement authenticate"):
            await Bare().authenticate(object())

    async def test_the_error_names_the_subclass(self):
        class MyBackend(AuthenticationBackend):
            pass

        with pytest.raises(NotImplementedError, match="MyBackend"):
            await MyBackend().authenticate(object())

    def test_handle_exception_logs_without_raising(self):
        class Bare(AuthenticationBackend):
            async def authenticate(self, request):
                return None

        Bare().handle_exception(object(), RuntimeError("backend failed"))


class TestRateLimitStrategyContract:
    def test_it_cannot_be_instantiated_directly(self):
        with pytest.raises(TypeError):
            RateLimitStrategy()

    async def test_a_subclass_must_implement_hit(self):
        class Bare(RateLimitStrategy):
            async def hit(self, backend, key, limit, window, cost=1, now=None):
                return await super().hit(backend, key, limit, window, cost, now)

        # The abstract body is reachable through an explicit super() call.
        with pytest.raises((NotImplementedError, TypeError, AttributeError)):
            await Bare().hit(None, "k", 1, 1)


class TestRoutePath:
    def test_a_path_outside_the_root_is_returned_unchanged(self):
        scope = {"path": "/other", "root_path": "/mounted"}
        assert get_route_path(scope) == "/other"

    def test_a_path_equal_to_the_root_becomes_empty(self):
        scope = {"path": "/mounted", "root_path": "/mounted"}
        assert get_route_path(scope) == ""

    def test_the_root_prefix_is_stripped(self):
        scope = {"path": "/mounted/thing", "root_path": "/mounted"}
        assert get_route_path(scope) == "/thing"

    def test_no_root_path_leaves_the_path_alone(self):
        scope = {"path": "/thing", "root_path": ""}
        assert get_route_path(scope) == "/thing"


class TestExceptionRepr:
    def test_an_http_exception_reports_status_and_detail(self):
        text = repr(HTTPException(status_code=404, detail="missing"))

        assert "404" in text
        assert "missing" in text
        assert text.startswith("HTTPException(")

    def test_a_subclass_reports_its_own_name(self):
        class NotFound(HTTPException):
            pass

        assert repr(NotFound(status_code=404, detail="x")).startswith("NotFound(")


class TestHashingSchemeSelection:
    def test_the_default_scheme_is_available(self):
        assert is_scheme_available(get_default_scheme())

    def test_an_unknown_scheme_is_not_available(self):
        assert is_scheme_available("no-such-scheme") is False

    def test_a_scheme_needing_no_package_is_always_available(self):
        builtin = [n for n, c in SCHEMES.items() if c.package is None]
        for name in builtin:
            assert is_scheme_available(name) is True

    def test_pbkdf2_is_the_fallback_when_nothing_else_is_installed(
        self, monkeypatch
    ):
        # Every scheme reports missing, so the built-in fallback is returned
        # rather than raising — hashing has to work with no extras installed.
        import sillo.hashing.config as config

        monkeypatch.setattr(config, "is_scheme_available", lambda name: False)

        assert config.get_default_scheme() == "pbkdf2_sha256"


class TestAdminActivityRepr:
    def test_it_summarises_the_entry(self):
        from sillo.admin.models import AdminActivity

        entry = AdminActivity(
            user_email="ada@example.com",
            action="update",
            model_name="User",
        )

        text = str(entry)

        assert "ada@example.com" in text
        assert "update" in text
        assert "User" in text
