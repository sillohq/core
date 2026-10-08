"""The C-encoder fast paths must produce exactly what the full conversion does.

``native_json`` (a handler's plain dict or list) and the ``default=`` attempt
inside ``JSONResponse`` exist to skip rebuilding a payload in Python. Both are
only allowed to be faster: for every value they accept, the bytes must equal
``json.dumps(jsonable_encoder(value))``; for every value they cannot be sure
about, they must decline so the old path runs and raises what it always raised.
"""

from __future__ import annotations

import collections
import dataclasses
import datetime
import decimal
import enum
import ipaddress
import json
import pathlib
import random
import uuid

import pytest
from pydantic import BaseModel

from sillo import HttpContext, SilloApp
from sillo import json as json_response
from sillo.core.encoding import CUSTOM_ENCODERS, jsonable_encoder, register_encoder
from sillo.core.http.response import JSONResponse, native_json
from sillo.testclient import TestClient

NOW = datetime.datetime(2026, 1, 2, 3, 4, 5, 678, tzinfo=datetime.timezone.utc)


class Color(str, enum.Enum):
    RED = "red"


class Level(enum.IntEnum):
    ONE = 1


class Plain(enum.Enum):
    A = 5


Point = collections.namedtuple("Point", "x y")


@dataclasses.dataclass
class Row:
    a: int
    when: datetime.date


class Item(BaseModel):
    n: int
    at: datetime.datetime


def reference(value, *, indent=None, ensure_ascii=True):
    """What the full conversion has always produced."""
    return json.dumps(
        jsonable_encoder(value),
        indent=indent,
        ensure_ascii=ensure_ascii,
        allow_nan=False,
        default=str,
        separators=(",", ":") if indent is None else None,
    )


def make_cases():
    """Fresh values each call: generators are single-use."""
    return {
        "native": {"a": [1, 2.5, "x", None, True], "b": {"c": "é"}},
        "rich row": [
            {
                "id": uuid.UUID(int=7),
                "at": NOW,
                "price": decimal.Decimal("9.99"),
                "whole": decimal.Decimal(12),
                "day": NOW.date(),
                "time": NOW.time(),
                "span": datetime.timedelta(seconds=90),
            }
        ],
        "enums": {"c": Color.RED, "n": Level.ONE, "p": Plain.A},
        "sequences": {"t": (1, 2), "s": {3}, "fs": frozenset([4]), "nt": Point(1, 2)},
        "defaultdict": collections.defaultdict(list, {"a": [1]}),
        "ordered": collections.OrderedDict(b=1, a=2),
        "dataclass": {"d": Row(1, NOW.date())},
        "pydantic": {"m": Item(n=1, at=NOW)},
        "bytes": {"b": b"hi"},
        "ip and path": {
            "ip": ipaddress.IPv4Address("1.2.3.4"),
            "p": pathlib.PurePosixPath("/a"),
        },
        "scalar keys": {1: "a", 2.5: "b", None: "d"},
        "bool keys": {True: "yes", False: "no"},
        "str enum key": {Color.RED: 1},
        "non-ascii": {"é": "日本"},
        "deep": [[[[{"k": NOW}]]]],
        "generator": {"g": (i for i in range(3))},
        "empty": {},
    }


@pytest.mark.parametrize("name", list(make_cases()))
def test_matches_the_full_conversion(name):
    got = native_json(make_cases()[name])
    assert got == reference(make_cases()[name])


@pytest.mark.parametrize(
    "value",
    [
        {"x": float("nan")},
        {"x": float("inf")},
        {NOW: 1},
        {(1, 2): 1},
        {Plain.A: 1},
        {"bad": object()},
    ],
    ids=["nan", "inf", "datetime key", "tuple key", "plain enum key", "unencodable"],
)
def test_declines_what_it_cannot_be_sure_of(value):
    """Declining sends the caller down the old path, which decides the outcome."""
    got = native_json(value)
    if got is not None:
        assert got == reference(value)
    else:
        # The old path is whatever it was: an error, or a conversion we skipped.
        try:
            reference(value)
        except (TypeError, ValueError):
            pass


def test_circular_reference_declines():
    loop: dict = {}
    loop["self"] = loop
    assert native_json(loop) is None


def test_registered_encoders_switch_the_fast_path_off():
    """A plain-dict return honoured registered encoders before; it still must."""

    class Tag(str):
        pass

    register_encoder(Tag, lambda t: f"tag:{t}")
    try:
        assert native_json({"t": Tag("x")}) is None
        app = SilloApp(debug=False)

        @app.get("/tag")
        async def tag(ctx: HttpContext):
            return {"t": Tag("x")}

        assert TestClient(app).get("/tag").json() == {"t": "tag:x"}
    finally:
        CUSTOM_ENCODERS.pop(Tag, None)


def _random_value(rng: random.Random, depth: int = 0):
    leaves = [
        lambda: rng.randint(-(10**6), 10**6),
        lambda: rng.random() * 10 ** rng.randint(-8, 18),
        lambda: rng.choice(
            ["", "a", "é", "日本", 'q"uote', "back\\slash", "line\nbreak"]
        ),
        lambda: rng.choice([True, False, None]),
        lambda: NOW + datetime.timedelta(seconds=rng.randint(0, 10**7)),
        lambda: uuid.UUID(int=rng.getrandbits(128)),
        lambda: decimal.Decimal(rng.choice(["1", "10", "1.5", "0.001", "123456.789"])),
        lambda: datetime.timedelta(seconds=rng.randint(0, 9999)),
        lambda: rng.choice(list(Color)),
        lambda: rng.choice(list(Level)),
        lambda: Point(rng.randint(0, 9), "p"),
    ]
    if depth > 3 or rng.random() < 0.35:
        return rng.choice(leaves)()
    if rng.random() < 0.5:
        return [_random_value(rng, depth + 1) for _ in range(rng.randint(0, 4))]
    keys = ["a", "b", "ключ", "k", 1, 2.5, True, None]
    return {
        rng.choice(keys): _random_value(rng, depth + 1)
        for _ in range(rng.randint(0, 4))
    }


def test_randomised_payloads_never_differ():
    rng = random.Random(20261008)
    accepted = 0
    for _ in range(1500):
        seed = rng.getrandbits(32)
        value = _random_value(random.Random(seed))
        fast = native_json(value)
        if fast is None:
            continue
        accepted += 1
        assert fast == reference(_random_value(random.Random(seed)))
    assert accepted > 1000  # the fast path really is being exercised


@pytest.mark.parametrize("ensure_ascii", [True, False])
@pytest.mark.parametrize("indent", [None, 2])
def test_json_response_with_rich_values_is_unchanged(indent, ensure_ascii):
    for name in make_cases():
        value = make_cases()[name]
        want = reference(make_cases()[name], indent=indent, ensure_ascii=ensure_ascii)
        got = JSONResponse(value, indent=indent, ensure_ascii=ensure_ascii).body
        got = got.decode() if isinstance(got, bytes) else got
        assert got == want, name


def test_handler_return_paths_agree():
    app = SilloApp(debug=False)

    @app.get("/plain")
    async def plain(ctx: HttpContext):
        return {
            "id": uuid.UUID(int=1),
            "at": NOW,
            "price": decimal.Decimal("1.5"),
            "tags": ["a"],
        }

    @app.get("/built")
    async def built(ctx: HttpContext):
        return json_response(
            {
                "id": uuid.UUID(int=1),
                "at": NOW,
                "price": decimal.Decimal("1.5"),
                "tags": ["a"],
            }
        )

    @app.get("/text")
    async def text_enum(ctx: HttpContext):
        return Color.RED  # converts to a plain string, which is sent as text

    @app.get("/list")
    async def a_list(ctx: HttpContext):
        return [1, {"x": NOW}]

    client = TestClient(app)
    plain_r, built_r = client.get("/plain"), client.get("/built")
    assert plain_r.status_code == built_r.status_code == 200
    assert plain_r.content == built_r.content
    assert plain_r.headers["content-type"].startswith("application/json")
    text_r = client.get("/text")
    assert (
        text_r.headers["content-type"].startswith("text/plain") and text_r.text == "red"
    )
    assert client.get("/list").json() == [1, {"x": NOW.isoformat()}]


def test_plain_return_errors_are_unchanged():
    app = SilloApp(debug=False)

    @app.get("/nan")
    async def nan(ctx: HttpContext):
        return {"x": float("nan")}

    assert TestClient(app, raise_server_exceptions=False).get("/nan").status_code == 500


def _too_deep(depth: int = 200_000):
    value: list = []
    for _ in range(depth):
        value = [value]
    return value


def test_a_payload_nested_too_deeply_still_raises_recursion_error():
    """The C encoder gives up first; the full conversion then fails the same way it always did."""
    with pytest.raises(RecursionError):
        JSONResponse(_too_deep())


def test_nesting_too_deep_raises_recursion_error_when_an_encoder_is_registered():
    """With a custom encoder registered the hook is off, so the error comes straight from the C encoder."""

    class Marker:
        pass

    register_encoder(Marker, lambda m: "marker")
    try:
        with pytest.raises(RecursionError):
            JSONResponse(_too_deep())
    finally:
        CUSTOM_ENCODERS.pop(Marker, None)
