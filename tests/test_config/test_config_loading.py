"""Tests for configuration loading."""

import os
from typing import Literal

import pytest
from pydantic import ValidationError

from sillo.config import Config, Field


class TestConfigLoading:
    """Test basic config loading."""

    def test_load_from_env_variables(self, isolated_env):
        """Config loads from environment variables."""
        os.environ['DATABASE_URL'] = 'postgresql://localhost/db'
        os.environ['JWT_SECRET'] = 'test-secret'
        os.environ['DEBUG'] = 'true'

        class TestConfig(Config):
            database_url: str
            jwt_secret: str
            debug: bool = False

            class Config:
                env_file = None  # Don't load .env file

        config = TestConfig()

        assert config.database_url == 'postgresql://localhost/db'
        assert config.jwt_secret == 'test-secret'
        assert config.debug is True

    def test_load_from_env_file(self, temp_env_file, isolated_env):
        """Config loads from .env file."""

        class TestConfig(Config):
            database_url: str
            jwt_secret: str
            debug: bool
            port: int

        config = TestConfig(_env_file=temp_env_file)

        assert config.database_url == 'postgresql://localhost/testdb'
        assert config.jwt_secret == 'test-secret-key'
        assert config.debug is True
        assert config.port == 9000

    def test_case_insensitive_loading(self, temp_env_file, isolated_env):
        """Environment variables are case-insensitive by default."""

        class TestConfig(Config):
            database_url: str
            jwt_secret: str

        config = TestConfig(_env_file=temp_env_file, _case_sensitive=False)
        assert config.database_url == 'postgresql://localhost/testdb'

    def test_required_field_missing(self, empty_env_file, isolated_env):
        """ValidationError when required field missing."""

        class TestConfig(Config):
            database_url: str
            jwt_secret: str

        with pytest.raises(ValidationError) as exc_info:
            TestConfig(_env_file=empty_env_file)

        errors = exc_info.value.errors()
        assert len(errors) == 2
        assert errors[0]['type'] == 'missing'
        assert errors[1]['type'] == 'missing'

    def test_optional_field_with_default(self, empty_env_file, isolated_env):
        """Optional fields use default value."""

        class TestConfig(Config):
            database_url: str = 'sqlite:///db.sqlite'
            debug: bool = False

        config = TestConfig(_env_file=empty_env_file)
        assert config.database_url == 'sqlite:///db.sqlite'
        assert config.debug is False


class TestConfigTypes:
    """Test type validation."""

    def test_string_type(self, isolated_env):
        """String fields work correctly."""
        os.environ['NAME'] = 'test-app'

        class TestConfig(Config):
            name: str

            class Config:
                env_file = None

        config = TestConfig()
        assert isinstance(config.name, str)
        assert config.name == 'test-app'

    def test_integer_type(self, isolated_env):
        """Integer fields are converted from string."""
        os.environ['PORT'] = '8000'

        class TestConfig(Config):
            port: int

            class Config:
                env_file = None

        config = TestConfig()
        assert isinstance(config.port, int)
        assert config.port == 8000

    def test_integer_type_invalid(self, isolated_env):
        """Invalid integer raises ValidationError."""
        os.environ['PORT'] = 'not-a-number'

        class TestConfig(Config):
            port: int

            class Config:
                env_file = None

        with pytest.raises(ValidationError):
            TestConfig()

    def test_boolean_type_true(self, isolated_env):
        """Boolean 'true' values."""
        for true_value in ['true', '1', 'yes', 'on', 'True', 'TRUE']:
            os.environ['DEBUG'] = true_value

            class TestConfig(Config):
                debug: bool

                class Config:
                    env_file = None

            config = TestConfig()
            assert config.debug is True

    def test_boolean_type_false(self, isolated_env):
        """Boolean 'false' values."""
        for false_value in ['false', '0', 'no', 'off', 'False', 'FALSE']:
            os.environ['DEBUG'] = false_value

            class TestConfig(Config):
                debug: bool

                class Config:
                    env_file = None

            config = TestConfig()
            assert config.debug is False

    def test_boolean_type_invalid(self, isolated_env):
        """Invalid boolean raises ValidationError."""
        os.environ['DEBUG'] = 'maybe'

        class TestConfig(Config):
            debug: bool

            class Config:
                env_file = None

        with pytest.raises(ValidationError):
            TestConfig()

    def test_float_type(self, isolated_env):
        """Float fields are converted from string."""
        os.environ['TIMEOUT'] = '30.5'

        class TestConfig(Config):
            timeout: float

            class Config:
                env_file = None

        config = TestConfig()
        assert isinstance(config.timeout, float)
        assert config.timeout == 30.5

    def test_literal_type(self, isolated_env):
        """Literal types restrict to specific values."""
        os.environ['ENVIRONMENT'] = 'production'

        class TestConfig(Config):
            environment: Literal['dev', 'staging', 'production']

            class Config:
                env_file = None

        config = TestConfig()
        assert config.environment == 'production'

    def test_literal_type_invalid(self, isolated_env):
        """Invalid literal value raises ValidationError."""
        os.environ['ENVIRONMENT'] = 'invalid'

        class TestConfig(Config):
            environment: Literal['dev', 'staging', 'production']

            class Config:
                env_file = None

        with pytest.raises(ValidationError):
            TestConfig()


class TestConfigField:
    """Test Field() usage."""

    def test_field_with_description(self, isolated_env):
        """Field() allows adding description."""
        os.environ['DATABASE_URL'] = 'postgresql://localhost/db'

        class TestConfig(Config):
            database_url: str = Field(
                ...,
                description="PostgreSQL connection string"
            )

            class Config:
                env_file = None

        config = TestConfig()
        assert config.database_url == 'postgresql://localhost/db'

    def test_field_with_default(self, isolated_env):
        """Field() with default value."""

        class TestConfig(Config):
            log_level: str = Field(default='info')

            class Config:
                env_file = None

        config = TestConfig()
        assert config.log_level == 'info'

    def test_field_with_alias(self, isolated_env):
        """Field() with alias maps different env var name."""
        os.environ['DB_URL'] = 'postgresql://localhost/db'

        class TestConfig(Config):
            database_url: str = Field(..., alias='db_url')

            class Config:
                env_file = None
                populate_by_name = True

        config = TestConfig(**{'db_url': 'postgresql://localhost/db'})
        assert config.database_url == 'postgresql://localhost/db'


class TestConfigRepr:
    """Test config representation."""

    def test_secret_fields_masked(self, isolated_env):
        """Secret fields are masked in repr."""
        os.environ['JWT_SECRET'] = 'super-secret'
        os.environ['API_KEY'] = 'secret-api-key'
        os.environ['PASSWORD'] = 'my-password'
        os.environ['NAME'] = 'public-name'

        class TestConfig(Config):
            jwt_secret: str
            api_key: str
            password: str
            name: str

            class Config:
                env_file = None

        config = TestConfig()
        repr_str = repr(config)

        # Secrets should be masked
        assert '***' in repr_str
        assert 'super-secret' not in repr_str
        assert 'secret-api-key' not in repr_str
        assert 'my-password' not in repr_str

        # Public values should be visible
        assert 'public-name' in repr_str


class TestEnvironmentSpecific:
    """Test environment-specific configuration."""

    def test_development_config(self, isolated_env, tmp_path):
        """Development configuration."""
        env_file_path = tmp_path / '.env.development'
        env_file_path.write_text(
            'DATABASE_URL=sqlite:///dev.db\n'
            'DEBUG=true\n'
            'LOG_LEVEL=debug\n'
        )

        class TestConfig(Config):
            database_url: str
            debug: bool
            log_level: str

        config = TestConfig(_env_file=str(env_file_path))
        assert config.database_url == 'sqlite:///dev.db'
        assert config.debug is True
        assert config.log_level == 'debug'

    def test_production_config(self, isolated_env, tmp_path):
        """Production configuration."""
        env_file_path = tmp_path / '.env.production'
        env_file_path.write_text(
            'DATABASE_URL=postgresql://prod-server/db\n'
            'DEBUG=false\n'
            'LOG_LEVEL=warning\n'
        )

        class TestConfig(Config):
            database_url: str
            debug: bool
            log_level: str

        config = TestConfig(_env_file=str(env_file_path))
        assert config.database_url == 'postgresql://prod-server/db'
        assert config.debug is False
        assert config.log_level == 'warning'
