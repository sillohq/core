"""Finding .env files, loading them, and reading single variables."""

import os
import re
from pathlib import Path

import pytest

from sillo.env import ENV_FILE_VARIABLE, autoload, env, find_env, load_env


class TestFindEnv:
    """Where the file is looked for."""

    def test_finds_it_in_the_working_directory(self, project):
        (project / ".env").write_text("KEY=value\n")
        assert find_env() == project / ".env"

    def test_finds_it_in_a_parent(self, project, monkeypatch):
        (project / ".env").write_text("KEY=value\n")
        nested = project / "app" / "handlers"
        nested.mkdir(parents=True)
        monkeypatch.chdir(nested)

        assert find_env() == project / ".env"

    def test_stops_at_the_project_root(self, tmp_path, monkeypatch):
        # A .env above the project must not be picked up: that is somebody's
        # home directory, and its variables are not this project's.
        (tmp_path / ".env").write_text("OUTSIDE=1\n")
        inner = tmp_path / "project"
        inner.mkdir()
        (inner / "pyproject.toml").write_text("[project]\n")
        monkeypatch.chdir(inner)

        assert find_env() is None

    def test_returns_none_when_there_is_none(self, project):
        assert find_env() is None

    def test_walks_to_the_top_when_no_marker_is_found(self, tmp_path, monkeypatch):
        nested = tmp_path / "a" / "b"
        nested.mkdir(parents=True)
        monkeypatch.chdir(nested)

        assert find_env(".env.nothing-is-named-this") is None

    def test_a_directory_named_env_is_not_a_file(self, project):
        (project / ".env").mkdir()
        assert find_env() is None

    def test_looks_for_the_name_it_is_given(self, project):
        (project / ".env.production").write_text("KEY=value\n")
        assert find_env(".env.production") == project / ".env.production"

    def test_starts_where_it_is_told(self, project, tmp_path):
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        (elsewhere / "pyproject.toml").write_text("[project]\n")
        (elsewhere / ".env").write_text("KEY=value\n")

        assert find_env(start=elsewhere) == elsewhere / ".env"


class TestLoadEnv:
    """What reaches the environment."""

    def test_loads_a_file_by_path(self, tmp_path):
        path = tmp_path / ".env"
        path.write_text("SILLO_TEST_A=1\nSILLO_TEST_B=two\n")

        applied = load_env(path)

        assert applied == {"SILLO_TEST_A": "1", "SILLO_TEST_B": "two"}
        assert os.environ["SILLO_TEST_A"] == "1"
        assert os.environ["SILLO_TEST_B"] == "two"

    def test_accepts_a_string_path(self, tmp_path):
        path = tmp_path / ".env"
        path.write_text("SILLO_TEST_A=1\n")

        load_env(str(path))

        assert os.environ["SILLO_TEST_A"] == "1"

    def test_the_real_environment_wins(self, tmp_path):
        os.environ["SILLO_TEST_A"] = "from-the-platform"
        path = tmp_path / ".env"
        path.write_text("SILLO_TEST_A=from-the-file\n")

        applied = load_env(path)

        assert os.environ["SILLO_TEST_A"] == "from-the-platform"
        assert applied == {}

    def test_override_reverses_that(self, tmp_path):
        os.environ["SILLO_TEST_A"] = "from-the-platform"
        path = tmp_path / ".env"
        path.write_text("SILLO_TEST_A=from-the-file\n")

        applied = load_env(path, override=True)

        assert os.environ["SILLO_TEST_A"] == "from-the-file"
        assert applied == {"SILLO_TEST_A": "from-the-file"}

    def test_a_missing_file_is_not_an_error(self, tmp_path):
        assert load_env(tmp_path / "nothing-here") == {}

    def test_a_directory_is_not_an_error(self, tmp_path):
        assert load_env(tmp_path) == {}

    def test_undecodable_bytes_are_not_an_error(self, tmp_path):
        path = tmp_path / ".env"
        path.write_bytes(b"KEY=\xff\xfe\n")

        assert load_env(path) == {}

    def test_writes_to_the_mapping_it_is_given(self, tmp_path):
        path = tmp_path / ".env"
        path.write_text("SILLO_TEST_A=1\n")
        target = {}

        load_env(path, environ=target)

        assert target == {"SILLO_TEST_A": "1"}
        assert "SILLO_TEST_A" not in os.environ

    def test_finds_the_file_when_given_no_path(self, project):
        (project / ".env").write_text("SILLO_TEST_A=found\n")

        assert load_env() == {"SILLO_TEST_A": "found"}

    def test_no_search_looks_only_in_the_working_directory(self, project, monkeypatch):
        (project / ".env").write_text("SILLO_TEST_A=found\n")
        nested = project / "app"
        nested.mkdir()
        monkeypatch.chdir(nested)

        assert load_env(search=False) == {}
        assert load_env(search=True) == {"SILLO_TEST_A": "found"}

    def test_layering_a_local_file_on_top(self, project):
        (project / ".env").write_text("SILLO_TEST_A=shared\nSILLO_TEST_B=shared\n")
        (project / ".env.local").write_text("SILLO_TEST_A=mine\n")

        load_env()
        load_env(project / ".env.local", override=True)

        assert os.environ["SILLO_TEST_A"] == "mine"
        assert os.environ["SILLO_TEST_B"] == "shared"

    def test_references_resolve_against_the_live_environment(self, tmp_path):
        os.environ["SILLO_TEST_HOST"] = "db.internal"
        path = tmp_path / ".env"
        path.write_text("SILLO_TEST_URL=postgres://$SILLO_TEST_HOST/app\n")

        load_env(path)

        assert os.environ["SILLO_TEST_URL"] == "postgres://db.internal/app"


class TestAutoload:
    """The automatic load the framework performs."""

    def test_loads_the_projects_env(self, project):
        (project / ".env").write_text("SILLO_TEST_A=1\n")

        assert autoload() == (project / ".env").resolve()
        assert os.environ["SILLO_TEST_A"] == "1"

    def test_reads_the_file_once(self, project):
        path = project / ".env"
        path.write_text("SILLO_TEST_A=first\n")
        autoload()

        # A second call must not re-read: something may have changed the
        # variable deliberately since startup.
        path.write_text("SILLO_TEST_A=second\n")
        del os.environ["SILLO_TEST_A"]
        autoload()

        assert "SILLO_TEST_A" not in os.environ

    def test_does_nothing_without_a_file(self, project):
        assert autoload() is None

    def test_env_file_variable_points_it_elsewhere(self, project):
        (project / ".env").write_text("SILLO_TEST_A=default\n")
        (project / ".env.production").write_text("SILLO_TEST_A=production\n")
        os.environ[ENV_FILE_VARIABLE] = str(project / ".env.production")

        autoload()

        assert os.environ["SILLO_TEST_A"] == "production"

    def test_empty_env_file_variable_turns_it_off(self, project):
        (project / ".env").write_text("SILLO_TEST_A=1\n")
        os.environ[ENV_FILE_VARIABLE] = ""

        assert autoload() is None
        assert "SILLO_TEST_A" not in os.environ

    def test_a_configured_file_that_is_missing_is_not_an_error(self, project):
        os.environ[ENV_FILE_VARIABLE] = str(project / "nothing-here")

        assert autoload() is None


class TestEnvAccessor:
    """``env()`` for the one-off read."""

    def test_reads_a_string(self):
        os.environ["SILLO_TEST_A"] = "value"
        assert env("SILLO_TEST_A") == "value"

    def test_returns_the_default_when_unset(self):
        assert env("SILLO_TEST_MISSING", "fallback") == "fallback"

    def test_a_variable_with_no_default_is_required(self):
        with pytest.raises(KeyError, match="SILLO_TEST_MISSING"):
            env("SILLO_TEST_MISSING")

    def test_casts_to_int(self):
        os.environ["SILLO_TEST_PORT"] = "8000"
        assert env("SILLO_TEST_PORT", cast=int) == 8000

    def test_casts_to_float(self):
        os.environ["SILLO_TEST_TIMEOUT"] = "1.5"
        assert env("SILLO_TEST_TIMEOUT", cast=float) == 1.5

    def test_casts_with_any_callable(self):
        os.environ["SILLO_TEST_HOSTS"] = "a.test,b.test"
        assert env("SILLO_TEST_HOSTS", cast=lambda raw: raw.split(",")) == [
            "a.test",
            "b.test",
        ]

    @pytest.mark.parametrize("raw", ["1", "true", "TRUE", "yes", "on", "y"])
    def test_true_words(self, raw):
        os.environ["SILLO_TEST_DEBUG"] = raw
        assert env("SILLO_TEST_DEBUG", cast=bool) is True

    @pytest.mark.parametrize("raw", ["0", "false", "FALSE", "no", "off", "n", ""])
    def test_false_words(self, raw):
        # Not Python's truthiness: "false" is a non-empty string, and every
        # config that gets this wrong ships debug mode to production.
        os.environ["SILLO_TEST_DEBUG"] = raw
        assert env("SILLO_TEST_DEBUG", cast=bool) is False

    def test_a_value_that_is_not_a_boolean(self):
        os.environ["SILLO_TEST_DEBUG"] = "maybe"
        with pytest.raises(ValueError):
            env("SILLO_TEST_DEBUG", cast=bool)

    def test_a_value_that_is_not_an_int(self):
        os.environ["SILLO_TEST_PORT"] = "eighty"
        with pytest.raises(ValueError, match="SILLO_TEST_PORT"):
            env("SILLO_TEST_PORT", cast=int)

    def test_the_default_is_returned_uncast(self):
        assert env("SILLO_TEST_MISSING", None, cast=int) is None


class TestNoDotenv:
    """The dependency this module exists to avoid."""

    def test_the_framework_does_not_import_python_dotenv(self):
        source = Path(__file__).resolve().parents[2] / "sillo"
        importing = re.compile(r"^\s*(?:from dotenv\b|import dotenv\b)", re.MULTILINE)
        offenders = [
            str(path.relative_to(source))
            for path in source.rglob("*.py")
            if importing.search(path.read_text(encoding="utf-8", errors="ignore"))
        ]
        assert offenders == []

    def test_python_dotenv_is_not_a_declared_dependency(self):
        pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
        text = pyproject.read_text(encoding="utf-8")
        assert "python-dotenv" not in text


class TestFrameworkLoadsItself:
    """The framework reads .env on its own, which is the whole point."""

    def test_building_an_application_loads_the_projects_env(self, project):
        from sillo import SilloApp

        (project / ".env").write_text("SILLO_TEST_APP_KEY=loaded\n")

        SilloApp(title="demo")

        assert os.environ["SILLO_TEST_APP_KEY"] == "loaded"

    def test_an_application_does_not_override_the_platform(self, project):
        from sillo import SilloApp

        os.environ["SILLO_TEST_APP_KEY"] = "from-the-platform"
        (project / ".env").write_text("SILLO_TEST_APP_KEY=from-the-file\n")

        SilloApp(title="demo")

        assert os.environ["SILLO_TEST_APP_KEY"] == "from-the-platform"

    def test_the_console_loads_it_before_finding_the_application(self, project):
        from sillo.__main__ import build_console

        (project / ".env").write_text("SILLO_TEST_CONSOLE_KEY=loaded\n")

        build_console()

        assert os.environ["SILLO_TEST_CONSOLE_KEY"] == "loaded"
