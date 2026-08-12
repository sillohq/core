"""Regression tests for the CORS credentials finding reported 2026-08-12.

``allow_credentials`` defaulted to true, and a wildcard origin was answered by
reflecting the caller's own ``Origin`` rather than sending ``*``. Together that
returned ``Access-Control-Allow-Credentials: true`` to any origin that asked,
which is exactly the pairing the Fetch standard forbids and browsers refuse —
refused only in its literal form, which reflection sidesteps.
"""

import pytest

from sillo import SilloApp
from sillo.core.http import Request, Response
from sillo.security.cors import CORSMiddleware, CorsConfig
from sillo.testclient import TestClient


def _app(config):
    app = SilloApp()

    @app.get("/resource")
    async def resource(request: Request, response: Response):
        return response.json({"message": "OK"})

    app.use(CORSMiddleware(config=config))
    return app


class TestCredentialsAreOffByDefault:
    def test_the_config_defaults_to_no_credentials(self):
        assert CorsConfig().allow_credentials is False

    def test_no_credentials_header_unless_asked_for(self):
        config = CorsConfig(allow_origins=["https://app.example.com"])

        with TestClient(_app(config)) as client:
            response = client.get(
                "/resource", headers={"Origin": "https://app.example.com"}
            )

        assert "Access-Control-Allow-Credentials" not in response.headers

    def test_credentials_are_sent_when_explicitly_configured(self):
        config = CorsConfig(
            allow_origins=["https://app.example.com"], allow_credentials=True
        )

        with TestClient(_app(config)) as client:
            response = client.get(
                "/resource", headers={"Origin": "https://app.example.com"}
            )

        assert response.headers["Access-Control-Allow-Credentials"] == "true"
        # A named origin is echoed, which is the only form a credentialed
        # request accepts.
        assert (
            response.headers["Access-Control-Allow-Origin"]
            == "https://app.example.com"
        )


class TestWildcardAndCredentialsCannotBeCombined:
    def test_the_pairing_is_refused_at_construction(self):
        with pytest.raises(ValueError, match="wildcard origin"):
            CORSMiddleware(
                config=CorsConfig(allow_origins=["*"], allow_credentials=True)
            )

    def test_the_error_names_the_way_out(self):
        with pytest.raises(ValueError) as caught:
            CORSMiddleware(
                config=CorsConfig(allow_origins=["*"], allow_credentials=True)
            )

        message = str(caught.value)
        assert "allow_origins=" in message
        assert "allow_credentials=True" in message

    def test_a_wildcard_without_credentials_is_fine(self):
        CORSMiddleware(config=CorsConfig(allow_origins=["*"]))


class TestWildcardIsNotReflected:
    """A wildcard configuration answers ``*``, not the caller's origin.

    Reflecting made the response vary by caller, so any shared cache in front
    of the application could serve one origin's headers to another — and it is
    what let credentials ride along with a wildcard in the first place.
    """

    @pytest.mark.parametrize(
        "origin",
        ["https://anything.example", "http://localhost:3000", "https://evil.example"],
    )
    def test_the_literal_wildcard_comes_back(self, origin):
        config = CorsConfig(allow_origins=["*"])

        with TestClient(_app(config)) as client:
            response = client.get("/resource", headers={"Origin": origin})

        assert response.headers["Access-Control-Allow-Origin"] == "*"
        assert "Access-Control-Allow-Credentials" not in response.headers

    def test_preflight_answers_the_wildcard_too(self):
        config = CorsConfig(allow_origins=["*"], allow_methods=["GET"])

        with TestClient(_app(config)) as client:
            response = client.options(
                "/resource",
                headers={
                    "Origin": "https://anything.example",
                    "Access-Control-Request-Method": "GET",
                },
            )

        assert response.headers["Access-Control-Allow-Origin"] == "*"
