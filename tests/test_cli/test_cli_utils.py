"""
CLI helper functions: echo styling, Click validators, app loading, and
key=value argument parsing.

The validators are Click callbacks, so they are called here the way Click
calls them — ``(ctx, param, value)`` — and are expected to raise
``BadParameter`` rather than return an error.
"""

import importlib
import os
import socket
import subprocess
import sys

import click
import pytest

from sillo.cli.utils import (
    _check_server_installed,
    _echo_error,
    _echo_info,
    _echo_success,
    _echo_warning,
    _has_write_permission,
    _is_port_in_use,
    _load_app_from_path,
    _load_app_from_string,
    _parse_cli_args_kwargs,
    _validate_app_path,
    _validate_host,
    _validate_port,
    _validate_project_name,
    _validate_project_title,
    _validate_server,
)


# ── echo helpers ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "fn,marker",
    [(_echo_success, "✓"), (_echo_info, "ℹ"), (_echo_warning, "⚠")],
)
def test_echo_helpers_write_to_stdout(fn, marker, capsys):
    fn("the message")
    out = capsys.readouterr().out
    assert marker in out
    assert "the message" in out


def test_errors_go_to_stderr(capsys):
    """Errors must not pollute stdout, which callers may be piping."""
    _echo_error("it broke")
    captured = capsys.readouterr()
    assert "it broke" in captured.err
    assert captured.out == ""


def test_the_error_marker_is_present(capsys):
    _echo_error("it broke")
    assert "✗" in capsys.readouterr().err


# ── filesystem and network probes ────────────────────────────────────────


def test_an_existing_writable_directory(tmp_path):
    assert _has_write_permission(tmp_path) is True


def test_a_missing_path_checks_its_parent(tmp_path):
    assert _has_write_permission(tmp_path / "not-created-yet") is True


def test_a_read_only_directory_is_rejected(tmp_path):
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o500)
    try:
        assert _has_write_permission(locked) is False
    finally:
        locked.chmod(0o700)


@pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses permission bits")
def test_a_path_under_a_read_only_parent_is_rejected(tmp_path):
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o500)
    try:
        assert _has_write_permission(locked / "new-file") is False
    finally:
        locked.chmod(0o700)


def test_a_free_port_reads_as_unused():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    assert _is_port_in_use("127.0.0.1", port) is False


def test_a_bound_port_reads_as_in_use():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        assert _is_port_in_use("127.0.0.1", port) is True


def test_an_installed_server_is_detected(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: None)
    assert _check_server_installed("uvicorn") is True


def test_a_missing_server_is_reported_rather_than_raised(monkeypatch):
    def missing(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "run", missing)
    assert _check_server_installed("granian") is False


def test_a_server_that_exits_nonzero_is_not_installed(monkeypatch):
    def failing(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "uvicorn")

    monkeypatch.setattr(subprocess, "run", failing)
    assert _check_server_installed("uvicorn") is False


# ── project name and title validators ────────────────────────────────────


@pytest.mark.parametrize("name", ["myapp", "my_app", "App2", "a"])
def test_valid_project_names(name):
    assert _validate_project_name(None, None, name) == name


@pytest.mark.parametrize("name", ["2fast", "_private", "my-app", "my app", "my.app"])
def test_invalid_project_names_are_rejected(name):
    """The name becomes both a directory and an importable module, so it has
    to satisfy Python identifier rules."""
    with pytest.raises(click.BadParameter):
        _validate_project_name(None, None, name)


def test_an_empty_project_name_is_passed_through():
    """Click's own required-field handling reports the missing value."""
    assert _validate_project_name(None, None, "") == ""


def test_a_none_project_name_is_passed_through():
    assert _validate_project_name(None, None, None) is None


@pytest.mark.parametrize("title", ["My App", "My-App_2", "Title"])
def test_valid_project_titles(title):
    assert _validate_project_title(None, None, title) == title


@pytest.mark.parametrize("title", ["My App!", "Title;rm -rf /", "a@b"])
def test_invalid_project_titles_are_rejected(title):
    with pytest.raises(click.BadParameter):
        _validate_project_title(None, None, title)


def test_an_empty_project_title_is_passed_through():
    assert _validate_project_title(None, None, "") == ""


# ── host and port validators ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "host", ["localhost", "127.0.0.1", "0.0.0.0", "example.com", "my-host"]
)
def test_valid_hosts(host):
    assert _validate_host(None, None, host) == host


@pytest.mark.parametrize("host", ["-bad", "host name", "bad_host!"])
def test_invalid_hosts_are_rejected(host):
    with pytest.raises(click.BadParameter):
        _validate_host(None, None, host)


@pytest.mark.parametrize("port", [1, 80, 8000, 65535])
def test_valid_ports(port):
    assert _validate_port(None, None, port) == port


@pytest.mark.parametrize("port", [0, -1, 65536, 99999])
def test_out_of_range_ports_are_rejected(port):
    with pytest.raises(click.BadParameter):
        _validate_port(None, None, port)


def test_the_port_error_names_the_offending_value():
    with pytest.raises(click.BadParameter, match="70000"):
        _validate_port(None, None, 70000)


# ── app path and server validators ───────────────────────────────────────


@pytest.mark.parametrize(
    "path", ["main:app", "myapp.main:app", "a.b.c:application", "mod_1:app_2"]
)
def test_valid_app_paths(path):
    assert _validate_app_path(None, None, path) == path


@pytest.mark.parametrize(
    "path", ["main", "main:", ":app", "main:app:extra", "my-app:app", "main app:app"]
)
def test_invalid_app_paths_are_rejected(path):
    with pytest.raises(click.BadParameter):
        _validate_app_path(None, None, path)


def test_an_empty_app_path_is_passed_through():
    assert _validate_app_path(None, None, "") == ""


@pytest.mark.parametrize("server", ["uvicorn", "granian"])
def test_supported_servers(server):
    assert _validate_server(None, None, server) == server


@pytest.mark.parametrize("server", ["gunicorn", "hypercorn", "Uvicorn"])
def test_unsupported_servers_are_rejected(server):
    with pytest.raises(click.BadParameter):
        _validate_server(None, None, server)


def test_an_empty_server_is_passed_through():
    """Click's default fills the value in when the flag is omitted."""
    assert _validate_server(None, None, "") == ""


# ── loading an app from a module path ────────────────────────────────────


@pytest.fixture
def app_module(tmp_path, monkeypatch):
    """A throwaway package on the path exposing ``app`` and ``not_an_app``."""
    module = tmp_path / "cli_probe_app.py"
    module.write_text(
        "from sillo import silloApp\n"
        "app = silloApp()\n"
        "alias = app\n"
        "not_an_app = None\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.invalidate_caches()
    yield "cli_probe_app"
    sys.modules.pop("cli_probe_app", None)


def test_loading_an_app(app_module):
    from sillo import silloApp

    assert isinstance(_load_app_from_string(f"{app_module}:app"), silloApp)


def test_loading_an_app_under_another_name(app_module):
    assert _load_app_from_string(f"{app_module}:alias") is _load_app_from_string(
        f"{app_module}:app"
    )


def test_a_path_without_a_colon_is_rejected():
    with pytest.raises(RuntimeError, match="module:app"):
        _load_app_from_string("just_a_module")


def test_a_missing_module_raises_import_error():
    with pytest.raises(ImportError, match="no_such_module_anywhere"):
        _load_app_from_string("no_such_module_anywhere:app")


def test_a_missing_attribute_is_reported(app_module):
    with pytest.raises(RuntimeError, match="missing_name"):
        _load_app_from_string(f"{app_module}:missing_name")


def test_an_attribute_that_is_none_is_treated_as_missing(app_module):
    """``getattr(..., None)`` cannot tell absent from ``None``, so a variable
    explicitly set to ``None`` reports the same error."""
    with pytest.raises(RuntimeError):
        _load_app_from_string(f"{app_module}:not_an_app")


def test_the_working_directory_is_importable(tmp_path, monkeypatch):
    """Project modules are usually not installed, so the loader adds the cwd."""
    (tmp_path / "cwd_probe_app.py").write_text(
        "from sillo import silloApp\napp = silloApp()\n"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", [p for p in sys.path if p != str(tmp_path)])
    importlib.invalidate_caches()
    try:
        assert _load_app_from_string("cwd_probe_app:app") is not None
    finally:
        sys.modules.pop("cwd_probe_app", None)


def test_load_app_from_path_delegates(app_module):
    assert _load_app_from_path(f"{app_module}:app") is not None


def test_load_app_from_path_requires_a_value():
    with pytest.raises(RuntimeError, match="--app"):
        _load_app_from_path("")


def test_load_app_from_path_rejects_none():
    with pytest.raises(RuntimeError):
        _load_app_from_path(None)


# ── key=value argument parsing ───────────────────────────────────────────


def test_no_arguments():
    assert _parse_cli_args_kwargs(()) == ([], {})


def test_positional_arguments_keep_their_order():
    assert _parse_cli_args_kwargs(("one", "two")) == (["one", "two"], {})


def test_a_string_keyword():
    assert _parse_cli_args_kwargs(("name=ada",))[1] == {"name": "ada"}


def test_positional_and_keyword_arguments_together():
    positional, keyword = _parse_cli_args_kwargs(("pos", "key=value", "other"))
    assert positional == ["pos", "other"]
    assert keyword == {"key": "value"}


@pytest.mark.parametrize("literal", ["true", "True", "TRUE"])
def test_true_is_coerced_to_a_bool(literal):
    assert _parse_cli_args_kwargs((f"reload={literal}",))[1] == {"reload": True}


@pytest.mark.parametrize("literal", ["false", "False", "FALSE"])
def test_false_is_coerced_to_a_bool(literal):
    assert _parse_cli_args_kwargs((f"reload={literal}",))[1] == {"reload": False}


def test_digits_are_coerced_to_int():
    parsed = _parse_cli_args_kwargs(("port=8080",))[1]
    assert parsed == {"port": 8080}
    assert isinstance(parsed["port"], int)


def test_a_decimal_is_coerced_to_float():
    parsed = _parse_cli_args_kwargs(("timeout=1.5",))[1]
    assert parsed == {"timeout": 1.5}
    assert isinstance(parsed["timeout"], float)


def test_a_non_numeric_value_stays_a_string():
    assert _parse_cli_args_kwargs(("host=localhost",))[1] == {"host": "localhost"}


def test_a_value_may_contain_an_equals_sign():
    assert _parse_cli_args_kwargs(("query=a=b",))[1] == {"query": "a=b"}


def test_an_empty_value_stays_an_empty_string():
    assert _parse_cli_args_kwargs(("name=",))[1] == {"name": ""}


def test_a_negative_number_is_parsed_as_a_float():
    """``isdigit`` is False for a leading minus, so the float branch takes it."""
    assert _parse_cli_args_kwargs(("offset=-5",))[1] == {"offset": -5.0}


def test_a_later_duplicate_key_wins():
    assert _parse_cli_args_kwargs(("port=1", "port=2"))[1] == {"port": 2}
