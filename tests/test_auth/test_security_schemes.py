"""One auth declaration, two consumers.

sillo used to make you say the same thing twice: once as a backend, which
enforced it, and once as an OpenAPI security scheme, which documented it.
Nothing connected the two, so a document could advertise bearer auth while
the gate checked an API key and no test would notice.

These assert the connection. The point is not that the syntax is shorter —
it is that the document and the gate can no longer disagree.
"""

from typing import Callable

import pytest

from sillo import silloApp
from sillo.auth import (
    APIKeyAuthBackend,
    AuthenticationMiddleware,
    AuthenticationBackend,
    JWTAuthBackend,
    SessionAuthBackend,
    useAuth,
)
from sillo.auth.model import AuthResult
from sillo.core.http import Request, Response
from sillo.testclient import TestClient


def document(app: silloApp, client_factory) -> dict:
    """Build the app's OpenAPI document the way a viewer would fetch it."""
    with client_factory(app) as client:
        return client.get("/openapi.json").json()


# ── backends describe themselves ─────────────────────────────────────────


def test_jwt_backend_describes_bearer_auth():
    backend = JWTAuthBackend(secret_key="s", description="A JWT from login.")
    scheme = backend.describe().model_dump(exclude_none=True, by_alias=True)

    assert backend.name == "bearerAuth"
    assert scheme == {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "A JWT from login.",
    }


def test_api_key_backend_describes_its_own_header():
    """The documented header must be the one the backend actually reads."""
    backend = APIKeyAuthBackend(header_name="X-Tenant-Key")
    scheme = backend.describe().model_dump(exclude_none=True, by_alias=True)

    assert scheme == {"type": "apiKey", "name": "X-Tenant-Key", "in": "header"}


def test_session_backend_describes_its_cookie():
    backend = SessionAuthBackend(cookie_name="sid")
    scheme = backend.describe().model_dump(exclude_none=True, by_alias=True)

    assert scheme == {"type": "apiKey", "name": "sid", "in": "cookie"}


def test_a_backend_may_decline_to_be_documented():
    """A backend with nothing to publish still authenticates."""

    class Internal(AuthenticationBackend):
        async def authenticate(self, request):
            return AuthResult(success=False, identity="", scope="")

    assert Internal().describe() is None


def test_two_backends_of_a_kind_can_be_named_apart():
    """Two JWT secrets are two schemes, not one overwriting the other."""
    user = JWTAuthBackend(secret_key="a")
    admin = JWTAuthBackend(secret_key="b", name="adminBearer")

    assert user.name == "bearerAuth"
    assert admin.name == "adminBearer"
    assert admin.describe().scheme == "bearer"


# ── the app publishes what it enforces ───────────────────────────────────


def test_declaring_backends_registers_their_schemes(
    test_client_factory: Callable[[silloApp], TestClient],
):
    app = silloApp(
        title="T",
        version="1",
        auth=[JWTAuthBackend(secret_key="s"), APIKeyAuthBackend()],
    )

    schemes = document(app, test_client_factory)["components"]["securitySchemes"]

    assert set(schemes) == {"bearerAuth", "apiKeyHeader"}
    assert schemes["apiKeyHeader"]["in"] == "header"


def test_declaring_backends_replaces_the_legacy_default(
    test_client_factory: Callable[[silloApp], TestClient],
):
    """An app that declares no JWT must not advertise one.

    The constructor registers `bearerAuth` unconditionally, so every
    application claimed JWT bearer auth whether or not it had any. Declaring
    backends is the opt-out.
    """
    app = silloApp(title="T", version="1", auth=[APIKeyAuthBackend()])

    schemes = document(app, test_client_factory)["components"]["securitySchemes"]

    assert "bearerAuth" not in schemes


def test_the_legacy_default_survives_without_backends(
    test_client_factory: Callable[[silloApp], TestClient],
):
    """Existing apps keep the scheme their `security=` may already name."""
    app = silloApp(title="T", version="1")

    schemes = document(app, test_client_factory)["components"]["securitySchemes"]

    assert "bearerAuth" in schemes


def test_a_backend_that_declines_is_left_out_of_the_document(
    test_client_factory: Callable[[silloApp], TestClient],
):
    class Internal(AuthenticationBackend):
        name = "internal"

        async def authenticate(self, request):
            return AuthResult(success=False, identity="", scope="")

    app = silloApp(
        title="T", version="1", auth=[JWTAuthBackend(secret_key="s"), Internal()]
    )

    schemes = document(app, test_client_factory)["components"]["securitySchemes"]

    assert set(schemes) == {"bearerAuth"}


def test_two_backends_claiming_one_name_is_an_error():
    """Silently overwriting would document a credential nothing reads."""
    with pytest.raises(ValueError, match="both claim the scheme 'bearerAuth'"):
        silloApp(
            title="T",
            version="1",
            auth=[
                JWTAuthBackend(secret_key="a", description="one"),
                JWTAuthBackend(secret_key="b", description="another"),
            ],
        )


# ── the route says it once ───────────────────────────────────────────────


@pytest.mark.parametrize(
    "gate, expected",
    [
        (useAuth(schemes=["bearerAuth"]), [{"bearerAuth": []}]),
        (
            useAuth(schemes=["bearerAuth", "sessionCookie"]),
            [{"bearerAuth": []}, {"sessionCookie": []}],
        ),
        (
            useAuth(schemes=["bearerAuth", "apiKeyHeader"], all_of=True),
            [{"bearerAuth": [], "apiKeyHeader": []}],
        ),
        (
            useAuth(schemes=["bearerAuth"], required=False),
            [{"bearerAuth": []}, {}],
        ),
        (useAuth(schemes={"oauth2": ["read:widgets"]}), [{"oauth2": ["read:widgets"]}]),
        (useAuth(), None),
        (useAuth(permissions=["read:users"]), None),
    ],
)
def test_a_gate_derives_its_security_requirements(gate, expected):
    """OR is separate objects, AND is one object, optional adds an empty one."""
    assert gate.security_requirements() == expected


def test_the_document_follows_the_gate(
    test_client_factory: Callable[[silloApp], TestClient],
):
    app = silloApp(
        title="T",
        version="1",
        auth=[JWTAuthBackend(secret_key="s"), SessionAuthBackend()],
    )

    @app.get("/me", auth=useAuth(schemes=["bearerAuth", "sessionCookie"]))
    async def me(request: Request, response: Response):
        return response.json({})

    doc = document(app, test_client_factory)

    assert doc["paths"]["/me"]["get"]["security"] == [
        {"bearerAuth": []},
        {"sessionCookie": []},
    ]


def test_an_explicit_security_still_wins(
    test_client_factory: Callable[[silloApp], TestClient],
):
    """A gateway may terminate auth ahead of the app.

    The document then has to describe something this process does not
    enforce, so a hand-written `security=` is never overwritten.
    """
    app = silloApp(title="T", version="1", auth=[JWTAuthBackend(secret_key="s")])

    @app.get(
        "/proxied",
        auth=useAuth(schemes=["bearerAuth"]),
        security=[{"mtls": []}],
    )
    async def proxied(request: Request, response: Response):
        return response.json({})

    doc = document(app, test_client_factory)

    assert doc["paths"]["/proxied"]["get"]["security"] == [{"mtls": []}]


def test_a_route_with_no_gate_declares_no_security(
    test_client_factory: Callable[[silloApp], TestClient],
):
    app = silloApp(title="T", version="1", auth=[JWTAuthBackend(secret_key="s")])

    @app.get("/health")
    async def health(request: Request, response: Response):
        return response.json({})

    doc = document(app, test_client_factory)

    assert doc["paths"]["/health"]["get"].get("security") is None


# ── the gate enforces the scheme it documents ────────────────────────────


class StubBackend(AuthenticationBackend):
    """A backend that always succeeds, so the gate is what is under test."""

    def __init__(self, name: str, scope: str):
        self.name = name
        self._scope = scope

    async def authenticate(self, request):
        return AuthResult(success=True, identity="u1", scope=self._scope)


def test_a_request_through_an_accepted_scheme_passes(
    test_client_factory: Callable[[silloApp], TestClient],
):
    app = silloApp(title="T", version="1", auth=[StubBackend("bearerAuth", "jwt")])

    @app.get("/me", auth=useAuth(schemes=["bearerAuth"]))
    async def me(request: Request, response: Response):
        return response.json({"ok": True})

    with test_client_factory(app) as client:
        assert client.get("/me").status_code == 200


def test_a_request_through_the_wrong_scheme_is_rejected(
    test_client_factory: Callable[[silloApp], TestClient],
):
    """Documented bearer, authenticated by cookie — the gate must refuse.

    This is the disagreement the whole change exists to make impossible: the
    document promises one credential and something else gets in.
    """
    app = silloApp(
        title="T", version="1", auth=[StubBackend("sessionCookie", "session")]
    )

    @app.get("/me", auth=useAuth(schemes=["bearerAuth"]))
    async def me(request: Request, response: Response):
        return response.json({"ok": True})

    with test_client_factory(app) as client:
        assert client.get("/me").status_code == 401


def test_the_middleware_records_which_scheme_answered(
    test_client_factory: Callable[[silloApp], TestClient],
):
    app = silloApp(title="T", version="1", auth=[StubBackend("apiKeyHeader", "apikey")])

    @app.get("/who")
    async def who(request: Request, response: Response):
        return response.json(
            {
                "scope": request.scope.get("auth"),
                "scheme": request.scope.get("auth_scheme"),
            }
        )

    with test_client_factory(app) as client:
        body = client.get("/who").json()

    # Both, and they are different things.
    assert body == {"scope": "apikey", "scheme": "apiKeyHeader"}


def test_an_unauthenticated_request_records_no_scheme(
    test_client_factory: Callable[[silloApp], TestClient],
):
    class Never(AuthenticationBackend):
        name = "bearerAuth"

        async def authenticate(self, request):
            return AuthResult(success=False, identity="", scope="")

    app = silloApp(title="T", version="1", auth=[Never()])

    @app.get("/who")
    async def who(request: Request, response: Response):
        return response.json({"scheme": request.scope.get("auth_scheme")})

    with test_client_factory(app) as client:
        assert client.get("/who").json() == {"scheme": None}


# ── strict_security ──────────────────────────────────────────────────────


def test_strict_security_rejects_an_unregistered_scheme(
    test_client_factory: Callable[[silloApp], TestClient],
):
    """A viewer would render an authorize box wired to nothing."""
    app = silloApp(
        title="T",
        version="1",
        auth=[JWTAuthBackend(secret_key="s")],
        strict_security=True,
    )

    @app.get("/oops", auth=useAuth(schemes=["sessionCookie"]))
    async def oops(request: Request, response: Response):
        return response.json({})

    with pytest.raises(ValueError, match="not registered"):
        app.build_openapi()


def test_strict_security_names_the_route_and_the_scheme():
    app = silloApp(
        title="T",
        version="1",
        auth=[JWTAuthBackend(secret_key="s")],
        strict_security=True,
    )

    @app.get("/oops", auth=useAuth(schemes=["sessionCookie"]))
    async def oops(request: Request, response: Response):
        return response.json({})

    with pytest.raises(ValueError) as caught:
        app.build_openapi()

    message = str(caught.value)
    assert "/oops" in message
    assert "sessionCookie" in message
    # And what *is* available, so the fix is obvious.
    assert "bearerAuth" in message


def test_strict_security_passes_when_everything_resolves():
    app = silloApp(
        title="T",
        version="1",
        auth=[JWTAuthBackend(secret_key="s"), SessionAuthBackend()],
        strict_security=True,
    )

    @app.get("/me", auth=useAuth(schemes=["bearerAuth", "sessionCookie"]))
    async def me(request: Request, response: Response):
        return response.json({})

    assert "bearerAuth" in app.build_openapi()


def test_strict_security_is_off_by_default():
    """Existing applications keep building."""
    app = silloApp(title="T", version="1")

    @app.get("/oops", security=[{"nothingDefinesThis": []}])
    async def oops(request: Request, response: Response):
        return response.json({})

    assert app.build_openapi()


def test_strict_security_ignores_excluded_routes():
    app = silloApp(
        title="T",
        version="1",
        auth=[JWTAuthBackend(secret_key="s")],
        strict_security=True,
    )

    @app.get("/internal", security=[{"ghost": []}], exclude_from_schema=True)
    async def internal(request: Request, response: Response):
        return response.json({})

    assert app.build_openapi()


# ── a gate that names no schemes ─────────────────────────────────────────


def test_a_bare_gate_is_documented_as_protected(
    test_client_factory: Callable[[silloApp], TestClient],
):
    """`useAuth()` names no scheme but still refuses anonymous callers.

    Deriving nothing left the route documented as public while it answered
    401 — the same disagreement this change exists to remove, pointing the
    more dangerous way: a consumer reads "no auth needed" and is refused.
    Any registered backend can satisfy the gate, so that is what it says.
    """
    app = silloApp(
        title="T",
        version="1",
        auth=[JWTAuthBackend(secret_key="s"), SessionAuthBackend()],
    )

    @app.get("/plain", auth=useAuth())
    async def plain(request: Request, response: Response):
        return response.json({})

    doc = document(app, test_client_factory)

    assert doc["paths"]["/plain"]["get"]["security"] == [
        {"bearerAuth": []},
        {"sessionCookie": []},
    ]


def test_a_permissions_only_gate_is_documented_as_protected(
    test_client_factory: Callable[[silloApp], TestClient],
):
    """Permissions imply authentication, so the route is not public."""
    app = silloApp(title="T", version="1", auth=[JWTAuthBackend(secret_key="s")])

    @app.get("/perm", auth=useAuth(permissions=["audit:read"]))
    async def perm(request: Request, response: Response):
        return response.json({})

    doc = document(app, test_client_factory)

    assert doc["paths"]["/perm"]["get"]["security"] == [{"bearerAuth": []}]


def test_a_bare_optional_gate_keeps_its_empty_alternative(
    test_client_factory: Callable[[silloApp], TestClient],
):
    app = silloApp(title="T", version="1", auth=[JWTAuthBackend(secret_key="s")])

    @app.get("/feed", auth=useAuth(required=False))
    async def feed(request: Request, response: Response):
        return response.json({})

    doc = document(app, test_client_factory)

    assert doc["paths"]["/feed"]["get"]["security"] == [{"bearerAuth": []}, {}]


def test_a_route_with_no_gate_stays_public(
    test_client_factory: Callable[[silloApp], TestClient],
):
    """The fallback must not protect what nothing gates."""
    app = silloApp(title="T", version="1", auth=[JWTAuthBackend(secret_key="s")])

    @app.get("/health")
    async def health(request: Request, response: Response):
        return response.json({})

    doc = document(app, test_client_factory)

    assert doc["paths"]["/health"]["get"].get("security") is None


def test_the_documented_and_enforced_answers_agree(
    test_client_factory: Callable[[silloApp], TestClient],
):
    """Whether a route is documented as protected must match whether it is.

    Asserting on the pair is the point — either alone passes while the two
    disagree, which is exactly how this went unnoticed.
    """
    app = silloApp(
        title="T",
        version="1",
        auth=[StubBackend("bearerAuth", "jwt"), SessionAuthBackend()],
    )

    @app.get("/gated", auth=useAuth())
    async def gated(request: Request, response: Response):
        return response.json({})

    @app.get("/open")
    async def open_route(request: Request, response: Response):
        return response.json({})

    doc = document(app, test_client_factory)

    for path in ("/gated", "/open"):
        documented = doc["paths"][path]["get"].get("security") is not None
        # StubBackend authenticates everything, so a gated route answers 200;
        # what matters is that a *documented* requirement exists exactly when
        # a gate does.
        gated_in_code = any(
            route.raw_path == path and getattr(route, "auth", None) is not None
            for route in app.get_all_routes()
        )
        assert documented == gated_in_code, path


def test_a_bare_gate_derives_nothing_without_registered_schemes():
    """No backends means nothing to name, and the route keeps quiet."""
    assert useAuth().security_requirements(available=[]) is None
    assert useAuth().security_requirements() is None


# ── one identifier ───────────────────────────────────────────────────────


def test_a_backend_reports_its_scheme_name_as_the_scope(
    test_client_factory: Callable[[silloApp], TestClient],
):
    """`auth` and `auth_scheme` are the same value now, not two vocabularies.

    A backend used to report a method label ("jwt") while the document named
    a scheme ("bearerAuth"), so a route had to know both. The backend now
    reports one identifier and both keys carry it.
    """
    app = silloApp(title="T", version="1", auth=[StubBackend("bearerAuth", "bearerAuth")])

    @app.get("/who")
    async def who(request: Request, response: Response):
        return response.json(
            {
                "auth": request.scope.get("auth"),
                "scheme": request.scope.get("auth_scheme"),
            }
        )

    with test_client_factory(app) as client:
        body = client.get("/who").json()

    assert body == {"auth": "bearerAuth", "scheme": "bearerAuth"}


def test_renaming_a_backend_renames_what_it_reports():
    """The name is the identifier, so changing it changes the gate too."""
    backend = JWTAuthBackend(secret_key="s", name="adminBearer")

    assert backend.name == "adminBearer"


def test_the_removed_scopes_parameter_is_rejected():
    """`scopes=` was the pre-`schemes` spelling of the same idea.

    It was removed once the migration to scheme names completed; passing it
    now is a `TypeError`, not a silent 401 or a warning.
    """
    with pytest.raises(TypeError):
        useAuth(scopes=["jwt"])


def test_the_middleware_survives_having_no_backends(
    test_client_factory: Callable[[silloApp], TestClient],
):
    """`AuthenticationMiddleware()` with no backend used to 500 every request.

    The single backend was wrapped as `[backend]` without checking for the
    `None` default, so the list held one `None`. Its first `AttributeError`
    was then handled by calling `None.handle_exception`, raising a second
    one from inside the handler for the first.
    """
    app = silloApp(title="T", version="1")
    app.use(AuthenticationMiddleware())

    @app.get("/anon")
    async def anon(request: Request, response: Response):
        return response.json({"authenticated": request.user.is_authenticated})

    with test_client_factory(app) as client:
        resp = client.get("/anon")

    assert resp.status_code == 200
    assert resp.json() == {"authenticated": False}
