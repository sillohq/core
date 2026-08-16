"""The seams where Sillo's server meets uvicorn's.

The tests in ``test_sillo_server.py`` cover the presentation — what a line
looks like once it has been translated. These cover the wiring: that the
configuration installs Sillo's logging rather than uvicorn's, that ``load()``
puts the access logger on the outside, that the banner reaches the startup and
shutdown paths, and that ``run()`` dispatches to the right supervisor.

None of them bind a port. Everything is driven through the objects directly,
because a test that starts a real server to check which log configuration was
installed is a slow test that fails for unrelated reasons.
"""

from __future__ import annotations

import logging

import pytest

pytest.importorskip("uvicorn")

from sillo import SilloApp  # noqa: E402
from sillo.core.http import Request, Response  # noqa: E402
from sillo.server import banner, server as server_module, theme  # noqa: E402
from sillo.server._uvicorn import SilloConfig, SilloServer  # noqa: E402
from sillo.server.access import AccessLog  # noqa: E402


def _app() -> SilloApp:
    app = SilloApp(debug=False)

    @app.get("/ping")
    async def ping(request: Request, response: Response):
        return response.json({"ok": True})

    return app


class _Listener:
    """A stand-in for a bound socket, with only the method the banner reads."""

    def __init__(self, port: int = 4321) -> None:
        self._port = port

    def getsockname(self):
        return ("127.0.0.1", self._port)


class TestTheConfiguration:
    def test_it_installs_sillos_logging_when_none_was_given(self):
        # `log_config=None` is the signal. uvicorn's own parameter defaults to
        # its dict, so None is the only unambiguous way to say "ours".
        SilloConfig(_app(), log_config=None)

        handlers = logging.getLogger("uvicorn.error").handlers
        assert handlers, "uvicorn.error should have a handler"
        assert type(handlers[0].formatter).__name__ == "SilloFormatter"

    def test_a_caller_supplied_log_config_wins(self):
        marker = {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {"plain": {"format": "%(message)s"}},
            "handlers": {
                "plain": {"class": "logging.StreamHandler", "formatter": "plain"}
            },
            "loggers": {"uvicorn.error": {"handlers": ["plain"], "level": "INFO"}},
        }

        SilloConfig(_app(), log_config=marker)

        formatter = logging.getLogger("uvicorn.error").handlers[0].formatter
        assert type(formatter).__name__ != "SilloFormatter"

        # Put Sillo's back for anything that runs after this.
        SilloConfig(_app(), log_config=None)

    def test_a_numeric_log_level_is_accepted(self):
        # uvicorn takes a name or a number; the logging document needs a name.
        SilloConfig(_app(), log_config=None, log_level=logging.WARNING)

        assert logging.getLogger("uvicorn.error").level == logging.WARNING

        SilloConfig(_app(), log_config=None, log_level="info")

    def test_load_wraps_the_application_in_the_access_logger(self):
        config = SilloConfig(_app(), log_config=None)

        config.load()

        assert isinstance(config.loaded_app, AccessLog)
        # The unwrapped application is kept so the banner can count its routes.
        assert config.sillo_app is not None

    def test_the_access_logger_can_be_switched_off(self):
        config = SilloConfig(_app(), log_config=None, sillo_access_log=False)

        config.load()

        assert not isinstance(config.loaded_app, AccessLog)


class TestTheBannerReachesTheServer:
    def test_the_started_message_prints_the_banner(self, capsys):
        config = SilloConfig(_app(), log_config=None, port=8000)
        config.load()

        SilloServer(config)._log_started_message([_Listener()])

        printed = capsys.readouterr().err
        assert "sillo" in printed
        assert "http://127.0.0.1:8000" in printed
        assert "routes" in printed

    def test_port_zero_reports_the_port_the_os_chose(self, capsys):
        config = SilloConfig(_app(), log_config=None, port=0)
        config.load()

        SilloServer(config)._log_started_message([_Listener(port=54321)])

        assert "54321" in capsys.readouterr().err

    def test_the_banner_can_be_switched_off(self, capsys):
        config = SilloConfig(_app(), log_config=None, sillo_banner=False)
        config.load()

        SilloServer(config)._log_started_message([_Listener()])

        # uvicorn's own one-liner is used instead, so nothing Sillo-shaped.
        assert "press ctrl-c to stop" not in capsys.readouterr().err

    def test_stopping_prints_the_closing_card(self, capsys):
        config = SilloConfig(_app(), log_config=None)

        SilloServer(config)._log_stopped_message()

        assert "stopped" in capsys.readouterr().err

    def test_stopping_is_silent_when_the_banner_is_off(self, capsys):
        config = SilloConfig(_app(), log_config=None, sillo_banner=False)

        SilloServer(config)._log_stopped_message()

        assert "stopped" not in capsys.readouterr().err


class TestRunDispatch:
    """``run`` picks a supervisor; none of these actually serve."""

    @pytest.fixture
    def spy(self, monkeypatch):
        calls: dict = {}

        class FakeServer:
            def __init__(self, config):
                self.config = config
                calls["config"] = config

            def run(self, sockets=None):
                calls["ran"] = True

        monkeypatch.setattr(
            server_module, "_classes", lambda: (SilloConfig, FakeServer)
        )
        return calls

    def test_a_single_worker_runs_in_process(self, spy):
        server_module.run(_app(), port=0)

        assert spy["ran"] is True

    def test_reload_needs_an_import_string(self, spy):
        with pytest.raises(RuntimeError, match="import string"):
            server_module.run(_app(), reload=True)

    def test_workers_need_an_import_string(self, spy):
        with pytest.raises(RuntimeError, match="import string"):
            server_module.run(_app(), workers=3)

    def test_reload_goes_to_the_change_supervisor(self, spy, monkeypatch):
        # `ChangeReload` is an alias that resolves to whichever watcher is
        # available, so this compares against the class uvicorn exports rather
        # than against a name.
        from uvicorn.supervisors import ChangeReload

        seen: dict = {}

        def fake_supervise(supervisor_class, config, server):
            seen["class"] = supervisor_class

        monkeypatch.setattr(server_module, "_supervise", fake_supervise)
        server_module.run("tests.test_server.test_server_wiring:_app", reload=True, port=0)

        assert seen["class"] is ChangeReload

    def test_workers_go_to_the_multiprocess_supervisor(self, spy, monkeypatch):
        seen: dict = {}

        from uvicorn.supervisors import Multiprocess

        def fake_supervise(supervisor_class, config, server):
            seen["class"] = supervisor_class

        monkeypatch.setattr(server_module, "_supervise", fake_supervise)
        server_module.run(
            "tests.test_server.test_server_wiring:_app", workers=2, port=0
        )

        assert seen["class"] is Multiprocess


class TestSupervisorCompatibility:
    """uvicorn has changed this constructor between releases."""

    def test_the_modern_three_argument_form_is_used_when_accepted(self):
        seen: dict = {}

        class Supervisor:
            def __init__(self, config, target=None, sockets=None):
                seen["target"] = target

            def run(self):
                seen["ran"] = True

        config = SilloConfig(_app(), log_config=None, port=0)
        server_module._supervise(Supervisor, config, SilloServer(config))

        assert seen["target"] is not None
        assert seen["ran"] is True

    def test_it_falls_back_when_target_is_not_accepted(self):
        # Newer uvicorn builds the target themselves and take (config, sockets).
        seen: dict = {}

        class Supervisor:
            def __init__(self, config, sockets=None):
                seen["sockets"] = sockets

            def run(self):
                seen["ran"] = True

        config = SilloConfig(_app(), log_config=None, port=0)
        server_module._supervise(Supervisor, config, SilloServer(config))

        assert seen["sockets"] is not None
        assert seen["ran"] is True


class TestTheShutdownCard:
    def test_it_reports_a_request_count_when_there_is_one(self):
        assert "3 requests" in banner.render_shutdown(requests=3)

    def test_one_request_is_singular(self):
        assert "1 request" in banner.render_shutdown(requests=1)
        assert "1 requests" not in banner.render_shutdown(requests=1)

    def test_short_uptimes_are_seconds(self):
        assert "42s uptime" in banner.render_shutdown(uptime_s=42)

    def test_long_uptimes_are_hours(self):
        assert "h uptime" in banner.render_shutdown(uptime_s=7200)

    def test_it_still_says_stopped_with_nothing_to_report(self):
        assert "stopped" in banner.render_shutdown()


class TestBannerDetails:
    def test_the_worker_count_appears_when_there_is_more_than_one(self):
        text = banner.render(target="a:b", host="127.0.0.1", port=8000, workers=4)

        assert "4 workers" in text

    def test_reload_is_named_in_the_mode_line(self):
        text = banner.render(target="a:b", host="127.0.0.1", port=8000, reload=True)

        assert "reload" in text

    def test_writing_to_a_closed_stream_is_survivable(self, monkeypatch):
        import io

        closed = io.StringIO()
        closed.close()
        monkeypatch.setattr("sys.stderr", closed)

        # A banner is never worth taking the server down for.
        banner.write("anything")


class TestThemeEdges:
    def test_a_redirect_is_styled_apart_from_success(self):
        assert theme.status_style(302) != theme.status_style(200)

    def test_a_slow_request_is_flagged(self):
        assert theme.duration_style(2000) != theme.duration_style(10)
        assert theme.duration_style(250) != theme.duration_style(10)

    def test_unstyled_text_is_returned_unchanged(self):
        assert theme.paint("plain", None) == "plain"


class TestThePackageSurface:
    def test_the_access_logger_is_importable_from_the_package(self):
        import sillo.server as package

        assert package.AccessLog is AccessLog

    def test_an_unknown_attribute_raises(self):
        import sillo.server as package

        with pytest.raises(AttributeError, match="no attribute"):
            package.does_not_exist
