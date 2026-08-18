"""Config reads the project's .env without being asked to.

The behaviour these cover is the point of the whole module: a project writes
a ``.env``, declares a config class, and installs nothing extra.
"""

import os

import pytest

from sillo.config import Config, Field
from sillo.env import _loader
from sillo.env._loader import ENV_FILE_VARIABLE


@pytest.fixture(autouse=True)
def clean_env():
    """Undo environment writes and autoload's memory between tests."""
    original = dict(os.environ)
    _loader._reset_autoload()

    yield

    os.environ.clear()
    os.environ.update(original)
    _loader._reset_autoload()


@pytest.fixture
def project(tmp_path, monkeypatch):
    """A project directory that is the working directory."""
    (tmp_path / "pyproject.toml").write_text("[project]\n")
    monkeypatch.chdir(tmp_path)
    names = (
        "DATABASE_URL",
        "DB_URL",
        "DB_HOST",
        "DATABASE_POOL_SIZE",
        "MAIL_HOST",
        "URL",
        "JWT_SECRET",
        "DEBUG",
        "PORT",
        ENV_FILE_VARIABLE,
    )
    for key in names:
        monkeypatch.delenv(key, raising=False)
        monkeypatch.delenv(key.lower(), raising=False)
    return tmp_path


class Settings(Config):
    """Declared at module level, the way an application declares one."""

    database_url: str
    debug: bool = False
    port: int = 8000


class TestAutomaticLoading:
    """No inner class, no arguments, no dotenv."""

    def test_the_projects_env_file_is_loaded(self, project):
        (project / ".env").write_text(
            "DATABASE_URL=postgres://localhost/app\nDEBUG=true\nPORT=9000\n"
        )

        config = Settings()

        assert config.database_url == "postgres://localhost/app"
        assert config.debug is True
        assert config.port == 9000

    def test_types_come_from_the_annotations(self, project):
        (project / ".env").write_text("DATABASE_URL=x\nPORT=9000\n")

        config = Settings()

        assert isinstance(config.port, int)
        assert isinstance(config.debug, bool)

    def test_found_from_a_subdirectory(self, project, monkeypatch):
        (project / ".env").write_text("DATABASE_URL=postgres://localhost/app\n")
        nested = project / "app" / "handlers"
        nested.mkdir(parents=True)
        monkeypatch.chdir(nested)

        assert Settings().database_url == "postgres://localhost/app"

    def test_defaults_apply_when_the_file_is_silent(self, project):
        (project / ".env").write_text("DATABASE_URL=postgres://localhost/app\n")

        config = Settings()

        assert config.debug is False
        assert config.port == 8000

    def test_a_missing_file_is_not_an_error(self, project):
        os.environ["DATABASE_URL"] = "postgres://localhost/app"

        assert Settings().database_url == "postgres://localhost/app"

    def test_a_missing_required_value_fails_at_construction(self, project):
        with pytest.raises(Exception) as error:
            Settings()

        assert "database_url" in str(error.value)

    def test_the_real_environment_wins_over_the_file(self, project):
        (project / ".env").write_text("DATABASE_URL=from-the-file\n")
        os.environ["DATABASE_URL"] = "from-the-platform"

        assert Settings().database_url == "from-the-platform"

    def test_arguments_win_over_both(self, project):
        (project / ".env").write_text("DATABASE_URL=from-the-file\n")
        os.environ["DATABASE_URL"] = "from-the-platform"

        assert Settings(database_url="explicit").database_url == "explicit"

    def test_references_inside_the_file_resolve(self, project):
        (project / ".env").write_text(
            "DB_HOST=db.internal\nDATABASE_URL=postgres://${DB_HOST}/app\n"
        )

        assert Settings().database_url == "postgres://db.internal/app"

    def test_the_file_is_read_once_for_many_configs(self, project):
        path = project / ".env"
        path.write_text("DATABASE_URL=first\n")
        Settings()

        path.write_text("DATABASE_URL=second\n")
        del os.environ["DATABASE_URL"]

        with pytest.raises(Exception):
            Settings()


class TestOptOut:
    """Turning the automatic load off."""

    def test_env_file_none_loads_no_file(self, project):
        (project / ".env").write_text("DATABASE_URL=from-the-file\n")
        os.environ["DATABASE_URL"] = "from-the-environment"

        class Isolated(Config):
            database_url: str

            class Env:
                env_file = None

        assert Isolated().database_url == "from-the-environment"
        assert "DEBUG" not in os.environ

    def test_empty_env_file_variable_turns_it_off(self, project):
        (project / ".env").write_text("DATABASE_URL=from-the-file\n")
        os.environ[ENV_FILE_VARIABLE] = ""
        os.environ["DATABASE_URL"] = "from-the-environment"

        assert Settings().database_url == "from-the-environment"

    def test_env_file_variable_selects_another_file(self, project):
        (project / ".env").write_text("DATABASE_URL=development\n")
        (project / ".env.production").write_text("DATABASE_URL=production\n")
        os.environ[ENV_FILE_VARIABLE] = str(project / ".env.production")

        assert Settings().database_url == "production"


class TestExplicitFile:
    """Naming a file, in the class or at the call."""

    def test_inner_env_class(self, project):
        (project / ".env.production").write_text("DATABASE_URL=production\n")

        class Production(Config):
            database_url: str

            class Env:
                env_file = ".env.production"

        assert Production().database_url == "production"

    def test_inner_config_class_still_works(self, project):
        (project / ".env.production").write_text("DATABASE_URL=production\n")

        class Production(Config):
            database_url: str

            class Config:
                env_file = ".env.production"

        assert Production().database_url == "production"

    def test_argument_overrides_the_class(self, project):
        (project / ".env.production").write_text("DATABASE_URL=production\n")
        (project / ".env.staging").write_text("DATABASE_URL=staging\n")

        class Production(Config):
            database_url: str

            class Env:
                env_file = ".env.production"

        config = Production(_env_file=str(project / ".env.staging"))
        assert config.database_url == "staging"


class TestPrefix:
    """``env_prefix``, so one file can hold several subsystems."""

    def test_fields_read_prefixed_variables(self, project):
        (project / ".env").write_text(
            "DATABASE_URL=postgres://localhost/app\nDATABASE_POOL_SIZE=20\n"
        )

        class DatabaseConfig(Config):
            url: str
            pool_size: int = 10

            class Env:
                env_prefix = "DATABASE_"

        config = DatabaseConfig()

        assert config.url == "postgres://localhost/app"
        assert config.pool_size == 20

    def test_the_unprefixed_name_is_not_read(self, project):
        os.environ["URL"] = "unprefixed"

        class DatabaseConfig(Config):
            url: str = "default"

            class Env:
                env_prefix = "DATABASE_"
                env_file = None

        assert DatabaseConfig().url == "default"

    def test_two_configs_share_one_file(self, project):
        (project / ".env").write_text("DATABASE_URL=postgres://db\nMAIL_HOST=smtp.test\n")

        class DatabaseConfig(Config):
            url: str

            class Env:
                env_prefix = "DATABASE_"

        class MailConfig(Config):
            host: str

            class Env:
                env_prefix = "MAIL_"

        assert DatabaseConfig().url == "postgres://db"
        assert MailConfig().host == "smtp.test"

    def test_prefix_argument_overrides_the_class(self, project):
        os.environ["OTHER_URL"] = "other"

        class DatabaseConfig(Config):
            url: str

            class Env:
                env_prefix = "DATABASE_"
                env_file = None

        assert DatabaseConfig(_env_prefix="OTHER_").url == "other"


class TestCaseSensitivity:
    """Field names are uppercased unless told otherwise."""

    def test_uppercased_by_default(self, project):
        os.environ["DATABASE_URL"] = "postgres://localhost/app"

        assert Settings().database_url == "postgres://localhost/app"

    def test_case_sensitive_reads_the_field_name_verbatim(self, project):
        os.environ["database_url"] = "lowercase"
        os.environ["DATABASE_URL"] = "uppercase"

        class Exact(Config):
            database_url: str

            class Env:
                case_sensitive = True
                env_file = None

        assert Exact().database_url == "lowercase"

    def test_case_sensitive_false_argument_overrides_the_class(self, project):
        os.environ["DATABASE_URL"] = "uppercase"

        class Exact(Config):
            database_url: str

            class Env:
                case_sensitive = True
                env_file = None

        assert Exact(_case_sensitive=False).database_url == "uppercase"


class TestAliases:
    """A field whose environment variable has a different name."""

    def test_the_alias_names_the_variable(self, project):
        os.environ["DB_URL"] = "postgres://localhost/app"

        class Aliased(Config):
            database_url: str = Field(alias="db_url")

            class Env:
                env_file = None

        assert Aliased().database_url == "postgres://localhost/app"

    def test_the_field_name_still_works(self, project):
        os.environ["DATABASE_URL"] = "postgres://localhost/app"

        class Aliased(Config):
            database_url: str = Field(alias="db_url")

            model_config = {"populate_by_name": True}

            class Env:
                env_file = None

        assert Aliased().database_url == "postgres://localhost/app"

    def test_the_alias_wins_when_both_are_set(self, project):
        os.environ["DB_URL"] = "by-alias"
        os.environ["DATABASE_URL"] = "by-name"

        class Aliased(Config):
            database_url: str = Field(alias="db_url")

            class Env:
                env_file = None

        assert Aliased().database_url == "by-alias"


class TestMasking:
    """Secrets stay out of output that people actually look at."""

    class Secrets(Config):
        jwt_secret: str
        api_key: str
        name: str

        class Env:
            env_file = None

    def test_repr_masks_secrets(self, project):
        config = self.Secrets(jwt_secret="s3cret", api_key="sk-123", name="public")

        assert "s3cret" not in repr(config)
        assert "sk-123" not in repr(config)
        assert "public" in repr(config)

    def test_str_masks_them_too(self, project):
        # print() calls __str__, which Pydantic writes out in full. That is
        # the moment a secret would otherwise reach a terminal or a log.
        config = self.Secrets(jwt_secret="s3cret", api_key="sk-123", name="public")

        assert "s3cret" not in str(config)
        assert "sk-123" not in str(config)
        assert "public" in str(config)

    def test_the_values_are_still_readable(self, project):
        config = self.Secrets(jwt_secret="s3cret", api_key="sk-123", name="public")

        assert config.jwt_secret == "s3cret"
