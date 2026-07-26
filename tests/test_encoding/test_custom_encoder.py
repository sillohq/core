from __future__ import annotations

import decimal
from dataclasses import dataclass

import pytest

from sillo import silloApp
from sillo.core.encoding import CUSTOM_ENCODERS, register_encoder
from sillo.testclient import TestClient


@dataclass
class Money:
    amount: decimal.Decimal
    currency: str


class Vector:
    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y


def teardown_module(module):
    CUSTOM_ENCODERS.pop(Money, None)
    CUSTOM_ENCODERS.pop(Vector, None)


class TestAppAddEncoder:
    def test_add_encoder_applies_to_handler_return(self):
        app = silloApp()
        app.add_encoder(Money, lambda m: {"amount": str(m.amount), "currency": m.currency})

        @app.get("/price")
        async def price(request, response):
            return {"total": Money(decimal.Decimal("19.99"), "USD")}

        client = TestClient(app)
        resp = client.get("/price")
        assert resp.status_code == 200
        assert resp.json() == {"total": {"amount": "19.99", "currency": "USD"}}

    def test_add_encoder_nested(self):
        app = silloApp()
        app.add_encoder(Vector, lambda v: [v.x, v.y])

        @app.get("/vec")
        async def vec(request, response):
            return {"points": [Vector(1, 2), Vector(3, 4)]}

        client = TestClient(app)
        assert client.get("/vec").json() == {"points": [[1, 2], [3, 4]]}

    def test_add_encoder_registers_globally(self):
        app = silloApp()
        app.add_encoder(Vector, lambda v: [v.x, v.y])
        assert Vector in CUSTOM_ENCODERS
        assert Vector in app.custom_encoders


class TestResponseJsonCustomEncoder:
    def test_response_json_per_call_encoder(self):
        app = silloApp()

        @app.get("/raw")
        async def raw(request, response):
            return response.json(
                {"v": Vector(5, 6)},
                custom_encoder={Vector: lambda v: {"x": v.x, "y": v.y}},
            )

        client = TestClient(app)
        assert client.get("/raw").json() == {"v": {"x": 5, "y": 6}}

    def test_response_json_per_call_overrides_global(self):
        # global registry encodes Vector as list; per-call overrides to dict
        register_encoder(Vector, lambda v: [v.x, v.y])
        app = silloApp()

        @app.get("/override")
        async def override(request, response):
            return response.json(
                Vector(7, 8),
                custom_encoder={Vector: lambda v: {"x": v.x, "y": v.y}},
            )

        client = TestClient(app)
        assert client.get("/override").json() == {"x": 7, "y": 8}


class TestEncoderPrecedence:
    def test_per_call_encoder_wins_over_app_registered(self):
        app = silloApp()
        app.add_encoder(Vector, lambda v: "app-level")

        @app.get("/win")
        async def win(request, response):
            return response.json(
                Vector(1, 1),
                custom_encoder={Vector: lambda v: "call-level"},
            )

        client = TestClient(app)
        assert client.get("/win").json() == "call-level"
