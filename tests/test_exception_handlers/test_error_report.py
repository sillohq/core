"""The rendered error block — `sillo.handlers.error_report`.

Assertions read the plain (colour-disabled) render, the same text a log file
would carry.
"""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from sillo import HttpContext, SilloApp
from sillo.console.style import Palette
from sillo.handlers import error_report
from sillo.testclient import TestClient

PLAIN = Palette(enabled=False)


def _raise(fn):
    try:
        fn()
    except Exception as exc:
        return exc
    raise AssertionError("fn did not raise")


def _ctx(method: str, path: str) -> SimpleNamespace:
    return SimpleNamespace(
        method=method, scope={"path": path}, url=SimpleNamespace(path=path)
    )


# ── trace_mode ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "env,debug,expected",
    [
        (None, True, "app"),
        ("off", True, "off"),
        ("full", False, "full"),
        ("nonsense", True, "app"),
    ],
)
def test_trace_mode_follows_env_then_debug(monkeypatch, env, debug, expected):
    if env is None:
        monkeypatch.delenv("SILLO_TRACE", raising=False)
    else:
        monkeypatch.setenv("SILLO_TRACE", env)
    assert error_report.trace_mode(debug) == expected


def test_trace_mode_with_debug_off_follows_terminal(monkeypatch):
    """Off a terminal, `debug=False` still means the block is skipped."""
    monkeypatch.delenv("SILLO_TRACE", raising=False)
    monkeypatch.setattr(error_report.sys.stderr, "isatty", lambda: False)
    assert error_report.trace_mode(False) == "off"


def test_trace_mode_with_debug_off_shows_at_a_real_terminal(monkeypatch):
    """`debug=False` no longer silences the trace at an actual terminal —
    only the client-facing debug page is gated by `debug`."""
    monkeypatch.delenv("SILLO_TRACE", raising=False)
    monkeypatch.setattr(error_report.sys.stderr, "isatty", lambda: True)
    assert error_report.trace_mode(False) == "app"


# ── the block ───────────────────────────────────────────────────────────


def test_first_line_is_emoji_word_type_and_message():
    exc = _raise(lambda: (_ for _ in ()).throw(ValueError("seat 12A is taken")))
    first = error_report.render(exc, palette=PLAIN).splitlines()[0]
    assert first == "💥 oops — ValueError: seat 12A is taken"


def test_calling_frames_are_one_line_the_broken_frame_gets_a_window(
    tmp_path, monkeypatch
):
    (tmp_path / "erp_frames.py").write_text(
        "def outer():\n"
        "    inner()\n"
        "\n"
        "def inner():\n"
        "    value = 1\n"
        "    raise RuntimeError('nope')\n"
    )
    monkeypatch.setenv("SILLO_APP_ROOT", str(tmp_path))
    monkeypatch.syspath_prepend(str(tmp_path))
    import importlib

    block = error_report.render(
        _raise(importlib.import_module("erp_frames").outer), palette=PLAIN
    )

    assert "at        erp_frames.py:2   in outer" in block
    assert "→ inner()" in block  # the calling frame: one line
    assert "at        erp_frames.py:6   in inner" in block
    # the broken frame: numbered window, the raising line marked
    lines = block.splitlines()
    ctx_5 = next(ln for ln in lines if ln.rstrip().endswith("value = 1"))
    marked = next(ln for ln in lines if "raise RuntimeError('nope')" in ln)
    assert ctx_5.lstrip().startswith("5")  # a plain numbered context line
    assert marked.lstrip().startswith("›")  # the raising line, marked
    assert "6" in marked


@pytest.mark.skipif(
    sys.version_info < (3, 11),
    reason="fine-grained error locations (PEP 657) are 3.11+",
)
def test_the_caret_underlines_the_failing_expression(tmp_path, monkeypatch):
    (tmp_path / "erp_caret.py").write_text(
        "def price(catalog, sku):\n    return catalog['items'][sku]\n"
    )
    monkeypatch.setenv("SILLO_APP_ROOT", str(tmp_path))
    monkeypatch.syspath_prepend(str(tmp_path))
    import importlib

    block = error_report.render(
        _raise(lambda: importlib.import_module("erp_caret").price({"items": {}}, "X")),
        palette=PLAIN,
    )
    lines = block.splitlines()
    src_i = next(
        i for i, ln in enumerate(lines) if "return catalog['items'][sku]" in ln
    )
    caret = lines[src_i + 1]
    assert set(caret.strip()) == {"^"}
    # the carets sit under `catalog['items'][sku]`, not the leading `return `
    assert caret.index("^") == lines[src_i].index("catalog['items'][sku]")


def test_request_line_is_shown_when_a_context_is_given():
    block = error_report.render(
        _raise(lambda: 1 / 0), _ctx("POST", "/pay"), palette=PLAIN
    )
    assert "    request   POST /pay" in block


def test_no_request_line_without_a_context(tmp_path, monkeypatch):
    # app root at an empty dir → no frame windows to pull stray words from
    monkeypatch.setenv("SILLO_APP_ROOT", str(tmp_path))
    block = error_report.render(_raise(lambda: 1 / 0), palette=PLAIN)
    assert "request" not in block


def test_chained_cause_gets_its_own_box():
    def inner():
        try:
            {}["k"]
        except KeyError as missing:
            raise ValueError("wrapped") from missing

    block = error_report.render(_raise(inner), palette=PLAIN)
    lines = block.splitlines()
    assert any(ln.lstrip().startswith("caused by") for ln in lines)
    boxed = "\n".join(lines)
    assert "╭" in boxed and "╰" in boxed
    assert "KeyError: 'k'" in boxed


def test_with_line_lists_the_raising_frames_locals(tmp_path, monkeypatch):
    (tmp_path / "erp_locals.py").write_text(
        "def book(flight, label, hold_token='tok_x'):\n"
        "    rows = [1, 2, 3]\n"
        "    raise RuntimeError('taken')\n"
    )
    monkeypatch.setenv("SILLO_APP_ROOT", str(tmp_path))
    monkeypatch.syspath_prepend(str(tmp_path))
    import importlib

    svc = importlib.import_module("erp_locals")
    block = error_report.render(_raise(lambda: svc.book("BA1", "12A")), palette=PLAIN)
    with_line = next(ln for ln in block.splitlines() if ln.lstrip().startswith("with"))
    assert "flight='BA1'" in with_line
    assert "label='12A'" in with_line
    assert "rows=[1, 2, 3]" in with_line
    assert "hold_token=***" in with_line  # redacted by name


def test_a_big_container_local_is_summarised_by_length(tmp_path, monkeypatch):
    (tmp_path / "erp_big.py").write_text(
        "def go():\n"
        "    payload = {'k%d' % i: i for i in range(50)}\n"
        "    raise RuntimeError('x')\n"
    )
    monkeypatch.setenv("SILLO_APP_ROOT", str(tmp_path))
    monkeypatch.syspath_prepend(str(tmp_path))
    import importlib

    big = importlib.import_module("erp_big")
    block = error_report.render(_raise(big.go), palette=PLAIN)
    assert "payload=<dict len=50>" in block


def test_no_error_id_or_footer(tmp_path, monkeypatch):
    monkeypatch.setenv("SILLO_APP_ROOT", str(tmp_path))
    block = error_report.render(_raise(lambda: 1 / 0), _ctx("GET", "/x"), palette=PLAIN)
    assert "err_" not in block
    assert "SILLO_TRACE" not in block


def test_full_mode_appends_the_raw_traceback():
    block = error_report.render(_raise(lambda: 1 / 0), palette=PLAIN, mode="full")
    assert "Traceback (most recent call last)" in block
    assert "ZeroDivisionError" in block


def test_an_error_wholly_inside_a_dependency_still_shows_a_frame():
    # json.loads raises entirely within the stdlib
    import json

    block = error_report.render(_raise(lambda: json.loads("{")), palette=PLAIN)
    assert "\n    at        " in block


def test_a_deep_chain_boxes_the_first_few_links_then_summarises():
    def raise_chain(n):
        if n == 0:
            raise ValueError("root cause")
        try:
            raise_chain(n - 1)
        except Exception as e:
            raise RuntimeError(f"level {n}") from e

    block = error_report.render(_raise(lambda: raise_chain(8)), palette=PLAIN)
    assert block.count("caused by") == error_report._CAUSE_LIMIT
    assert block.count("╭") == error_report._CAUSE_LIMIT
    assert "… 4 more" in block
    assert "level 4" in block  # the last boxed link
    assert "level 3" not in block  # folded into the summary


def test_a_short_chain_is_fully_boxed_with_no_summary():
    def inner():
        try:
            {}["k"]
        except KeyError as missing:
            raise ValueError("wrapped") from missing

    block = error_report.render(_raise(inner), palette=PLAIN)
    assert "more" not in block


def test_a_long_message_or_name_is_clipped_to_stay_inside_the_box():
    # A wide class name, message, path or function name used to push text
    # straight past the box's right-hand border instead of being trimmed.
    class ThisIsAnAbsurdlyLongCustomExceptionClassNameForTestingPurposes(Exception):
        pass

    def inner():
        try:
            {}["a-rather-long-dictionary-key-that-would-never-normally-show-up"]
        except KeyError as missing:
            raise ThisIsAnAbsurdlyLongCustomExceptionClassNameForTestingPurposes(
                "a very long exception message that goes on and on and on well "
                "past what any box drawn to a terminal could reasonably hold"
            ) from missing

    block = error_report.render(_raise(inner), palette=PLAIN)
    box_lines = [ln for ln in block.splitlines() if "│" in ln]
    assert box_lines  # sanity: a box was actually drawn
    widths = {len(ln) for ln in box_lines}
    assert len(widths) == 1  # every row of every box is the same width
    for ln in box_lines:
        assert ln.startswith(f"    {'│'}")
        assert ln.endswith("│")


# ── one_line / emit ─────────────────────────────────────────────────────


def test_one_line_is_greppable_and_has_no_id():
    exc = _raise(lambda: (_ for _ in ()).throw(ValueError("boom")))
    line = error_report.one_line(exc, _ctx("GET", "/x"))
    assert line.startswith("500 GET /x ValueError: boom")
    assert "err_" not in line and "\n" not in line


def test_emit_writes_nothing_to_a_non_terminal_but_returns_the_line(capsys):
    line = error_report.emit(_raise(lambda: 1 / 0), None, debug=True)
    assert line.startswith("500") and "ZeroDivisionError" in line
    assert capsys.readouterr().err == ""


def test_emit_respects_trace_off(monkeypatch, capsys):
    monkeypatch.setenv("SILLO_TRACE", "off")
    error_report.emit(_raise(lambda: 1 / 0), None, debug=True)
    assert capsys.readouterr().err == ""


def test_emit_writes_the_block_to_a_terminal(monkeypatch):
    import io

    class Tty(io.StringIO):
        def isatty(self):
            return True

    fake = Tty()
    monkeypatch.setattr(error_report.sys, "stderr", fake)
    error_report.emit(_raise(lambda: 1 / 0), _ctx("GET", "/x"), debug=True)
    assert "💥 oops" in fake.getvalue()


# ── helper branches ────────────────────────────────────────────────────


def test_line_and_context_readers_degrade_on_a_bad_target():
    assert error_report._line_at("/no/such/file.py", 1) == ""
    assert error_report._line_at(__file__, 10**7) == ""
    assert error_report._context("/no/such/file.py", 1) == ([], 0)
    assert error_report._context(__file__, 10**7) == ([], 0)


def test_line_at_reassembles_a_call_split_across_lines(tmp_path):
    f = tmp_path / "c.py"
    f.write_text("x = dict(\n    a=1,\n)\n")
    assert error_report._line_at(str(f), 1) == "x = dict( a=1, )"


def test_caret_is_skipped_without_column_info():
    fs = SimpleNamespace(lineno=1, end_lineno=1, colno=None, end_colno=None)
    assert error_report._caret(fs, 0) is None
    fs = SimpleNamespace(lineno=1, end_lineno=1, colno=200, end_colno=210)
    assert error_report._caret(fs, 0) is None  # past the trimmed width


def test_cause_falls_back_to_implicit_context():
    def inner():
        try:
            {}["k"]
        except KeyError:
            raise ValueError("wrapped")  # no `from` -> __context__

    block = error_report.render(_raise(inner), palette=PLAIN)
    assert "caused by" in block
    assert "KeyError" in block


def test_short_repr_covers_the_odd_shapes():
    class Sized:
        def __len__(self):
            return 3

    class Broken:
        def __len__(self):
            raise RuntimeError

    class Plain:
        pass

    assert error_report._short_repr(Sized()) == "<Sized len=3>"
    assert error_report._short_repr(Broken()) == "<Broken>"
    assert error_report._short_repr(Plain()) == "<Plain>"
    assert error_report._short_repr("z" * 80).endswith("…")


def test_locals_line_edge_cases():
    import os as _os

    assert error_report._locals_line(None) == ""

    frame = SimpleNamespace(
        f_locals={
            "self": object(),
            "__hidden__": 1,
            "mod": _os,
            "a": 1,
            "b": 2,
            "c": 3,
            "d": 4,
            "e": 5,
            "f": 6,
            "g": 7,
        }
    )
    line = error_report._locals_line(frame)
    assert "self=" not in line and "__hidden__" not in line  # skipped
    assert "mod=" not in line  # a module is skipped
    assert line.count("=") == 6  # capped at six


def test_render_falls_back_to_one_line_when_source_is_unreadable(monkeypatch):
    monkeypatch.setattr(error_report, "_context", lambda *a, **k: ([], 0))
    block = error_report.render(_raise(lambda: 1 / 0), palette=PLAIN)
    # no numbered window, but still a marked line for the broken frame
    assert "›" in block


# ── end to end ─────────────────────────────────────────────────────────


def test_a_500_logs_exactly_one_structured_line(caplog):
    app = SilloApp(debug=False)

    @app.get("/boom")
    async def boom(ctx: HttpContext):
        raise ValueError("kaboom")

    with caplog.at_level("ERROR", logger="sillo"):
        resp = TestClient(app).get("/boom")

    assert resp.status_code == 500
    hits = [r for r in caplog.records if "kaboom" in r.getMessage()]
    assert len(hits) == 1
    assert hits[0].getMessage().startswith("500 GET /boom ValueError: kaboom")


def test_an_error_after_the_response_started_is_logged_and_reraised(caplog):
    from sillo.responses import stream

    app = SilloApp(debug=False)

    async def chunks():
        yield b"partial "
        raise RuntimeError("mid-stream")

    @app.get("/leak")
    async def leak(ctx: HttpContext):
        return stream(chunks())

    with caplog.at_level("ERROR", logger="sillo"), pytest.raises(RuntimeError):
        TestClient(app).get("/leak")

    assert any(
        "after the response had started" in r.getMessage() for r in caplog.records
    )
