"""
Unknown route keyword arguments are rejected.

The verb decorators forward ``**kwargs`` to ``Route``, so a misspelled option
used to be accepted and quietly dropped. For an option like ``response_model``
whose job is to constrain output, a typo meant the endpoint went on returning
every field it was handed — a silent data leak with no error anywhere.
"""

import pytest
from pydantic import BaseModel

from sillo import SilloApp
from sillo.testclient import TestClient


class UserOut(BaseModel):
    id: int
    name: str


@pytest.fixture
def app():
    return SilloApp()


# ── rejection ────────────────────────────────────────────────────────────


def test_a_misspelled_option_is_rejected(app):
    with pytest.raises(TypeError, match="response_modle"):

        @app.get("/users", response_modle=UserOut)
        async def handler(request, response):
            return {}


def test_the_error_suggests_the_intended_option(app):
    with pytest.raises(TypeError, match="did you mean 'response_model'"):

        @app.get("/users", response_modle=UserOut)
        async def handler(request, response):
            return {}


def test_an_option_with_no_close_match_is_still_rejected(app):
    with pytest.raises(TypeError, match="totally_made_up"):

        @app.get("/users", totally_made_up=1)
        async def handler(request, response):
            return {}


def test_a_missing_underscore_is_caught(app):
    with pytest.raises(TypeError, match="did you mean 'request_model'"):

        @app.post("/users", requestmodel=UserOut)
        async def handler(request, response):
            return {}


@pytest.mark.parametrize("verb", ["get", "post", "put", "patch", "delete"])
def test_every_verb_decorator_rejects_unknown_options(app, verb):
    with pytest.raises(TypeError, match="nonsense_option"):

        @getattr(app, verb)(f"/{verb}", nonsense_option=True)
        async def handler(request, response):
            return {}


def test_several_bad_options_are_reported_together(app):
    with pytest.raises(TypeError) as exc:

        @app.get("/users", response_modle=UserOut, taggs=["a"])
        async def handler(request, response):
            return {}

    assert "response_modle" in str(exc.value)
    assert "taggs" in str(exc.value)


# ── the spelled-correctly path still works ───────────────────────────────


def test_a_correctly_spelled_option_shapes_the_response(app):
    @app.get("/users", response_model=UserOut)
    async def handler(request, response):
        return {"id": 1, "name": "Ada", "password_hash": "leaked"}

    body = TestClient(app).get("/users").json()

    assert body == {"id": 1, "name": "Ada"}
    assert "password_hash" not in body


def test_known_options_are_all_accepted(app):
    @app.get(
        "/documented",
        name="documented",
        summary="A summary",
        description="A description",
        tags=["things"],
        deprecated=True,
        operation_id="getDocumented",
        exclude_from_schema=False,
        response_model=UserOut,
        response_model_exclude_none=True,
    )
    async def handler(request, response):
        return {"id": 1, "name": "Ada"}

    assert TestClient(app).get("/documented").status_code == 200
