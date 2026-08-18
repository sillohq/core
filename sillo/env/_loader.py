"""Read ``.env`` files.

Sillo parses ``.env`` itself. Nothing in this module imports ``python-dotenv``,
and no application needs it installed: :class:`sillo.config.Config` and
:class:`sillo.SilloApp` both call :func:`autoload` on the way up, so the
variables a project keeps in ``.env`` are in ``os.environ`` before the first
line of application code reads one.

The grammar
-----------

::

    KEY=value                     # bare, everything to end of line
    KEY="value"                   # escapes and ${REFERENCES} resolved
    KEY='value'                   # taken literally, nothing resolved
    KEY=\"\"\"multi              # newlines belong to the value
    line\"\"\"
    export KEY=value              # the prefix is dropped
    # a comment                   # whole-line comments are skipped
    KEY=value # trailing comment  # needs the space; `a#b` is the value `a#b`

References resolve against names defined earlier in the same file first, then
against the surrounding environment. ``${NAME:-fallback}`` supplies a value
when ``NAME`` is unset or empty, ``${NAME-fallback}`` only when it is unset,
and an unresolved reference becomes the empty string. Write ``\\$`` (or use a
single-quoted value) for a literal dollar sign — the case that otherwise
mangles passwords.

Precedence
----------

A variable already present in the real environment wins over the file, so a
deploy that exports ``DATABASE_URL`` beats a ``.env`` left in the image. Pass
``override=True`` to reverse that.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping, MutableMapping
from pathlib import Path
from typing import Any

__all__ = [
    "autoload",
    "env",
    "find_env",
    "load_env",
    "parse_env",
]

#: The file looked for when no path is given.
DEFAULT_ENV_FILE = ".env"

#: Points :func:`autoload` at a different file. Set it to the empty string to
#: turn automatic loading off entirely.
ENV_FILE_VARIABLE = "SILLO_ENV_FILE"

#: The upward search for a ``.env`` stops at the directory holding one of
#: these, so a stray ``~/.env`` never leaks into a project.
ROOT_MARKERS = ("pyproject.toml", "uv.lock", "setup.py", "setup.cfg", ".git")

_TRUE = frozenset({"1", "true", "t", "yes", "y", "on"})
_FALSE = frozenset({"0", "false", "f", "no", "n", "off", ""})

# `\<newline>` maps to "" so a double-quoted value can be wrapped over lines.
_ESCAPES = {
    "n": "\n",
    "r": "\r",
    "t": "\t",
    "b": "\b",
    "f": "\f",
    "v": "\v",
    "0": "\0",
    "a": "\a",
    "\\": "\\",
    '"': '"',
    "'": "'",
    "$": "$",
    "`": "`",
    "\n": "",
}

_MISSING: Any = object()


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def _is_key(key: str) -> bool:
    """Whether *key* is a usable environment variable name."""
    return key.isascii() and key.isidentifier()


def _end_of_line(text: str, index: int) -> int:
    """Index just past the newline that ends the line containing *index*."""
    newline = text.find("\n", index)
    return len(text) if newline == -1 else newline + 1


def _lookup(
    name: str,
    values: Mapping[str, str],
    environ: Mapping[str, str],
) -> str | None:
    """Resolve *name*, the file's own values first."""
    if name in values:
        return values[name]
    return environ.get(name)


def _reference(
    text: str,
    index: int,
    values: Mapping[str, str],
    environ: Mapping[str, str],
) -> tuple[str, int]:
    """Resolve the reference starting at ``text[index] == '$'``.

    Returns the replacement text and the index just past the reference. A
    ``$`` that begins nothing recognisable is returned as itself.
    """
    if index + 1 >= len(text):
        return "$", index + 1

    if text[index + 1] == "{":
        close = text.find("}", index + 2)
        if close == -1:
            return "$", index + 1
        body = text[index + 2 : close]
        after = close + 1

        if ":-" in body:
            name, _, fallback = body.partition(":-")
            resolved = _lookup(name, values, environ)
            return (fallback if not resolved else resolved), after
        if "-" in body:
            name, _, fallback = body.partition("-")
            resolved = _lookup(name, values, environ)
            return (fallback if resolved is None else resolved), after

        return (_lookup(body, values, environ) or ""), after

    end = index + 1
    while end < len(text) and (text[end].isalnum() or text[end] == "_"):
        end += 1
    if end == index + 1:
        return "$", index + 1
    return (_lookup(text[index + 1 : end], values, environ) or ""), end


def _interpolate(
    raw: str,
    values: Mapping[str, str],
    environ: Mapping[str, str],
    *,
    escapes: bool,
) -> str:
    """Resolve escapes and references in one pass.

    One pass rather than two because unescaping first would turn ``\\$HOME``
    into a reference to ``HOME`` instead of the literal text the backslash
    asked for.
    """
    out: list[str] = []
    i = 0
    while i < len(raw):
        char = raw[i]
        if char == "\\" and i + 1 < len(raw):
            following = raw[i + 1]
            if escapes:
                # An unknown escape keeps both characters: a Windows path in
                # a quoted value stays the path it looks like.
                out.append(_ESCAPES.get(following, "\\" + following))
                i += 2
                continue
            if following == "$":
                out.append("$")
                i += 2
                continue
        if char == "$":
            replacement, i = _reference(raw, i, values, environ)
            out.append(replacement)
            continue
        out.append(char)
        i += 1
    return "".join(out)


def _strip_comment(raw: str) -> str:
    """Drop a trailing ``# comment`` from an unquoted value.

    The ``#`` has to follow whitespace, so ``KEY=pass#word`` keeps its hash
    the way every shell and ``python-dotenv`` do.
    """
    for position, char in enumerate(raw):
        if char == "#" and (position == 0 or raw[position - 1] in " \t"):
            return raw[:position]
    return raw


def _read_value(
    text: str,
    index: int,
    values: Mapping[str, str],
    environ: Mapping[str, str],
) -> tuple[str, int]:
    """Read the value starting at *index*, returning it and the next index."""
    while index < len(text) and text[index] in " \t":
        index += 1

    for quote in ('"""', "'''"):
        if text.startswith(quote, index):
            close = text.find(quote, index + 3)
            if close == -1:
                # Unterminated: take the rest of the file rather than lose it.
                body, after = text[index + 3 :], len(text)
            else:
                body, after = text[index + 3 : close], _end_of_line(text, close + 3)
            if quote == "'''":
                return body, after
            return _interpolate(body, values, environ, escapes=True), after

    if index < len(text) and text[index] in "\"'":
        quote = text[index]
        cursor = index + 1
        chunk: list[str] = []
        while cursor < len(text):
            char = text[cursor]
            if char == "\\" and quote == '"' and cursor + 1 < len(text):
                chunk.append(text[cursor : cursor + 2])
                cursor += 2
                continue
            if char == quote:
                body = "".join(chunk)
                after = _end_of_line(text, cursor + 1)
                if quote == "'":
                    return body, after
                return _interpolate(body, values, environ, escapes=True), after
            chunk.append(char)
            cursor += 1
        # Unterminated quote: treat the opener as part of a bare value.

    stop = _end_of_line(text, index)
    raw = text[index:stop].rstrip("\n").rstrip("\r")
    raw = _strip_comment(raw).strip()
    return _interpolate(raw, values, environ, escapes=False), stop


def parse_env(text: str, *, environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """Parse the contents of a ``.env`` file.

    Pure: nothing is written to the process environment. Lines that are not
    ``KEY=value`` are skipped rather than raising, because a half-typed line
    in a ``.env`` should not stop an application from booting.

    Args:
        text: The file's contents.
        environ: What ``${REFERENCES}`` fall back to once the file's own
            values are exhausted. Defaults to ``os.environ``. Pass ``{}`` to
            resolve against the file alone.

    Returns:
        The variables the file defines, in the order they appear. A key
        repeated in the file keeps its last value.
    """
    surroundings = os.environ if environ is None else environ
    values: dict[str, str] = {}

    index = 0
    if text.startswith("﻿"):
        index = 1

    while index < len(text):
        char = text[index]
        if char in " \t\r\n":
            index += 1
            continue
        if char == "#":
            index = _end_of_line(text, index)
            continue

        start = index
        while index < len(text) and text[index] not in "=\r\n":
            index += 1
        if index >= len(text) or text[index] != "=":
            index = _end_of_line(text, index)
            continue

        key = text[start:index].strip()
        index += 1
        if key.startswith(("export ", "export\t")):
            key = key[6:].lstrip()

        value, index = _read_value(text, index, values, surroundings)
        if _is_key(key):
            values[key] = value

    return values


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------


def find_env(
    name: str = DEFAULT_ENV_FILE,
    start: str | os.PathLike[str] | None = None,
) -> Path | None:
    """Search *start* and its parents for an env file.

    The walk stops at the first directory holding one of :data:`ROOT_MARKERS`,
    so running a command from ``project/app/handlers`` finds the project's
    ``.env`` while a file in the user's home directory is never picked up.

    Args:
        name: The file name to look for.
        start: Where to begin. Defaults to the working directory.

    Returns:
        The path found, or ``None``.
    """
    try:
        directory = Path(start or os.getcwd()).resolve()
    except OSError:
        return None

    for candidate in (directory, *directory.parents):
        target = candidate / name
        if target.is_file():
            return target
        if any((candidate / marker).exists() for marker in ROOT_MARKERS):
            return None
    return None


def load_env(
    path: str | os.PathLike[str] | None = None,
    *,
    override: bool = False,
    search: bool = True,
    environ: MutableMapping[str, str] | None = None,
) -> dict[str, str]:
    """Load an env file into the process environment.

    A missing or unreadable file is not an error — most projects have no
    ``.env`` in production, where the variables are exported by the platform.

    Args:
        path: The file to read. ``None`` looks for ``.env``.
        override: Whether file values replace variables that are already set.
            Off by default: the real environment is the more specific source.
        search: Whether ``None`` should search parent directories
            (:func:`find_env`) or only look in the working directory.
        environ: The mapping to write to. Defaults to ``os.environ``.

    Returns:
        The variables that were applied, which excludes any the environment
        already had unless *override* was set.
    """
    target = os.environ if environ is None else environ

    if path is None:
        found = find_env() if search else Path(DEFAULT_ENV_FILE)
        if found is None or not found.is_file():
            return {}
        source = found
    else:
        source = Path(path)

    try:
        text = source.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}

    applied: dict[str, str] = {}
    for key, value in parse_env(text, environ=target).items():
        if override or key not in target:
            target[key] = value
            applied[key] = value
    return applied


#: Files :func:`autoload` has already read, so constructing a hundred configs
#: reads the file once.
_loaded: set[Path] = set()


def autoload() -> Path | None:
    """Load the project's ``.env`` once.

    Called by :class:`sillo.SilloApp` and :class:`sillo.config.Config`, which
    is what makes ``.env`` work without an application doing anything. Set
    ``SILLO_ENV_FILE`` to load a different file, or to the empty string to
    switch automatic loading off.

    Returns:
        The file that was loaded or had already been loaded, or ``None``.
    """
    configured = os.environ.get(ENV_FILE_VARIABLE)
    if configured is not None and not configured.strip():
        return None

    if configured:
        candidate = Path(configured)
        if not candidate.is_file():
            return None
    else:
        candidate = find_env() or Path(DEFAULT_ENV_FILE)
        if not candidate.is_file():
            return None

    resolved = candidate.resolve()
    if resolved in _loaded:
        return resolved

    load_env(resolved)
    _loaded.add(resolved)
    return resolved


def _reset_autoload() -> None:
    """Forget which files :func:`autoload` has read. For tests."""
    _loaded.clear()


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------


def _to_bool(raw: str) -> bool:
    """Read a boolean the way a ``.env`` file writes one."""
    lowered = raw.strip().lower()
    if lowered in _TRUE:
        return True
    if lowered in _FALSE:
        return False
    raise ValueError(f"{raw!r} is not a boolean")


def env(
    key: str,
    default: Any = _MISSING,
    *,
    cast: Callable[[str], Any] | None = None,
) -> Any:
    """Read one environment variable, with a type.

    For the odd value that does not deserve a :class:`~sillo.config.Config`
    class::

        from sillo.env import env

        port = env("PORT", 8000, cast=int)
        debug = env("DEBUG", False, cast=bool)
        secret = env("JWT_SECRET")          # raises if it is not set

    Args:
        key: The variable name.
        default: Returned unchanged when the variable is unset. Omit it to
            make the variable required.
        cast: Applied to the string. ``bool`` understands ``true/yes/on/1``
            and their opposites rather than Python's "any non-empty string".

    Returns:
        The cast value, or *default*.

    Raises:
        KeyError: If the variable is unset and no default was given.
        ValueError: If *cast* rejects the value.
    """
    if key not in os.environ:
        if default is _MISSING:
            raise KeyError(f"{key} is not set, and has no default")
        return default

    raw = os.environ[key]
    if cast is None:
        return raw
    if cast is bool:
        return _to_bool(raw)
    try:
        return cast(raw)
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"{key}={raw!r} is not a valid {getattr(cast, '__name__', cast)}: {error}"
        ) from error
