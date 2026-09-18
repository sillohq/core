"""
Tortoise connection config built from a DatabaseConfig.

These pin the engine module and credential names per backend. The drivers
themselves (asyncpg, aiomysql) need not be installed — the bug being guarded
against was producing a config that could never connect, which is visible in
the dict without opening a socket.
"""

import ssl

import pytest

from sillo.record.config import DatabaseConfig
from sillo.record.manager import DatabaseManager, _build_ssl_context, _normalize_db_url


def connection_for(config: DatabaseConfig) -> dict:
    return DatabaseManager(config)._build_tortoise_config()["connections"]["default"]


# ── engine resolution ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "url, engine",
    [
        ("sqlite://:memory:", "tortoise.backends.sqlite"),
        ("postgres://u:p@h:5432/db", "tortoise.backends.asyncpg"),
        ("postgresql://u:p@h:5432/db", "tortoise.backends.asyncpg"),
        ("mysql://u:p@h:3306/db", "tortoise.backends.mysql"),
        ("mariadb://u:p@h:3306/db", "tortoise.backends.mysql"),
    ],
)
def test_the_url_scheme_selects_a_real_driver_module(url, engine):
    """``tortoise.backends.postgres`` does not exist; asyncpg is the module."""
    assert connection_for(DatabaseConfig(url=url))["engine"] == engine


def test_an_unknown_scheme_is_rejected(recwarn):
    from tortoise.exceptions import ConfigurationError

    with pytest.raises(ConfigurationError):
        connection_for(DatabaseConfig(url="oracle-ish://u:p@h/db"))


# ── credentials ──────────────────────────────────────────────────────────


def test_a_postgres_url_is_split_into_connection_parts():
    """The whole URL as the database name was the original defect."""
    creds = connection_for(
        DatabaseConfig.postgres("shop", "s3cret", user="app", host="db.internal", port=6543)
    )["credentials"]

    assert creds["database"] == "shop"
    assert creds["host"] == "db.internal"
    assert creds["port"] == 6543
    assert creds["user"] == "app"
    assert creds["password"] == "s3cret"


def test_a_mysql_url_is_split_into_connection_parts():
    creds = connection_for(DatabaseConfig.mysql("shop", "pw", user="app"))["credentials"]

    assert creds["database"] == "shop"
    assert creds["host"] == "localhost"
    assert creds["port"] == 3306
    assert creds["user"] == "app"


def test_sqlite_gets_a_file_path_and_no_server_credentials():
    creds = connection_for(DatabaseConfig.sqlite("data/app.db"))["credentials"]

    assert creds["file_path"] == "data/app.db"
    assert "host" not in creds
    assert "minsize" not in creds


def test_pool_settings_use_the_names_the_drivers_accept():
    """Both clients pop ``minsize``/``maxsize``; ``pool_size`` is ignored."""
    config = DatabaseConfig(url="postgres://u:p@h:5432/db", pool_size=4, max_overflow=6)
    creds = connection_for(config)["credentials"]

    assert creds["minsize"] == 4
    assert creds["maxsize"] == 10
    assert "pool_size" not in creds
    assert "max_overflow" not in creds


def test_pool_recycle_maps_to_each_drivers_equivalent():
    postgres = connection_for(
        DatabaseConfig(url="postgres://u:p@h:5432/db", pool_recycle=900)
    )["credentials"]
    mysql = connection_for(
        DatabaseConfig(url="mysql://u:p@h:3306/db", pool_recycle=900)
    )["credentials"]

    assert postgres["max_inactive_connection_lifetime"] == 900
    assert mysql["pool_recycle"] == 900


def test_echo_never_reaches_the_driver():
    """asyncpg has no ``echo`` argument; passing one raises at connect time."""
    creds = connection_for(
        DatabaseConfig(url="postgres://u:p@h:5432/db", echo=True)
    )["credentials"]

    assert "echo" not in creds


def test_ssl_becomes_a_context_not_a_boolean():
    creds = connection_for(
        DatabaseConfig(url="postgres://u:p@h:5432/db", ssl=True)
    )["credentials"]

    assert isinstance(creds["ssl"], ssl.SSLContext)


def test_ssl_is_absent_when_not_requested():
    creds = connection_for(DatabaseConfig(url="postgres://u:p@h:5432/db"))["credentials"]

    assert "ssl" not in creds


def test_charset_is_applied_for_mysql_only():
    mysql = connection_for(DatabaseConfig(url="mysql://u:p@h:3306/db"))["credentials"]
    postgres = connection_for(DatabaseConfig(url="postgres://u:p@h:5432/db"))["credentials"]

    assert mysql["charset"] == "utf8mb4"
    assert "charset" not in postgres


# ── the rest of the config document ──────────────────────────────────────


def test_registered_model_modules_reach_the_config():
    manager = DatabaseManager(DatabaseConfig.sqlite())
    manager.register_models("myapp.models", "myapp.billing.models")

    apps = manager._build_tortoise_config()["apps"]["models"]
    assert apps["models"] == ["myapp.models", "myapp.billing.models"]
    assert apps["default_connection"] == "default"


def test_timezone_is_carried_through():
    config = DatabaseConfig(url="sqlite://:memory:", timezone="Europe/Berlin")
    assert DatabaseManager(config)._build_tortoise_config()["timezone"] == "Europe/Berlin"


# ── _normalize_db_url ──────────────────────────────────────────────────


def test_a_url_with_no_scheme_separator_is_returned_unchanged():
    assert _normalize_db_url("not-a-url") == "not-a-url"


# ── _build_ssl_context ────────────────────────────────────────────────


def _self_signed_cert_and_key(tmp_path):
    """A throwaway self-signed cert/key pair, just to exercise
    ``load_cert_chain`` -- nothing here is meant to be trusted."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    import datetime

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "sillo-test")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
        .not_valid_after(
            datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)
        )
        .sign(key, hashes.SHA256())
    )

    cert_path = tmp_path / "cert.pem"
    key_path = tmp_path / "key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    return str(cert_path), str(key_path)


def test_ssl_context_without_a_client_cert_still_verifies_the_server():
    context = _build_ssl_context(DatabaseConfig(url="sqlite://:memory:"))
    assert context.verify_mode.name == "CERT_REQUIRED"


def test_ssl_context_loads_a_client_cert_when_configured(tmp_path):
    cert_path, key_path = _self_signed_cert_and_key(tmp_path)
    config = DatabaseConfig(
        url="postgres://u:p@h/db", ssl_cert=cert_path, ssl_key=key_path
    )

    # Raises if the cert/key pair cannot be loaded -- the point of the test.
    _build_ssl_context(config)
