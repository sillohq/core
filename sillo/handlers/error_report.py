"""The block Sillo logs when a request raises and nothing handled it.

A Python traceback is a transcript — every frame, framework and stdlib and
your code weighted the same. This keeps only the frames in *your* code: each
calling frame is one line, and the frame it broke on gets a window of source
with the line marked and a caret under the exact expression.

    💥 oops — KeyError: 'ABC-9'
        request   GET /catalog/ABC-9
        at        api/catalog.py:14   in show
                  → price = lookup(catalog, sku)
        at        pricing/rules.py:2   in lookup
                     1   def lookup(catalog, sku):
                 ›   2       price = catalog["items"][sku]["price"]
                                     ^^^^^^^^^^^^^^^^^^^^^
                     3       return price * 1.2
        with      catalog={'items': {}}, sku='ABC-9'

The ``file:line`` is coloured (cyan, the line number bright), the function
name bold; the marked line's code stays bright while its neighbours dim; the
caret needs Python 3.11+ and a single-line expression. ``with`` lists the
raising frame's own locals — scalars and small containers verbatim, a big one
as ``<dict len=N>``, anything whose name reads like a secret as ``***``.

`SILLO_TRACE` sets the depth: ``off`` logs nothing here (the 500's own log
line still stands), ``app`` (the default when attached to a terminal) logs
the block, ``full`` appends the raw traceback under it. Off a terminal the
block is skipped and one structured line is logged instead — what a log
shipper wants.

This is independent of ``debug``: ``debug`` controls what a *client* can see
— the debug HTML page, a 404's own message instead of a generic one — while
this block only ever reaches the server's own terminal, so a developer
running ``debug=False`` locally still gets it.
"""

from __future__ import annotations

import os
import site
import sys
import sysconfig
import traceback
import typing

from sillo.console.style import DANGER, INFO, MUTED, PRIMARY, Palette, Style, strip_ansi

if typing.TYPE_CHECKING:
    from sillo.core.http import HttpContext

EMOJI = "💥"
WORD = "oops"
THROW = "›"
CALL = "→"

#: How many links of a `raise ... from ...` chain get their own box before
#: the rest are summarised on one line — a chain this deep is already a
#: design smell, and printing all of it just buries the top of the stack.
_CAUSE_LIMIT = 4
_BOX_WIDTH = 76

_MODES = ("off", "app", "full")
_BOLD = Style(bold=True)
_LOC = INFO  # file paths and line numbers: a readable location colour
_LOC_N = INFO | Style(bold=True)  # the line number itself

#: Local names whose value is never printed, however it is spelled.
_SECRET = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "auth",
    "cookie",
    "session",
    "credential",
    "private_key",
    "signature",
)
_STDLIB = os.path.realpath(sysconfig.get_paths()["stdlib"])
try:
    _SITE = tuple(
        os.path.realpath(p)
        for p in (*site.getsitepackages(), site.getusersitepackages())
    )
except AttributeError:  # pragma: no cover - a virtualenv without getsitepackages
    _SITE = ()


def _app_root() -> str:
    """Where the project's own code lives — ``SILLO_APP_ROOT`` or the cwd.

    Read fresh each call: the process may ``chdir`` after import, and a test
    needs to point it elsewhere.
    """
    return os.path.realpath(os.environ.get("SILLO_APP_ROOT", os.getcwd()))


def trace_mode(debug: bool) -> str:
    """Resolve ``SILLO_TRACE``: an explicit value, else follow the terminal.

    ``debug`` no longer decides this by itself. It gates what a client can
    see — nothing here ever reaches a client — so a project that (correctly)
    runs with ``debug=False`` in local development should not lose the
    pretty trace along with the debug HTML page. Attached to a real
    terminal, the block still helps; piped to a file or a log collector, one
    structured line is the right shape either way. ``debug=True`` still
    forces it on even off a terminal, for parity with what the debug HTML
    page already shows a browser.
    """
    raw = os.environ.get("SILLO_TRACE", "").strip().lower()
    if raw in _MODES:
        return raw
    if debug:
        return "app"
    at_terminal = bool(getattr(sys.stderr, "isatty", lambda: False)())
    return "app" if at_terminal else "off"


def _is_app_frame(filename: str) -> bool:
    """Whether a frame is the project's own code, not a dependency."""
    path = os.path.realpath(filename)
    if path.startswith(_STDLIB) or any(path.startswith(p) for p in _SITE):
        return False
    if f"{os.sep}sillo{os.sep}" in path:
        return False
    return path.startswith(_app_root())


def _short(filename: str) -> str:
    """A frame's path, relative to the project root when it is under it."""
    path = os.path.realpath(filename)
    root = _app_root()
    if path.startswith(root):
        return os.path.relpath(path, root)
    return os.path.basename(path)


def _line_at(filename: str, lineno: int) -> str:
    """The statement at ``lineno``, trimmed to one line.

    A statement split across lines — ``raise ValueError(\\n  "msg"\\n)`` — is
    reassembled by reading on while brackets are unbalanced, up to two extra
    lines, so the marked line is not just ``raise ValueError(``.
    """
    try:
        with open(filename, encoding="utf-8", errors="replace") as handle:
            lines = handle.read().splitlines()
    except OSError:
        return ""
    if not 1 <= lineno <= len(lines):
        return ""
    parts = [lines[lineno - 1]]
    depth = _bracket_depth(parts[0])
    extra = lineno
    while depth > 0 and extra < len(lines) and extra - lineno < 2:
        parts.append(lines[extra])
        depth += _bracket_depth(lines[extra])
        extra += 1
    text = " ".join(p.strip() for p in parts).expandtabs(4)
    return text if len(text) <= 100 else text[:99] + "…"


def _bracket_depth(text: str) -> int:
    depth = 0
    for ch in text:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
    return depth


_CONTEXT_WIDTH = 76


def _context(
    filename: str, lineno: int, radius: int = 2
) -> tuple[list[tuple[int, str]], int]:
    """A window of real source around ``lineno``.

    Returns ``(rows, dedent)`` — ``rows`` is ``(number, code)`` with the
    window's common leading whitespace removed and each line trimmed to a
    readable width; ``dedent`` is how many columns were removed, so a caret
    can be shifted to match.
    """
    try:
        with open(filename, encoding="utf-8", errors="replace") as handle:
            src = handle.read().splitlines()
    except OSError:
        return [], 0
    if not 1 <= lineno <= len(src):
        return [], 0
    lo = max(1, lineno - radius)
    hi = min(len(src), lineno + radius)
    window = [src[n - 1].expandtabs(4) for n in range(lo, hi + 1)]
    dedent = min((len(w) - len(w.lstrip()) for w in window if w.strip()), default=0)
    rows = []
    for offset, text in enumerate(window):
        code = text[dedent:].rstrip()
        if len(code) > _CONTEXT_WIDTH:
            code = code[: _CONTEXT_WIDTH - 1] + "…"
        rows.append((lo + offset, code))
    return rows, dedent


def _caret(fs: traceback.FrameSummary, dedent: int) -> tuple[int, int] | None:
    """``(start, length)`` for a caret under the exact sub-expression.

    Python 3.11+ records the column span of the failing expression on the
    ``FrameSummary``. Returned only when it sits on the one line and lands
    inside the trimmed window.
    """
    end_lineno = getattr(fs, "end_lineno", None)
    colno = getattr(fs, "colno", None)
    end_colno = getattr(fs, "end_colno", None)
    if end_lineno != fs.lineno or colno is None or end_colno is None:
        return None
    start = colno - dedent
    length = end_colno - colno
    if start < 0 or length <= 0 or start + length > _CONTEXT_WIDTH:
        return None
    return start, length


def _clip(text: str, width: int = 100) -> str:
    text = " ".join(text.split())
    return text if len(text) <= width else text[: width - 1] + "…"


def _app_frames(exc: BaseException) -> list[traceback.FrameSummary]:
    return [
        fs
        for fs in traceback.extract_tb(exc.__traceback__)
        if _is_app_frame(fs.filename)
    ]


def _cause(exc: BaseException) -> BaseException | None:
    if exc.__cause__ is not None:
        return exc.__cause__
    if exc.__context__ is not None and not exc.__suppress_context__:
        return exc.__context__
    return None


def _deepest_app_frame(exc: BaseException):
    """The live frame object for the deepest frame in the project's code.

    ``traceback.extract_tb`` throws the frames away, and locals live on the
    frame — so the traceback list is walked here directly.
    """
    tb = exc.__traceback__
    found = None
    while tb is not None:
        if _is_app_frame(tb.tb_frame.f_code.co_filename):
            found = tb.tb_frame
        tb = tb.tb_next
    return found


def _short_repr(value: object) -> str:
    """A one-glance value.

    Scalars and small containers as their own ``repr``; a big container as
    ``<dict len=42>``; anything else as ``<ClassName>``.
    """
    if isinstance(value, (str, bytes, int, float, bool)) or value is None:
        text = repr(value)
        return text if len(text) <= 48 else text[:47] + "…"
    if isinstance(value, (dict, list, tuple, set, frozenset)):
        text = repr(value)
        return text if len(text) <= 48 else f"<{type(value).__name__} len={len(value)}>"
    name = type(value).__name__
    sized = getattr(value, "__len__", None)
    if callable(sized):
        try:
            return f"<{name} len={sized()}>"
        except Exception:
            pass
    return f"<{name}>"


def _locals_line(frame) -> str:
    """A ``name=value`` summary of a frame's own locals — redacted, capped.

    Only the simple, immediately useful names: no ``self`` / ``cls``, no
    dunders, no imported modules, and anything whose name reads like a secret
    is shown as ``***``.
    """
    if frame is None:
        return ""
    pairs: list[str] = []
    for name, value in frame.f_locals.items():
        if name in ("self", "cls") or name.startswith("__"):
            continue
        if type(value).__name__ == "module":
            continue
        if any(s in name.lower() for s in _SECRET):
            pairs.append(f"{name}=***")
        else:
            pairs.append(f"{name}={_short_repr(value)}")
        if len(pairs) == 6:
            break
    return ", ".join(pairs)


def _fit(text: str, width: int) -> str:
    """Trim plain (unstyled) text to `width` columns, marking the cut.

    Called before any colour is applied to a piece — styling an
    already-fitted string can never push it back over the box's border,
    where slicing a styled string could cut an escape sequence in half.
    """
    if len(text) <= width:
        return text
    return text[: max(1, width - 1)] + "…"


def _box(lines: list[str], p: Palette, style: Style, indent: str = "    ") -> list[str]:
    """Frame `lines` in a border, so one cascade link reads as one unit.

    A chain of ``raise ... from ...`` blurs together as plain lines — the
    border is what lets the eye jump straight from one cause to the next
    without re-reading each one to find where it starts.
    """

    def c(text: str) -> str:
        return p.render(text, style)

    # Belt and braces: callers are expected to fit their own text with
    # `_fit` before colouring it, but a plain (unstyled) line that somehow
    # arrives too wide is still clipped here rather than left to spill past
    # the border -- a styled one cannot be sliced safely, so it is trusted.
    fitted = [
        line if len(line) != len(strip_ansi(line)) else _fit(line, _BOX_WIDTH)
        for line in lines
    ]
    width = min(max((len(strip_ansi(line)) for line in fitted), default=0), _BOX_WIDTH)
    top = c(f"╭{'─' * (width + 2)}╮")
    bottom = c(f"╰{'─' * (width + 2)}╯")
    side = c("│")

    out = [f"{indent}{top}"]
    for line in fitted:
        pad = " " * max(0, width - len(strip_ansi(line)))
        out.append(f"{indent}{side} {line}{pad} {side}")
    out.append(f"{indent}{bottom}")
    return out


def _cause_block(exc: BaseException, p: Palette) -> list[str]:
    """One cascade link's own compact summary: type, message, where, one line.

    Deliberately lighter than the top exception's own report — a full source
    window per link, several links deep, would be noise rather than signal.

    Every piece is trimmed to its own budget with :func:`_fit` *before* it is
    coloured, so a long class name, path or source line can never push the
    line past the box's border -- the failure mode this is guarding against
    is text spilling out past the right-hand edge, not a wasted character or
    two of slack.
    """

    def c(text: str, style: Style) -> str:
        return p.render(text, style)

    type_name = _fit(type(exc).__name__, 30)
    message = _fit(_clip(str(exc)), max(1, _BOX_WIDTH - len(type_name) - 2))
    message = message or "(no message)"
    lines = [f"{c(type_name, DANGER | _BOLD)}: {message}"]

    frames = _app_frames(exc) or traceback.extract_tb(exc.__traceback__)
    if frames:
        fs = frames[-1]
        name = _fit(fs.name, 24)
        lineno = str(fs.lineno)
        # Fixed furniture around the two variable-length pieces: "at ",
        # the ":" between path and line number, and "   in " before the
        # function name -- 10 columns total.
        fixed = len("at ") + len(":") + len("   in ")
        loc = _fit(_short(fs.filename), max(1, _BOX_WIDTH - fixed - len(name) - len(lineno)))
        where = f"{c(loc, _LOC)}{c(':', _LOC)}{c(lineno, _LOC_N)}"
        lines.append(f"{c('at', MUTED)} {where}   in {c(name, _BOLD)}")
        src = _fit(_line_at(fs.filename, fs.lineno or 0), _BOX_WIDTH - 2)
        if src:
            lines.append(f"{c(THROW, PRIMARY)} {src}")
    return lines


def render(
    exc: BaseException,
    ctx: HttpContext | None = None,
    *,
    palette: Palette | None = None,
    mode: str = "app",
) -> str:
    """Build the block for ``exc``.

    ``mode`` is ``app`` (the block) or ``full`` (the block then the raw
    traceback). A disabled ``palette`` returns plain text.
    """
    p = palette or Palette()

    def c(text: str, style: Style) -> str:
        return p.render(text, style)

    def label(word: str) -> str:
        # Pad before colouring: ANSI codes have no display width.
        return "    " + c(word.ljust(10), MUTED)

    out: list[str] = []

    # -- what broke --------------------------------------------------
    message = _clip(str(exc)) or "(no message)"
    out.append(
        f"{EMOJI} {c(WORD, PRIMARY)} — "
        f"{c(type(exc).__name__, DANGER | _BOLD)}: {message}"
    )

    if ctx is not None:
        method = getattr(ctx, "method", "?")
        path = getattr(getattr(ctx, "url", None), "path", "") or ctx.scope.get(
            "path", "?"
        )
        out.append(f"{label('request')}{method} {path}")

    # -- your frames, outermost first -----------------------------
    frames = _app_frames(exc)
    windowed = bool(frames)
    if not frames:
        # The error is entirely inside a dependency: show the deepest frame
        # as one line, without a source window — the window is a "your code"
        # affordance and this is not.
        tail = traceback.extract_tb(exc.__traceback__)
        if tail:
            frames = [tail[-1]]
    for i, fs in enumerate(frames):
        last = i == len(frames) - 1
        where = (
            f"{c(_short(fs.filename), _LOC)}{c(':', _LOC)}{c(str(fs.lineno), _LOC_N)}"
        )
        out.append(f"{label('at')}{where}   in {c(fs.name, _BOLD)}")

        if not last or not windowed:
            # A calling frame, or a dependency fallback: just the one line.
            src = _line_at(fs.filename, fs.lineno or 0)
            if src:
                mark = THROW if last else CALL
                style = PRIMARY if last else MUTED
                body = src if last else c(src, MUTED)
                out.append(f"              {c(mark, style)} {body}")
            continue

        # The frame it broke on: a window of source, the line marked, and a
        # caret under the exact expression when the interpreter recorded one.
        rows, dedent = _context(fs.filename, fs.lineno or 0)
        for n, code in rows:
            if n == fs.lineno:
                out.append(
                    f"            {c(THROW, PRIMARY)} {c(f'{n:>4}', _LOC_N)}   {code}"
                )
                span = _caret(fs, dedent)
                if span is not None:
                    start, length = span
                    # code begins at display column 21 on the line above
                    out.append(" " * (21 + start) + c("^" * length, PRIMARY))
            else:
                out.append(f"              {c(f'{n:>4}', MUTED)}   {c(code, MUTED)}")
        if not rows:  # unreadable source — fall back to one reassembled line
            src = _line_at(fs.filename, fs.lineno or 0)
            if src:
                out.append(f"            {c(THROW, PRIMARY)} {src}")

        values = _locals_line(_deepest_app_frame(exc))
        if values:
            out.append(f"{label('with')}{c(values, MUTED)}")

    # -- what it was raised from, each link its own box -----------
    cause = _cause(exc)
    seen = {id(exc)}
    depth = 0
    while cause is not None and id(cause) not in seen:
        seen.add(id(cause))
        depth += 1
        if depth > _CAUSE_LIMIT:
            remaining = 1
            rest = _cause(cause)
            while rest is not None and id(rest) not in seen:
                seen.add(id(rest))
                remaining += 1
                rest = _cause(rest)
            out.append(f"{label('from')}{c(f'… {remaining} more', MUTED)}")
            break
        out.append(f"{label('caused by')}")
        out.extend(_box(_cause_block(cause, p), p, MUTED))
        cause = _cause(cause)

    if mode == "full":
        out.append("")
        out.append(
            "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        )

    return "\n".join(out)


def one_line(exc: BaseException, ctx: HttpContext | None) -> str:
    """The single structured line for a non-terminal sink — no colour, no block."""
    frames = _app_frames(exc)
    at = f" at={_short(frames[-1].filename)}:{frames[-1].lineno}" if frames else ""
    where = ""
    if ctx is not None:
        path = getattr(getattr(ctx, "url", None), "path", "") or ctx.scope.get(
            "path", "?"
        )
        where = f" {getattr(ctx, 'method', '?')} {path}"
    return f"500{where} {type(exc).__name__}: {_clip(str(exc), 120)}{at}"


def emit(exc: BaseException, ctx: HttpContext | None, *, debug: bool) -> str:
    """Write the block to the terminal, return the one-line summary to log.

    The block goes straight to ``stderr`` — the logger's ``[time] LEVEL in
    module:`` prefix would fight the layout. When ``stderr`` is not a
    terminal, or ``SILLO_TRACE`` is ``off``, nothing is written and the
    returned line is logged instead.
    """
    mode = trace_mode(debug)
    at_terminal = bool(getattr(sys.stderr, "isatty", lambda: False)())
    if mode != "off" and at_terminal:
        sys.stderr.write(
            render(exc, ctx, palette=Palette(sys.stderr), mode=mode) + "\n"
        )
        sys.stderr.flush()
    return one_line(exc, ctx)
