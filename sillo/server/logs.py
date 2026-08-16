"""Sillo's log presentation for the ASGI server.

uvicorn talks about itself. It announces "Started server process", "Waiting for
application startup." and "Uvicorn running on http://…", which is correct and
also tells a Sillo user about a component they did not choose and cannot see.
This module replaces that voice without replacing the server.

Two things happen here. A :class:`Translator` filter sits on ``uvicorn.error``
and rewrites or drops each message uvicorn emits, matched on the *format
string* rather than the rendered text so the match is exact and does not depend
on the arguments. A :class:`SilloFormatter` then renders whatever survives in
the server's own layout.

Anything uvicorn emits that is not in the table passes through untouched with a
mapped level. That is deliberate: a warning about an unsupported upgrade header
or a failed binding is exactly the message a user needs, and silently swallowing
unrecognised output to keep the log pretty would be the wrong trade.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any, Union

from sillo.server import theme

#: A translation's replacement: either a format string taking the record's
#: original arguments, or a callable reshaping them into a new pair.
Replacement = Union[str, Callable[[tuple], "tuple[str, tuple]"]]

#: What to do with one of uvicorn's messages: drop it, or restate it.
Action = Union[tuple[str, Replacement], None]

#: Level name shown for each Python logging level.
_LEVEL_NAMES: dict[int, str] = {
    logging.DEBUG: "debug",
    logging.INFO: "info",
    logging.WARNING: "warn",
    logging.ERROR: "error",
    logging.CRITICAL: "error",
}

#: Width of the level column, so messages start at a fixed offset.
_LEVEL_WIDTH = 7

def _watching(args: tuple) -> tuple[str, tuple]:
    """Render the reloader's watch list as paths rather than a list repr.

    uvicorn passes the directories as a Python list, so the default rendering
    is ``watching [PosixPath('/srv/app')]`` — a repr of an internal data
    structure, in a line meant to tell someone which folder to edit.

    Args:
        args: The record's original arguments.

    Returns:
        ``(template, args)`` naming the directories relative to the working
        directory where that is shorter, which it almost always is.
    """
    import os

    directories = args[0] if args else []
    if not isinstance(directories, (list, tuple)):
        directories = [directories]

    shown = []
    for directory in directories:
        text = str(directory)
        try:
            relative = os.path.relpath(text)
            shown.append(relative if len(relative) < len(text) else text)
        except ValueError:
            shown.append(text)

    return "watching %s", (", ".join(shown) or "the working directory",)


def _changed(args: tuple) -> tuple[str, tuple]:
    """Name the file that changed, dropping the reloader's own name.

    uvicorn's message is ``"%s detected changes in %s. Reloading..."`` and its
    first argument is the watcher's class name — "StatReload", "WatchFiles" —
    an implementation detail of the thing doing the watching rather than
    information about the change. Passing both through a one-placeholder
    template is also a ``TypeError`` at format time, which surfaces as a
    logging error rather than a reload notice.

    Args:
        args: The record's original arguments.

    Returns:
        ``(template, args)`` naming only the changed path, unquoted.
    """
    changed = args[-1] if args else "a file"
    return "%s changed, reloading", (str(changed).strip("'\""),)


#: How uvicorn's own messages are handled.
#:
#: Keys are uvicorn's format strings, verbatim. A value of ``None`` drops the
#: record, which is right for anything the banner or the shutdown card already
#: says — repeating it in a log line is noise, not redundancy. Otherwise the
#: value is ``(level, template)``, where the template is either a format string
#: taking the record's original arguments or a callable returning a new
#: ``(template, args)`` pair for the cases that need reshaping.
TRANSLATIONS: dict[str, Action] = {
    # Startup. The banner reports the address, the pid and the elapsed time,
    # so none of this needs saying twice.
    "Started server process [%d]": None,
    "Waiting for application startup.": None,
    "Application startup complete.": None,
    "Uvicorn running on %s://%s:%d (Press CTRL+C to quit)": None,
    "Uvicorn running on socket %s (Press CTRL+C to quit)": None,
    "Uvicorn running on unix socket %s (Press CTRL+C to quit)": None,
    # Shutdown. The card prints the summary; the intermediate steps are only
    # interesting when one of them hangs, and then the last line printed is
    # the one that hung.
    "Shutting down": ("stop", "shutting down"),
    "Waiting for application shutdown.": None,
    "Application shutdown complete.": None,
    "Finished server process [%d]": None,
    "Waiting for connections to close. (CTRL+C to force quit)": (
        "stop",
        "waiting for open connections to finish — ctrl-c again to force",
    ),
    # Reload. The interesting one is the change notification; the reloader's
    # own lifecycle is not.
    "Will watch for changes in these directories: %s": ("reload", _watching),
    "Detected file change in '%s'. Reloading...": ("reload", _changed),
    "%s detected changes in %s. Reloading...": ("reload", _changed),
}

#: Messages uvicorn builds with an f-string rather than a format string.
#:
#: Those arrive already rendered, so ``record.msg`` carries the pid and the
#: reloader name inline and there is no stable key to match on. Matched by
#: prefix instead. Both of these are dropped: the banner already reports the
#: pid, and that reload is on.
PREFIXES: dict[str, Action] = {
    "Started reloader process": None,
    "Stopping reloader process": None,
    "Started parent process": None,
    "Stopping parent process": None,
    "Started child process": None,
    "Stopping child process": None,
}


class Translator(logging.Filter):
    """Rewrites uvicorn's messages into Sillo's, or drops them.

    Attached to ``uvicorn.error``. Mutates the record in place, which is safe
    here because these records go to exactly one handler and are not reused.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Translate one record.

        Args:
            record: The record uvicorn emitted.

        Returns:
            ``False`` to drop the record, ``True`` to let it through — with
            ``record.msg`` and ``record.sillo_level`` rewritten when there is a
            translation for it.
        """
        message = str(record.msg)
        translation = TRANSLATIONS.get(message, _MISSING)

        if translation is _MISSING:
            for prefix, action in PREFIXES.items():
                if message.startswith(prefix):
                    translation = action
                    break

        if translation is None:
            return False

        if translation is not _MISSING:
            level, template = translation
            if isinstance(template, str):
                # A template with no placeholders must be given no arguments.
                if "%" not in template:
                    record.args = ()
                record.msg = template
            else:
                reshape: Callable[[tuple], tuple[str, tuple]] = template
                # `record.args` is a tuple for %-style logging and a mapping
                # for the dict form. Only the tuple form reaches here, and
                # coercing rather than asserting keeps a surprising record from
                # taking the server down over a log line.
                args = record.args if isinstance(record.args, tuple) else ()
                record.msg, record.args = reshape(args)
            record.sillo_level = level
            return True

        # Not in the table: uvicorn is saying something we did not anticipate,
        # which is precisely when the user needs to see it.
        record.sillo_level = _LEVEL_NAMES.get(record.levelno, "info")
        return True


#: Distinguishes "no translation" from "translated to None", which mean
#: opposite things and would otherwise collide on a ``dict.get`` default.
_MISSING: Any = object()


class SilloFormatter(logging.Formatter):
    """Renders a log record in the server's layout.

    ``HH:MM:SS  level    message``, with the level column padded to a fixed
    width so messages align down the page and the eye can run past the
    timestamps.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Render one record.

        Args:
            record: The record to render, already translated.

        Returns:
            The line to write, styled if the stream takes it.
        """
        level = getattr(record, "sillo_level", None) or _LEVEL_NAMES.get(
            record.levelno, "info"
        )
        message = record.getMessage()

        stamp = theme.paint(
            time.strftime("%H:%M:%S", time.localtime(record.created)),
            theme.TIMESTAMP,
        )
        tag = theme.paint(level.ljust(_LEVEL_WIDTH), theme.LEVELS.get(level))

        line = f"  {stamp}  {tag} {message}"

        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


def logging_config(level: str = "info") -> dict:
    """Build the logging configuration the server installs.

    Replaces uvicorn's ``LOGGING_CONFIG`` wholesale rather than patching it.
    ``uvicorn.access`` is silenced here and not merely restyled: the server
    emits its own access lines from :mod:`sillo.server.access`, which have a
    duration uvicorn's records do not carry.

    Args:
        level: Lowest level to emit, as a level name.

    Returns:
        A ``logging.config.dictConfig`` document.

    Note:
        ``disable_existing_loggers`` is ``False``. Setting it true is uvicorn's
        default and it silences every logger the application configured before
        the server started, which for a Sillo app means its own.
    """
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "sillo": {"()": "sillo.server.logs.SilloFormatter"},
        },
        "filters": {
            "translate": {"()": "sillo.server.logs.Translator"},
        },
        "handlers": {
            "sillo": {
                "class": "logging.StreamHandler",
                "formatter": "sillo",
                "filters": ["translate"],
                "stream": "ext://sys.stderr",
            },
        },
        "loggers": {
            "uvicorn": {"handlers": [], "level": level.upper(), "propagate": False},
            "uvicorn.error": {
                "handlers": ["sillo"],
                "level": level.upper(),
                "propagate": False,
            },
            # Silenced in favour of the server's own access lines.
            "uvicorn.access": {"handlers": [], "level": "CRITICAL", "propagate": False},
        },
    }
