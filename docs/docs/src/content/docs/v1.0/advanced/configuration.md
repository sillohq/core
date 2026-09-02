---
title: "Sillo Configuration System"
description: "Config class, .env loading, secret masking, environment variables"
---

## 1. Config Base Class

**Source**: `core/sillo/config/core.py`

`Config` is the base class for all Sillo configuration. It extends Pydantic's
`BaseModel` with automatic `.env` file loading, environment variable mapping,
and secret masking in `repr` output.

The `.env` reading is Sillo's own — `sillo.env`, documented in
[Environment & .env](/v1.0/guides/environment/). `python-dotenv` is not a
dependency of the framework and is not imported anywhere in it.

### Class Definition

```python
class Config(BaseModel):
    """Base configuration class, loaded from the environment."""

    model_config = ConfigDict(extra="ignore")

    def __init__(
        self,
        _env_file: str | None = _UNSET,
        _case_sensitive: bool = _UNSET,
        _env_prefix: str = _UNSET,
        **data
    ):
```

`_UNSET` is a sentinel, not a default value: it separates "the subclass said
nothing", which loads the project's `.env`, from an explicit `None`, which
loads no file at all.

### Features

| Feature | Description |
|---------|-------------|
| `.env` loading | Finds and loads the project's `.env` through `sillo.env.autoload`, once per process. No third-party dependency |
| Env prefix | `env_prefix` maps a whole class onto `PREFIX_*` variables |
| Type validation | All fields are validated by Pydantic at construction time |
| Env var mapping | Field names are mapped to uppercase environment variables by default |
| Secret masking | Fields with names containing `secret`, `key`, `password`, `token`, etc. are masked in `repr()` |
| IDE autocomplete | Full type hints for all fields |
| Extra field ignore | `extra="ignore"` prevents crashes from unknown environment variables |

### Initialization Flow

```python
def __init__(self, _env_file=_UNSET, _case_sensitive=_UNSET, _env_prefix=_UNSET, **data):
    # 1. Read the subclass's inner options class (Env, or the older Config)
    options = self._options()
    env_file = _env_file if _env_file is not _UNSET else options.get("env_file", _UNSET)
    case_sensitive = ...
    prefix = ...

    # 2. Load the file: the project's .env when nothing was asked for,
    #    the named file when one was, nothing at all when it is None.
    if env_file is _UNSET:
        autoload()
    elif env_file is not None:
        load_env(env_file)

    # 3. Map fields onto environment variables, alias first
    env_data = {}
    for name, field in self.__class__.model_fields.items():
        alias = field.alias if isinstance(field.alias, str) else None
        for candidate in (alias, name):
            if candidate is None:
                continue
            key = prefix + candidate
            if not case_sensitive:
                key = key.upper()
            if key in os.environ:
                env_data[alias or name] = os.environ[key]
                break

    # 4. Merge with provided data (provided data takes precedence)
    env_data.update(data)
    super().__init__(**env_data)
```

Three sources, most specific first: arguments beat the real environment, and
the real environment beats the file.

### Environment Variable Mapping

```python
class AppConfig(Config):
    database_url: str
    debug: bool = False

# Maps to:
#   database_url → DATABASE_URL (env var)
#   debug → DEBUG (env var)

config = AppConfig()  # Reads DATABASE_URL and DEBUG from environment
config = AppConfig(database_url="sqlite:///app.db")  # Explicit values take precedence
```

### Secret Masking

```python
def __repr__(self) -> str:
    fields_repr = {}
    for field_name, field_value in self.model_dump().items():
        if self._is_secret_field(field_name):
            fields_repr[field_name] = "***"
        else:
            fields_repr[field_name] = field_value
    return f"<{self.__class__.__name__} {fields_repr}>"

@staticmethod
def _is_secret_field(field_name: str) -> bool:
    secret_keywords = (
        "secret", "key", "password", "token", "apikey", "api_key",
        "auth", "credential", "private",
    )
    return any(keyword in field_name.lower() for keyword in secret_keywords)
```

**Example:**

```python
class AppConfig(Config):
    database_url: str
    jwt_secret: str
    api_key: str

config = AppConfig(
    database_url="postgres://localhost/mydb",
    jwt_secret="super-secret",
    api_key="sk-123"
)
print(repr(config))
# <AppConfig {'database_url': 'postgres://localhost/mydb', 'jwt_secret': '***', 'api_key': '***'}>
```

### Subclass Options Inner Class

```python
class AppConfig(Config):
    database_url: str
    debug: bool = False

    class Env:
        env_file = ".env"          # None loads no file
        env_prefix = ""
        case_sensitive = False
```

`Env` is checked first, then `Config` — the name earlier versions documented,
kept working but no longer recommended, since Pydantic uses it for its own
deprecated class-based settings and warns whenever it sees one.

Each setting can be overridden at instantiation time:

```python
config = AppConfig(_env_file=".env.production", _case_sensitive=True, _env_prefix="APP_")
```

### Re-exported Field

```python
# config/core.py
from pydantic import Field as PydanticField
Field = PydanticField
```

`Field` is re-exported from Pydantic for convenience, so users can import from
`sillo.config`:

```python
from sillo.config import Config, Field

class AppConfig(Config):
    name: str = Field(default="Sillo", description="Application name")
```

---

## 2. DatabaseConfig

**Pattern**: Each subsystem owns its configuration class, extending `Config`.

### Example Structure

```python
from sillo.config import Config, Field
from typing import Literal

class DatabaseConfig(Config):
    """Database connection configuration."""

    # Connection
    url: str = Field(description="Database connection URL")
    pool_size: int = Field(default=10, description="Connection pool size")
    max_overflow: int = Field(default=20, description="Max overflow connections")
    pool_timeout: int = Field(default=30, description="Pool checkout timeout (seconds)")
    pool_recycle: int = Field(default=3600, description="Connection recycle time (seconds)")

    # Behavior
    echo: bool = Field(default=False, description="Log all SQL statements")
    echo_pool: bool = Field(default=False, description="Log pool checkouts/checkins")
    autoflush: bool = Field(default=True, description="Autoflush after each statement")
    autocommit: bool = Field(default=False, description="Autocommit mode")

    # Migration
    migration_dir: str = Field(default="migrations", description="Migration scripts directory")

    class Env:
        env_prefix = "DATABASE_"
```

### Environment Variable Mapping

```
DATABASE_URL=postgres://user:pass@localhost:5432/mydb
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=30
DATABASE_ECHO=false
DATABASE_MIGRATION_DIR=./migrations
```

### Usage

```python
db_config = DatabaseConfig()
# or
db_config = DatabaseConfig(url="sqlite:///app.db", pool_size=5)
```

---

## 3. SessionConfig

### Example Structure

```python
class SessionConfig(Config):
    """Session management configuration."""

    # Storage
    driver: Literal["cookie", "file", "redis", "database"] = Field(
        default="cookie", description="Session storage driver"
    )
    lifetime: int = Field(default=120, description="Session lifetime in minutes")
    encrypt: bool = Field(default=True, description="Encrypt session data")

    # Cookie settings (when driver="cookie")
    cookie_name: str = Field(default="sillo_session", description="Session cookie name")
    cookie_domain: str | None = Field(default=None, description="Cookie domain")
    cookie_path: str = Field(default="/", description="Cookie path")
    cookie_secure: bool = Field(default=False, description="Require HTTPS for cookie")
    cookie_httponly: bool = Field(default=True, description="HttpOnly flag")
    cookie_samesite: Literal["lax", "strict", "none"] = Field(
        default="lax", description="SameSite attribute"
    )

    # Redis settings (when driver="redis")
    redis_url: str | None = Field(default=None, description="Redis connection URL")

    # Database settings (when driver="database")
    table_name: str = Field(default="sessions", description="Sessions table name")

    class Env:
        env_prefix = "SESSION_"
```

### Environment Variable Mapping

```
SESSION_DRIVER=redis
SESSION_LIFETIME=60
SESSION_ENCRYPT=true
SESSION_COOKIE_NAME=my_session
SESSION_COOKIE_SECURE=true
SESSION_REDIS_URL=redis://localhost:6379/0
```

---

## 4. MailConfig

### Example Structure

```python
class MailConfig(Config):
    """Email sending configuration."""

    # SMTP settings
    host: str = Field(default="localhost", description="SMTP server host")
    port: int = Field(default=587, description="SMTP server port")
    username: str | None = Field(default=None, description="SMTP username")
    password: str | None = Field(default=None, description="SMTP password")
    use_tls: bool = Field(default=True, description="Use STARTTLS")
    use_ssl: bool = Field(default=False, description="Use SSL/TLS")

    # Sender defaults
    from_address: str = Field(default="noreply@example.com", description="Default sender address")
    from_name: str = Field(default="Sillo App", description="Default sender name")

    # Queue
    queue_enabled: bool = Field(default=False, description="Enable mail queue")
    retry_count: int = Field(default=3, description="Retry count for failed sends")
    retry_delay: int = Field(default=60, description="Retry delay in seconds")

    class Env:
        env_prefix = "MAIL_"
```

### Environment Variable Mapping

```
MAIL_HOST=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=user@gmail.com
MAIL_PASSWORD=app-specific-password
MAIL_USE_TLS=true
MAIL_FROM_ADDRESS=noreply@myapp.com
```

---

## 5. CorsConfig

### Example Structure

```python
class CorsConfig(Config):
    """CORS (Cross-Origin Resource Sharing) configuration."""

    allow_origins: list[str] = Field(
        default=["*"],
        description="Allowed origins. Use ['*'] for all origins."
    )
    allow_methods: list[str] = Field(
        default=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        description="Allowed HTTP methods"
    )
    allow_headers: list[str] = Field(
        default=["*"],
        description="Allowed ctx headers"
    )
    allow_credentials: bool = Field(
        default=False,
        description="Allow credentials (cookies, auth headers)"
    )
    expose_headers: list[str] = Field(
        default=[],
        description="Headers exposed to the browser"
    )
    max_age: int = Field(
        default=600,
        description="Preflight cache duration in seconds"
    )

    class Env:
        env_prefix = "CORS_"
```

### Environment Variable Mapping

```
CORS_ALLOW_ORIGINS=http://localhost:3000,https://myapp.com
CORS_ALLOW_METHODS=GET,POST,PUT,DELETE
CORS_ALLOW_CREDENTIALS=true
CORS_MAX_AGE=86400
```

### Usage with Middleware

```python
from sillo.middleware.security import CORSMiddleware

cors_config = CorsConfig(
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
)

app.use(CORSMiddleware(
    allow_origins=cors_config.allow_origins,
    allow_methods=cors_config.allow_methods,
    allow_headers=cors_config.allow_headers,
    allow_credentials=cors_config.allow_credentials,
    max_age=cors_config.max_age,
))
```

---

## 6. CSRFConfig

### Example Structure

```python
from sillo import HttpContext

class CSRFConfig(Config):
    """CSRF (Cross-Site HttpContext Forgery) protection configuration."""

    enabled: bool = Field(default=True, description="Enable CSRF protection")
    secret: str = Field(description="Secret key for CSRF token generation")
    token_name: str = Field(default="_token", description="Form field name for token")
    header_name: str = Field(default="X-CSRF-Token", description="Header name for token")
    cookie_name: str = Field(default="csrf_token", description="Cookie name for token")
    lifetime: int = Field(default=3600, description="Token lifetime in seconds")
    secure: bool = Field(default=False, description="Require HTTPS for cookie")
    same_site: Literal["lax", "strict", "none"] = Field(
        default="lax", description="SameSite attribute"
    )
    exempt_methods: list[str] = Field(
        default=["GET", "HEAD", "OPTIONS"],
        description="Methods exempt from CSRF checks"
    )
    exempt_paths: list[str] = Field(
        default=[],
        description="Paths exempt from CSRF checks"
    )

    class Env:
        env_prefix = "CSRF_"
```

### Environment Variable Mapping

```
CSRF_ENABLED=true
CSRF_SECRET=my-csrf-secret-key
CSRF_TOKEN_NAME=_token
CSRF_HEADER_NAME=X-CSRF-Token
CSRF_LIFETIME=3600
```

---

## 7. RateLimitConfig

### Example Structure

```python
class RateLimitConfig(Config):
    """Rate limiting configuration."""

    enabled: bool = Field(default=True, description="Enable rate limiting")
    driver: Literal["memory", "redis", "database"] = Field(
        default="memory", description="Rate limit storage driver"
    )

    # Default limits
    default_rate: str = Field(
        default="60/minute",
        description="Default rate limit (format: count/period)"
    )
    default_burst: int = Field(
        default=10,
        description="Default burst allowance"
    )

    # Redis settings
    redis_url: str | None = Field(default=None, description="Redis URL for rate limiting")

    # BaseResponse
    retry_after_header: bool = Field(
        default=True,
        description="Include Retry-After header in 429 responses"
    )
    message: str = Field(
        default="Rate limit exceeded. Please try again later.",
        description="Error message for rate limited requests"
    )

    class Env:
        env_prefix = "RATE_LIMIT_"
```

### Environment Variable Mapping

```
RATE_LIMIT_ENABLED=true
RATE_LIMIT_DRIVER=redis
RATE_LIMIT_DEFAULT_RATE=100/minute
RATE_LIMIT_DEFAULT_BURST=20
RATE_LIMIT_REDIS_URL=redis://localhost:6379/1
```

### Period Parsing

The `default_rate` string is parsed into count and period:

```python
"60/minute"  → 60 requests per 60 seconds
"1000/hour"  → 1000 requests per 3600 seconds
"10/second"  → 10 requests per 1 second
"5000/day"   → 5000 requests per 86400 seconds
```

---

## 8. InertiaConfig

### Example Structure

```python
class InertiaConfig(Config):
    """Inertia.js integration configuration."""

    # Version management
    version: str | None = Field(
        default=None,
        description="Asset version for cache busting"
    )

    # Root template
    root_view: str = Field(
        default="app.html",
        description="Root HTML template that wraps Inertia responses"
    )

    # SSR (Server-Side Rendering)
    ssr_enabled: bool = Field(default=False, description="Enable SSR mode")
    ssr_url: str | None = Field(
        default=None,
        description="SSR server URL (e.g., http://localhost:13714)"
    )

    # History encryption
    encrypt_history: bool = Field(
        default=False,
        description="Encrypt back/forward history state"
    )

    # Testing
    testing_enabled: bool = Field(
        default=False,
        description="Enable Inertia testing helpers"
    )

    class Env:
        env_prefix = "INERTIA_"
```

### Environment Variable Mapping

```
INERTIA_VERSION=abc123
INERTIA_ROOT_VIEW=app.html
INERTIA_SSR_ENABLED=true
INERTIA_SSR_URL=http://localhost:13714
INERTIA_ENCRYPT_HISTORY=true
```

### Inertia Integration Pattern

```python
from inertia import InertiaConfig, inertia_middleware

config = InertiaConfig(
    version="1.0.0",
    root_view="app.html",
)

# Inertia middleware uses config to:
# 1. Compare X-Inertia-Version header with config.version
# 2. Force a full page reload on version mismatch
# 3. Render the root template with the Inertia page object
```

---

## 9. Configuration Patterns

### 10.1 Composite Configuration

Applications typically create a top-level config that composes subsystem configs:

```python
from sillo.config import Config, Field

class AppConfig(Config):
    # Application
    app_name: str = Field(default="My App")
    debug: bool = Field(default=False)
    secret_key: str = Field(description="Application secret key")

    # Subsystem configs are declared as fields
    # They can be nested or flattened depending on preference

    class Env:
        env_file = ".env"

# Flat approach (all vars at top level)
class FlatAppConfig(Config):
    debug: bool = False
    database_url: str = ""
    session_driver: str = "cookie"
    mail_host: str = "localhost"
    cors_allow_origins: str = "*"
```

### 10.2 Environment-Specific Configuration

```python
import os

class AppConfig(Config):
    debug: bool = False
    database_url: str = ""
    log_level: str = "info"

# Load from environment-specific .env file
env = os.getenv("APP_ENV", "development")
config = AppConfig(_env_file=f".env.{env}")
# .env.development, .env.staging, .env.production
```

### 10.3 Validation with Pydantic

```python
from pydantic import field_validator
from sillo.config import Config

class DatabaseConfig(Config):
    url: str
    pool_size: int = 10

    @field_validator("url")
    @classmethod
    def validate_url(cls, v):
        if not v.startswith(("postgres://", "mysql://", "sqlite://")):
            raise ValueError("Unsupported database URL scheme")
        return v

    @field_validator("pool_size")
    @classmethod
    def validate_pool_size(cls, v):
        if v < 1 or v > 100:
            raise ValueError("Pool size must be between 1 and 100")
        return v
```

### 10.4 Integration with SilloApp

```python
from sillo import SilloApp
from sillo.config import Config

class AppConfig(Config):
    debug: bool = False
    title: str = "My API"
    version: str = "1.0.0"

config = AppConfig()

app = SilloApp(
    debug=config.debug,
    title=config.title,
    version=config.version,
)
```

### 10.5 Configuration Loading Priority

The loading priority for configuration values is:

1. **Constructor arguments** (highest priority)
2. **Environment variables**
3. **`.env` file values**
4. **Field defaults** (lowest priority)

```python
# .env file contains: DEBUG=true
# Environment variable: DEBUG=false

config = AppConfig()                    # DEBUG=False (env var wins)
config = AppConfig(_env_file=".env")    # DEBUG=False (env var still wins)
config = AppConfig(debug=True)          # DEBUG=True (constructor arg wins)
```

### 10.6 Secret Management

Configuration fields with secret-related names are automatically masked:

```python
class AppConfig(Config):
    database_url: str          # Not masked
    app_name: str              # Not masked
    jwt_secret: str            # Masked (contains "secret")
    api_key: str               # Masked (contains "key")
    smtp_password: str         # Masked (contains "password")
    stripe_token: str          # Masked (contains "token")
    auth_token: str            # Masked (contains "auth" and "token")
    private_key: str           # Masked (contains "private")
    credentials: str           # Masked (contains "credential")
```

The masking applies to `repr()` output only. The actual values are accessible
via attribute access:

```python
config = AppConfig(jwt_secret="super-secret")
print(repr(config))        # <AppConfig {'jwt_secret': '***'}>
print(config.jwt_secret)   # "super-secret"
```

---

## Appendix: Config Class Hierarchy

```mermaid
graph TD
    BM["pydantic.BaseModel"] --> CFG["Config"]
    CFG --> DBC["DatabaseConfig"]
    CFG --> SC["SessionConfig"]
    CFG --> MC["MailConfig"]
    CFG --> CC["CorsConfig"]
    CFG --> CSRF["CSRFConfig"]
    CFG --> RLC["RateLimitConfig"]
    CFG --> IC["InertiaConfig"]
    CFG --> APP_CFG["AppConfig (user-defined)"]
```

### Module Structure

```
core/sillo/config/
├── __init__.py          # Re-exports Config, Field
└── core.py              # Config base class, Field re-export
```

### Public API

```python
from sillo.config import Config, Field

__all__ = ["Config", "Field"]
```

The `Field` export is Pydantic's `Field` function, re-exported for convenience:

```python
from pydantic import Field as PydanticField
Field = PydanticField
```

### Extension Points

Each subsystem can define its own `Config` subclass:

```python
# In sillo/session/config.py (if it exists)
from sillo.config import Config, Field

class SessionConfig(Config):
    driver: str = "cookie"
    lifetime: int = 120
    # ...

# In sillo/mail/config.py (if it exists)
from sillo.config import Config, Field

class MailConfig(Config):
    host: str = "localhost"
    port: int = 587
    # ...
```

The pattern is consistent: every subsystem's config extends `Config`, gets
`.env` loading for free, and masks secrets automatically.
