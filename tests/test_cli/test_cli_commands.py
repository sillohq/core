"""
The ``sillo`` CLI commands, driven through Click's ``CliRunner``.

``run`` spawns a server and ``shell`` blocks on an interactive console, so
both are exercised with the blocking call replaced — the assertions are about
the command line that would have been executed, not about actually running it.
"""

import importlib
import subprocess
import sys

import pytest
from click.testing import CliRunner

from sillo.cli.commands.new import new
from sillo.cli.commands.ping import ping
from sillo.cli.commands.run import run
from sillo.cli.commands.shell import shell
from sillo.cli.commands.urls import urls
from sillo.cli.main import cli

#: The module object — ``sillo.cli.commands.shell`` as an attribute lookup
#: resolves to the command, which the package re-exports under the same name.
shell_module = sys.modules["sillo.cli.commands.shell"]


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def app_module(tmp_path, monkeypatch):
    """A module on the import path exposing a small sillo app as ``app``."""
    (tmp_path / "cli_cmd_app.py").write_text(
        "from sillo import silloApp\n"
        "from sillo.core.http import Request, Response\n"
        "app = silloApp()\n"
        "@app.get('/health', name='health', summary='Liveness probe')\n"
        "async def health(request: Request, response: Response):\n"
        "    return response.json({'ok': True})\n"
        "@app.post('/items')\n"
        "async def create(request: Request, response: Response):\n"
        "    return response.json({}, status_code=201)\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.invalidate_caches()
    yield "cli_cmd_app:app"
    sys.modules.pop("cli_cmd_app", None)


@pytest.fixture
def recorded_run(monkeypatch):
    """Capture the command ``subprocess.run`` would have executed."""
    calls = []

    def fake_run(cmd, *args, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    return calls


# ── the root group ───────────────────────────────────────────────────────


def test_the_group_shows_help(runner):
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "sillo" in result.output


def test_every_command_is_registered(runner):
    output = runner.invoke(cli, ["--help"]).output
    for name in ("new", "run", "urls", "ping", "shell"):
        assert name in output


def test_the_version_flag(runner):
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0


def test_an_unknown_command_is_a_usage_error(runner):
    assert runner.invoke(cli, ["nonexistent"]).exit_code != 0


def test_short_help_is_available(runner):
    """The group sets ``help_option_names`` so ``-h`` works too."""
    assert runner.invoke(cli, ["-h"]).exit_code == 0


# ── run ──────────────────────────────────────────────────────────────────


def test_run_builds_a_uvicorn_command(runner, recorded_run):
    result = runner.invoke(run, ["--app", "main:app"])
    assert result.exit_code == 0
    assert recorded_run[0][:2] == ["uvicorn", "main:app"]


def test_run_passes_the_host_and_port(runner, recorded_run):
    runner.invoke(run, ["--app", "main:app", "--host", "0.0.0.0", "--port", "9000"])
    cmd = recorded_run[0]
    assert cmd[cmd.index("--host") + 1] == "0.0.0.0"
    assert cmd[cmd.index("--port") + 1] == "9000"


def test_run_adds_the_reload_flag(runner, recorded_run):
    runner.invoke(run, ["--app", "main:app", "--reload"])
    assert "--reload" in recorded_run[0]


def test_run_omits_reload_by_default(runner, recorded_run):
    runner.invoke(run, ["--app", "main:app"])
    assert "--reload" not in recorded_run[0]


def test_run_builds_a_granian_command(runner, recorded_run):
    runner.invoke(run, ["--app", "main:app", "--server", "granian"])
    assert recorded_run[0][0] == "granian"


def test_granian_receives_the_worker_count(runner, recorded_run):
    runner.invoke(run, ["--app", "main:app", "--server", "granian", "--workers", "4"])
    cmd = recorded_run[0]
    assert cmd[cmd.index("--workers") + 1] == "4"


def test_key_value_arguments_override_the_options(runner, recorded_run):
    """Trailing ``key=value`` pairs are merged over the parsed flags."""
    runner.invoke(run, ["--app", "main:app", "--port", "8000", "port=9999"])
    cmd = recorded_run[0]
    assert cmd[cmd.index("--port") + 1] == "9999"


def test_the_app_path_can_be_overridden_by_a_key_value(runner, recorded_run):
    runner.invoke(run, ["--app", "main:app", "app_path=other:application"])
    assert recorded_run[0][1] == "other:application"


def test_run_requires_an_app(runner):
    assert runner.invoke(run, []).exit_code != 0


def test_run_rejects_a_malformed_app_path(runner):
    result = runner.invoke(run, ["--app", "not-a-valid-path"])
    assert result.exit_code != 0


def test_run_rejects_an_out_of_range_port(runner):
    assert runner.invoke(run, ["--app", "main:app", "--port", "70000"]).exit_code != 0


def test_run_rejects_an_unknown_server(runner):
    assert (
        runner.invoke(run, ["--app", "main:app", "--server", "hypercorn"]).exit_code != 0
    )


def test_a_failing_server_exits_nonzero(runner, monkeypatch):
    def failing(cmd, *args, **kwargs):
        raise subprocess.CalledProcessError(2, cmd)

    monkeypatch.setattr(subprocess, "run", failing)
    result = runner.invoke(run, ["--app", "main:app"])
    assert result.exit_code == 1


def test_an_unexpected_failure_exits_nonzero(runner, monkeypatch):
    def exploding(cmd, *args, **kwargs):
        raise OSError("no such binary")

    monkeypatch.setattr(subprocess, "run", exploding)
    assert runner.invoke(run, ["--app", "main:app"]).exit_code == 1


def test_run_reports_the_address_it_is_starting_on(runner, recorded_run):
    result = runner.invoke(run, ["--app", "main:app", "--port", "8123"])
    assert "8123" in result.output


# ── urls ─────────────────────────────────────────────────────────────────


def test_urls_lists_the_registered_routes(runner, app_module):
    result = runner.invoke(urls, ["--app", app_module])
    assert result.exit_code == 0
    assert "/health" in result.output


def test_urls_prints_a_header_row(runner, app_module):
    output = runner.invoke(urls, ["--app", app_module]).output
    assert "METHODS" in output
    assert "PATH" in output


def test_urls_shows_the_route_name(runner, app_module):
    assert "health" in runner.invoke(urls, ["--app", app_module]).output


def test_urls_shows_the_summary(runner, app_module):
    assert "Liveness probe" in runner.invoke(urls, ["--app", app_module]).output


def test_urls_shows_the_methods(runner, app_module):
    assert "POST" in runner.invoke(urls, ["--app", app_module]).output.upper()


def test_urls_requires_an_app(runner):
    assert runner.invoke(urls, []).exit_code != 0


def test_urls_fails_cleanly_on_an_unimportable_app(runner):
    result = runner.invoke(urls, ["--app", "no_such_module_at_all:app"])
    assert result.exit_code == 1


# ── ping ─────────────────────────────────────────────────────────────────


def test_ping_reports_a_reachable_route(runner, app_module):
    result = runner.invoke(ping, ["/health", "--app", app_module])
    assert result.exit_code == 0
    assert "200" in result.output


def test_ping_reports_a_missing_route(runner, app_module):
    result = runner.invoke(ping, ["/nope", "--app", app_module])
    assert "404" in result.output


def test_ping_uses_the_requested_method(runner, app_module):
    result = runner.invoke(ping, ["/items", "--app", app_module, "--method", "post"])
    assert "201" in result.output


def test_a_non_200_status_is_reported_as_unexpected(runner, app_module):
    result = runner.invoke(ping, ["/items", "--app", app_module, "--method", "POST"])
    assert "Unexpected" in result.output


def test_ping_echoes_the_path_and_method(runner, app_module):
    output = runner.invoke(ping, ["/health", "--app", app_module]).output
    assert "/health" in output
    assert "GET" in output


def test_ping_requires_an_app(runner):
    assert runner.invoke(ping, ["/health"]).exit_code != 0


def test_ping_fails_cleanly_on_an_unimportable_app(runner):
    result = runner.invoke(ping, ["/health", "--app", "no_such_module_at_all:app"])
    assert result.exit_code == 1


# ── shell ────────────────────────────────────────────────────────────────


@pytest.fixture
def fake_console(monkeypatch):
    """Replace the blocking interactive console with a recorder."""
    import code

    captured = {}

    class Recorder:
        def __init__(self, namespace):
            captured["namespace"] = namespace

        def interact(self, banner=None):
            captured["banner"] = banner

    monkeypatch.setattr(code, "InteractiveConsole", Recorder)
    return captured


def test_the_shell_starts_and_exposes_the_app(runner, app_module, fake_console):
    result = runner.invoke(shell, ["--app", app_module])
    assert result.exit_code == 0
    assert "app" in fake_console["namespace"]


def test_the_shell_exposes_the_application_class(runner, app_module, fake_console):
    runner.invoke(shell, ["--app", app_module])
    assert fake_console["namespace"]["silloApp"].__name__ == "silloApp"


def test_the_shell_exposes_request_and_response(runner, app_module, fake_console):
    runner.invoke(shell, ["--app", app_module])
    namespace = fake_console["namespace"]
    assert "Request" in namespace
    assert "Response" in namespace


def test_the_shell_prints_a_banner(runner, app_module, fake_console):
    runner.invoke(shell, ["--app", app_module])
    assert "sillo Interactive Shell" in fake_console["banner"]


def test_the_shell_reports_the_loaded_app(runner, app_module, fake_console):
    assert "Loaded app" in runner.invoke(shell, ["--app", app_module]).output


def test_the_shell_requires_an_app(runner):
    assert runner.invoke(shell, []).exit_code != 0


def test_the_shell_fails_cleanly_on_an_unimportable_app(runner, fake_console):
    result = runner.invoke(shell, ["--app", "no_such_module_at_all:app"])
    assert result.exit_code == 1


def test_the_ipython_flag_falls_back_when_ipython_is_absent(
    runner, app_module, fake_console, monkeypatch
):
    """Asking for IPython on a machine without it must still give a shell."""
    monkeypatch.setattr(shell_module, "InteractiveShellEmbed", None)
    result = runner.invoke(shell, ["--app", app_module, "--ipython"])
    assert result.exit_code == 0
    assert "Falling back" in result.output
    assert "app" in fake_console["namespace"]


def test_the_ipython_flag_uses_ipython_when_present(runner, app_module, monkeypatch):
    started = {}

    class FakeEmbed:
        def __init__(self, banner1=None):
            started["banner"] = banner1

        def __call__(self, local_ns=None):
            started["namespace"] = local_ns

    monkeypatch.setattr(shell_module, "InteractiveShellEmbed", FakeEmbed)
    result = runner.invoke(shell, ["--app", app_module, "--ipython"])
    assert result.exit_code == 0
    assert "app" in started["namespace"]


def test_a_console_that_cannot_start_falls_through_to_ipython(
    runner, app_module, monkeypatch
):
    import code

    class Broken:
        def __init__(self, namespace):
            raise RuntimeError("no tty")

    started = {}

    class FakeEmbed:
        def __init__(self, banner1=None):
            pass

        def __call__(self, local_ns=None):
            started["namespace"] = local_ns

    monkeypatch.setattr(code, "InteractiveConsole", Broken)
    monkeypatch.setattr(shell_module, "InteractiveShellEmbed", FakeEmbed)

    result = runner.invoke(shell, ["--app", app_module])
    assert result.exit_code == 0
    assert "app" in started["namespace"]


# ── new ──────────────────────────────────────────────────────────────────


def test_new_rejects_an_invalid_project_name(runner):
    assert runner.invoke(new, ["2fast"]).exit_code != 0


def test_new_rejects_an_invalid_title(runner, tmp_path):
    result = runner.invoke(
        new, ["myapp", "--output-dir", str(tmp_path), "--title", "Bad!Title"]
    )
    assert result.exit_code != 0


def test_new_rejects_an_unknown_template(runner, tmp_path):
    result = runner.invoke(
        new, ["myapp", "--output-dir", str(tmp_path), "--template", "nonexistent"]
    )
    assert result.exit_code != 0


def test_new_refuses_to_overwrite_an_existing_directory(runner, tmp_path):
    (tmp_path / "myapp").mkdir()
    result = runner.invoke(new, ["myapp", "--output-dir", str(tmp_path)])
    assert "already exists" in result.output


def test_new_reports_a_directory_it_cannot_write_to(runner, tmp_path):
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o500)
    try:
        result = runner.invoke(new, ["myapp", "--output-dir", str(locked)])
        assert "permission" in result.output.lower()
    finally:
        locked.chmod(0o700)


def test_new_requires_a_project_name(runner):
    assert runner.invoke(new, []).exit_code != 0


def test_new_accepts_a_valid_name_and_template(runner, tmp_path):
    """Whether the bundled templates are present or not, a valid invocation
    must not crash — it either scaffolds or reports the missing template."""
    result = runner.invoke(
        new, ["myapp", "--output-dir", str(tmp_path), "--template", "basic"]
    )
    assert result.exit_code == 0


def test_new_creates_the_project_directory(runner, tmp_path):
    runner.invoke(new, ["myapp", "--output-dir", str(tmp_path)])
    assert (tmp_path / "myapp").is_dir()


class TestScaffolding:
    """The copy-and-substitute path, against a template tree created here.

    The bundled ``sillo/templates`` directory is not present in a source
    checkout, so it is stood up for the duration of the test and removed
    afterwards — and left alone entirely if it already exists.
    """

    @pytest.fixture
    def template_tree(self):
        import shutil
        from pathlib import Path

        import sillo

        root = Path(sillo.__file__).parent / "templates"
        if root.exists():
            pytest.skip("real bundled templates present; not overwriting them")

        basic = root / "basic"
        basic.mkdir(parents=True)
        (basic / "main.py").write_text(
            "# {{project_name_title}}\n"
            "APP_NAME = '{{project_name}}'\n"
            "SILLO_VERSION = '{{version}}'\n"
        )
        (basic / "requirements.txt").write_text("sillo\n")
        (basic / "app").mkdir()
        (basic / "app" / "routes.py").write_text("# routes for {{project_name}}\n")
        try:
            yield root
        finally:
            shutil.rmtree(root)

    def test_the_template_files_are_copied(self, runner, tmp_path, template_tree):
        runner.invoke(new, ["myapp", "--output-dir", str(tmp_path)])
        assert (tmp_path / "myapp" / "main.py").exists()
        assert (tmp_path / "myapp" / "requirements.txt").exists()

    def test_nested_template_directories_are_recreated(
        self, runner, tmp_path, template_tree
    ):
        runner.invoke(new, ["myapp", "--output-dir", str(tmp_path)])
        assert (tmp_path / "myapp" / "app" / "routes.py").exists()

    def test_the_project_name_is_substituted(self, runner, tmp_path, template_tree):
        runner.invoke(new, ["myapp", "--output-dir", str(tmp_path)])
        content = (tmp_path / "myapp" / "main.py").read_text()
        assert "APP_NAME = 'myapp'" in content
        assert "{{project_name}}" not in content

    def test_the_title_defaults_to_the_project_name(
        self, runner, tmp_path, template_tree
    ):
        runner.invoke(new, ["my_cool_app", "--output-dir", str(tmp_path)])
        assert "# My Cool App" in (tmp_path / "my_cool_app" / "main.py").read_text()

    def test_an_explicit_title_is_used(self, runner, tmp_path, template_tree):
        runner.invoke(
            new, ["myapp", "--output-dir", str(tmp_path), "--title", "My Portal"]
        )
        assert "# My Portal" in (tmp_path / "myapp" / "main.py").read_text()

    def test_the_version_is_substituted(self, runner, tmp_path, template_tree):
        from sillo.__main__ import __version__

        runner.invoke(new, ["myapp", "--output-dir", str(tmp_path)])
        content = (tmp_path / "myapp" / "main.py").read_text()
        assert f"SILLO_VERSION = '{__version__}'" in content

    def test_an_env_file_is_written(self, runner, tmp_path, template_tree):
        runner.invoke(new, ["myapp", "--output-dir", str(tmp_path)])
        env = (tmp_path / "myapp" / ".env").read_text()
        assert "DEBUG=True" in env
        assert "PORT=4000" in env

    def test_success_is_reported_with_next_steps(
        self, runner, tmp_path, template_tree
    ):
        output = runner.invoke(new, ["myapp", "--output-dir", str(tmp_path)]).output
        assert "created successfully" in output
        assert "cd myapp" in output

    def test_a_binary_template_file_is_reported_but_not_fatal(
        self, runner, tmp_path, template_tree
    ):
        """Templates are read as UTF-8 text; a stray binary asset must warn
        rather than abort the scaffold."""
        (template_tree / "basic" / "logo.bin").write_bytes(b"\xff\xfe\x00binary")
        result = runner.invoke(new, ["myapp", "--output-dir", str(tmp_path)])
        assert (tmp_path / "myapp" / "main.py").exists()
        assert result.exit_code == 0
