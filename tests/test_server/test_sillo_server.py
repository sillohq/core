"""The Sillo server presents uvicorn as Sillo.

uvicorn still moves the bytes. What is replaced is everything a developer
reads: the lifecycle announcements, the access log, the startup output. These
tests pin the parts that are easy to break by accident — the translation table
falling out of step with uvicorn's wording, the banner losing its route count
to a middleware wrapper, and the classes drifting somewhere unpicklable, which
breaks ``--reload`` and nothing else.
"""

from __future__ import annotations

import asyncio
import io
import logging
import pickle

import pytest

from sillo.server import banner, logs, theme
from sillo.server.access import AccessLog


def _record(msg, *args, level=logging.INFO):
    """Build a log record the way uvicorn would."""
    return logging.LogRecord(
        name="uvicorn.error",
        level=level,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=args or (),
        exc_info=None,
    )


class TestTranslatingUvicornsVoice:
    def test_it_drops_what_the_banner_already_says(self):
        translator = logs.Translator()

        assert translator.filter(_record("Started server process [%d]", 1)) is False
        assert translator.filter(_record("Application startup complete.")) is False
        assert (
            translator.filter(
                _record("Uvicorn running on %s://%s:%d (Press CTRL+C to quit)",
                        "http", "127.0.0.1", 8000)
            )
            is False
        )

    def test_it_restates_shutdown_in_sillos_words(self):
        record = _record("Shutting down")

        assert logs.Translator().filter(record) is True
        assert record.getMessage() == "shutting down"
        assert record.sillo_level == "stop"

    def test_an_unrecognised_message_survives(self):
        # The whole point: a warning nobody anticipated is exactly the one a
        # user needs. Swallowing it to keep the log tidy would be the wrong
        # trade.
        record = _record("Something uvicorn has never said before", level=logging.WARNING)

        assert logs.Translator().filter(record) is True
        assert record.getMessage() == "Something uvicorn has never said before"
        assert record.sillo_level == "warn"

    def test_the_reload_notice_names_only_the_file(self):
        # uvicorn passes the watcher's class name as the first argument, and a
        # one-placeholder template would raise TypeError at format time.
        record = _record("%s detected changes in %s. Reloading...", "StatReload", "'app.py'")

        assert logs.Translator().filter(record) is True
        assert record.getMessage() == "app.py changed, reloading"

    def test_the_watch_list_is_paths_not_a_list_repr(self):
        record = _record("Will watch for changes in these directories: %s", ["/srv/app"])

        assert logs.Translator().filter(record) is True
        assert "[" not in record.getMessage()

    def test_f_string_messages_are_matched_by_prefix(self):
        # These arrive already rendered, so there is no format string to key on.
        record = _record("Started reloader process [4823] using WatchFiles")

        assert logs.Translator().filter(record) is False

    def test_a_message_with_no_placeholders_drops_its_arguments(self):
        record = _record("Shutting down", "unexpected-extra")

        assert logs.Translator().filter(record) is True
        assert record.getMessage() == "shutting down"


class TestTheFormatter:
    def test_it_renders_level_and_message(self):
        record = _record("hello")
        record.sillo_level = "info"

        line = logs.SilloFormatter().format(record)

        assert "hello" in line
        assert "info" in line

    def test_every_translated_level_has_a_style(self):
        # A translation naming a level with no style renders unpainted, which
        # is silent and only visible to someone looking at that exact line.
        named = {
            action[0]
            for action in list(logs.TRANSLATIONS.values()) + list(logs.PREFIXES.values())
            if action is not None
        }
        assert named <= set(theme.LEVELS), f"unstyled levels: {named - set(theme.LEVELS)}"


class TestTheBanner:
    def test_it_reports_the_route_count_through_wrappers(self):
        # uvicorn wraps the app in ProxyHeadersMiddleware, so reading only the
        # outermost object reports nothing.
        class Router:
            routes = [1, 2, 3]

        class App:
            router = Router()

        class Wrapper:
            def __init__(self, app):
                self.app = app

        assert banner._route_count(Wrapper(Wrapper(App()))) == 3

    def test_it_says_nothing_rather_than_zero_when_it_cannot_tell(self):
        assert banner._route_count(object()) is None

    def test_it_survives_a_self_referential_chain(self):
        class Loop:
            pass

        node = Loop()
        node.app = node

        assert banner._route_count(node) is None

    def test_the_bind_all_address_is_shown_as_something_openable(self):
        assert banner._address("0.0.0.0", 8000) == "http://localhost:8000"

    def test_ipv6_addresses_are_bracketed(self):
        assert banner._address("::1", 8000) == "http://[::1]:8000"

    def test_tls_changes_the_scheme(self):
        assert banner._address("127.0.0.1", 443, ssl=True) == "https://127.0.0.1:443"

    def test_it_names_an_object_rather_than_printing_its_repr(self):
        assert "0x" not in banner.describe_target(object())

    def test_an_import_string_is_passed_through(self):
        assert banner.describe_target("app.main:app") == "app.main:app"

    def test_it_renders_without_a_route_count(self):
        text = banner.render(target="app:app", host="127.0.0.1", port=8000)

        assert "app:app" in text
        assert "http://127.0.0.1:8000" in text
        assert "routes" not in text


class TestTheAccessLog:
    @staticmethod
    def _scope(path="/things", method="GET", query=b""):
        return {
            "type": "http",
            "method": method,
            "path": path,
            "root_path": "",
            "query_string": query,
            "headers": [],
        }

    @staticmethod
    async def _receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    def _run(self, app, scope):
        stream = io.StringIO()

        async def send(message):
            pass

        asyncio.run(AccessLog(app, stream=stream)(scope, self._receive, send))
        return stream.getvalue()

    def test_it_logs_the_method_status_and_path(self):
        async def app(scope, receive, send):
            await send({"type": "http.response.start", "status": 201, "headers": []})
            await send({"type": "http.response.body", "body": b"", "more_body": False})

        line = self._run(app, self._scope(method="POST"))

        assert "POST" in line
        assert "201" in line
        assert "/things" in line

    def test_the_query_string_is_kept(self):
        async def app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"", "more_body": False})

        assert "?q=x" in self._run(app, self._scope(query=b"q=x"))

    def test_a_crash_is_logged_before_it_propagates(self):
        # Otherwise a failing request leaves a silent gap in the log exactly
        # where the interesting thing happened.
        async def app(scope, receive, send):
            raise RuntimeError("boom")

        stream = io.StringIO()

        async def send(message):
            pass

        async def drive():
            await AccessLog(app, stream=stream)(self._scope(), self._receive, send)

        with pytest.raises(RuntimeError, match="boom"):
            asyncio.run(drive())

        assert "500" in stream.getvalue()

    def test_non_http_scopes_pass_through_unlogged(self):
        seen = []

        async def app(scope, receive, send):
            seen.append(scope["type"])

        stream = io.StringIO()

        async def send(message):
            pass

        asyncio.run(
            AccessLog(app, stream=stream)({"type": "lifespan"}, self._receive, send)
        )

        assert seen == ["lifespan"]
        assert stream.getvalue() == ""

    def test_a_closed_stream_does_not_take_the_server_down(self):
        async def app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"", "more_body": False})

        stream = io.StringIO()
        stream.close()

        async def send(message):
            pass

        # No exception: a log line is never worth a dropped request.
        asyncio.run(AccessLog(app, stream=stream)(self._scope(), self._receive, send))

    def test_long_paths_are_shortened_from_the_left(self):
        from sillo.server.access import _PATH_WIDTH, _shorten

        shortened = _shorten("/a" * 200)

        assert len(shortened) <= _PATH_WIDTH
        # The tail identifies the request; the prefix is shared by the router.
        assert shortened.endswith("/a")


class TestDurations:
    @pytest.mark.parametrize(
        ("milliseconds", "expected"),
        [(0.4, "400us"), (12.44, "12.4ms"), (2400, "2.40s")],
    )
    def test_each_magnitude_reads_naturally(self, milliseconds, expected):
        assert theme.format_duration(milliseconds) == expected

    def test_status_colour_tracks_the_response_class(self):
        assert theme.status_style(200) != theme.status_style(500)
        assert theme.status_style(404) != theme.status_style(200)


class TestTheServerClasses:
    """Reload and workers both spawn a process and pickle the config to it."""

    def test_they_are_importable_by_qualified_name(self):
        pytest.importorskip("uvicorn")
        from sillo.server import SilloConfig, SilloServer

        # Defined inside a function they would be local objects, and
        # `--reload` would fail with "Can't get local object" and nothing else.
        assert pickle.loads(pickle.dumps(SilloConfig)) is SilloConfig
        assert pickle.loads(pickle.dumps(SilloServer)) is SilloServer

    def test_importing_the_package_does_not_require_uvicorn(self):
        # A project serving with something else should not be made to install
        # uvicorn just to import sillo.server.
        import subprocess
        import sys

        probe = (
            "import sys; sys.modules['uvicorn'] = None; "
            "import sillo.server; print('ok')"
        )
        result = subprocess.run(
            [sys.executable, "-c", probe], capture_output=True, text=True, timeout=120
        )

        assert result.returncode == 0, result.stderr
        assert "ok" in result.stdout

    def test_reload_without_an_import_string_explains_itself(self):
        pytest.importorskip("uvicorn")
        from sillo.server import run

        with pytest.raises(RuntimeError, match="import string"):
            run(object(), reload=True)
