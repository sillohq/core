---
title: Configuration Management
description: Type-safe configuration with Pydantic and environment variables
---

Sillo provides type-safe configuration management using Pydantic, with `.env`
loading, validation, and environment-specific settings.

## Overview

The configuration system provides:

- **Type Safety** - Full type hints, IDE autocomplete, mypy support
- **Validation** - Pydantic validates all values on load
- **Environment Variables** - Load from `.env` files
- **Required vs Optional** - Clear which settings are mandatory
- **Secret Masking** - Automatically hides sensitive values
- **Environment-Specific** - Different configs per environment (dev/staging/prod)
- **Defaults** - Sensible defaults for optional settings

## Installation

Nothing to install. Sillo parses `.env` itself — `python-dotenv` is not a
dependency, and there is no `load_dotenv()` call to remember. Constructing a
config, or a `SilloApp`, loads the project's `.env` on its own. See
[Environment & .env](/guides/environment/) for the file format and the
precedence rules.

## Quick Start

### 1. Define Configuration

```python
from sillo.config import Config, Field
from typing import Literal

class AppConfig(Config):
    """Application configuration from .env"""
    
    # Required fields
    database_url: str
    jwt_secret: str
    
    # Optional fields with defaults
    debug: bool = False
    log_level: Literal['debug', 'info', 'warning', 'error'] = 'info'
    port: int = 8000

# Load configuration — .env is found and read automatically
config = AppConfig()
```

### 2. Create .env File

```bash
# .env
DATABASE_URL=postgresql://localhost/mydb
JWT_SECRET=your-secret-key
DEBUG=true
LOG_LEVEL=debug
PORT=8000
```

### 3. Use in Application

```python
from sillo import SilloApp

app = SilloApp(
    debug=config.debug,
    title="My API"
)

@app.on_startup
async def startup():
    print(f"Starting in {config.environment}")
    await database.connect(config.database_url)
```

## Configuration Classes

### Basic Structure

```python
from sillo.config import Config, Field
from typing import Literal, Optional

class AppConfig(Config):
    """Define all application settings."""
    
    # Required string
    database_url: str
    
    # Required with description
    api_key: str = Field(..., description="Third-party API key")
    
    # Optional with default
    debug: bool = False
    
    # Enum-like with type
    environment: Literal['dev', 'staging', 'prod'] = 'dev'
    
    # Integer with default
    port: int = 8000
    
    # Optional (can be None)
    cache_url: Optional[str] = None
```

### Adjusting the Defaults

An inner `Env` class changes how the fields map onto the environment. Every
setting is optional:

```python
class DatabaseConfig(Config):
    url: str
    pool_size: int = 10

    class Env:
        env_file = '.env.production'   # None loads no file at all
        env_prefix = 'DATABASE_'       # DATABASE_URL, DATABASE_POOL_SIZE
        case_sensitive = False         # the default: field names uppercased
```

`env_prefix` is what lets one `.env` serve several subsystems without the
field names growing prefixes of their own.

:::note
An inner class named `Config` is read the same way — that is what earlier
versions documented. Prefer `Env`: Pydantic claims the name `Config` for its
own deprecated class-based settings and warns on every model that uses one.
:::

### Type Support

Pydantic supports many types automatically:

```python
from sillo.config import Config
from typing import Literal, Optional
from pathlib import Path

class Config(Config):
    # Basic types
    name: str
    port: int
    timeout: float
    enabled: bool
    
    # Enums
    environment: Literal['dev', 'staging', 'prod']
    log_level: Literal['debug', 'info', 'warning', 'error']
    
    # Optional
    optional_key: Optional[str] = None
    
    # Collections
    allowed_origins: list[str] = []
    cors_headers: dict[str, str] = {}
    
    # Paths
    log_file: Path = Path('app.log')
```

### Validation

Pydantic validates types on load:

```python
port: int = 8000        # Must be integer or convertible to int
debug: bool = False     # Must be bool or 'true'/'false' string
timeout: float = 30.0   # Must be float

# These work:
PORT=8000           # Loaded as int
DEBUG=true          # Converted to bool
DEBUG=yes           # So are yes/no, on/off and 1/0
TIMEOUT=30.5        # Loaded as float

# These fail:
PORT=eight          # ValidationError
DEBUG=maybe         # ValidationError
```

## .env Files

### File Format

```bash
# Simple key=value
DATABASE_URL=postgresql://localhost/db
DEBUG=true
PORT=8000

# Spaces around = are fine
KEY = value

# Quotes keep whitespace; single quotes stop all expansion
QUOTED="  spaces kept  "
LITERAL='nothing $expands here'

# Multi-line values, for keys and certificates
PRIVATE_KEY="""-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkq...
-----END PRIVATE KEY-----"""

# References to earlier keys, and to the surrounding environment
DB_HOST=db.internal
DATABASE_URL=postgres://${DB_HOST}:5432/app
PORT=${PORT:-8000}

# Comments with #
# This is a comment
SECRET_KEY=abc123  # Inline comment — the space before # is what makes it one
PASSWORD=pa#ssword # No space, so this hash is part of the password
```

The full grammar is in [Environment & .env](/guides/environment/).

### File Locations

```
project/
├── .env                 # Main config (git ignored)
├── .env.example         # Template (commit this)
├── .env.development     # Development overrides
├── .env.production      # Production config (git ignored)
└── .env.test           # Test config
```

### Environment-Specific Loading

The usual way is from the outside, so the code does not have to know:

```bash
SILLO_ENV_FILE=.env.production sillo serve
```

Or decide in code:

```python
import os

class AppConfig(Config):
    database_url: str

    class Env:
        env_file = f".env.{os.getenv('ENVIRONMENT', 'development')}"
```

To layer a developer's overrides on top of a shared file:

```python
from sillo.env import load_env

load_env()                              # .env
load_env('.env.local', override=True)   # then whatever this machine changes
```

## Usage Patterns

### Basic Usage

```python
# Load config
config = AppConfig()

# Access values (type-safe)
db_url: str = config.database_url
port: int = config.port
debug: bool = config.debug

# All have proper types and IDE autocomplete
```

### With Sillo App

```python
from sillo import SilloApp

config = AppConfig()

app = SilloApp(
    debug=config.debug,
    title="My API",
)

@app.on_startup
async def startup():
    print(f"Starting {app.title}")
    print(f"Environment: {config.environment}")
    print(f"Database: {config.database_url}")
```

### Secret Masking

```python
config = AppConfig()

# JWT_SECRET, API_KEY, PASSWORD fields are automatically masked
print(config)
# <AppConfig {..., 'jwt_secret': '***', 'api_key': '***', ...}>

# Secrets not masked in direct access
secret = config.jwt_secret  # Full value available in code
```

### Conditional Behavior

```python
class AppConfig(Config):
    environment: Literal['development', 'production']
    debug: bool = False

config = AppConfig()

# Change behavior based on config
if config.debug:
    logger.setLevel('DEBUG')
else:
    logger.setLevel('INFO')

if config.environment == 'production':
    use_https()
else:
    allow_http()
```

### Feature Flags

```python
class AppConfig(Config):
    enable_payments: bool = False
    enable_notifications: bool = False
    enable_analytics: bool = False

config = AppConfig()

# Enable/disable features via .env
if config.enable_payments:
    setup_stripe(config.stripe_api_key)

if config.enable_notifications:
    setup_email_service()
```

## Common Patterns

### Database Configuration

```python
class AppConfig(Config):
    # Option 1: Full URL
    database_url: str
    
    # Option 2: Components
    database_host: str = 'localhost'
    database_port: int = 5432
    database_user: str
    database_password: str
    database_name: str
    
    @property
    def db_connection_string(self) -> str:
        """Build connection string from components."""
        return (
            f"postgresql://"
            f"{self.database_user}:{self.database_password}"
            f"@{self.database_host}:{self.database_port}"
            f"/{self.database_name}"
        )
```

### Security Settings

```python
class AppConfig(Config):
    jwt_secret: str                    # Never commit!
    jwt_algorithm: str = 'HS256'
    jwt_expiration_hours: int = 24
    
    cors_origins: str = '*'            # Restrict in production
    enable_swagger: bool = False       # Disable in production
    debug: bool = False                # Always False in production

# Production .env
DEBUG=false
ENABLE_SWAGGER=false
CORS_ORIGINS=https://app.example.com,https://www.example.com
```

### Email Configuration

```python
from typing import Literal

class EmailConfig(Config):
    email_provider: Literal['smtp', 'sendgrid', 'mailgun'] = 'smtp'
    
    # SMTP settings
    smtp_host: str = 'localhost'
    smtp_port: int = 587
    smtp_user: str = ''
    smtp_password: str = ''
    
    # API key for SendGrid/Mailgun
    api_key: str = ''
    
    email_from: str = 'noreply@example.com'

# Use in app
config = EmailConfig()

if config.email_provider == 'smtp':
    send_via_smtp(config)
elif config.email_provider == 'sendgrid':
    send_via_sendgrid(config)
```

### Logging Configuration

```python
from typing import Literal

class LoggingConfig(Config):
    log_level: Literal['debug', 'info', 'warning', 'error'] = 'info'
    log_format: Literal['json', 'text', 'pretty'] = 'json'
    log_file: str = 'app.log'
    log_max_size_mb: int = 10
    log_backup_count: int = 5
```

## Validation

### Required Fields

```python
class AppConfig(Config):
    # These MUST be in .env or will raise ValidationError
    database_url: str
    jwt_secret: str
    api_key: str
```

If missing:
```
ValidationError: 3 validation errors for AppConfig
database_url
  Field required (type=missing)
jwt_secret
  Field required (type=missing)
api_key
  Field required (type=missing)
```

### Type Validation

```python
class Config(Config):
    port: int = 8000
    timeout: float = 30.0
    debug: bool = False

# .env
PORT=8000           # OK: Valid integer
TIMEOUT=30.5        # OK: Valid float
DEBUG=true          # OK: Valid boolean

PORT=not_a_number   # ValidationError: Invalid integer
TIMEOUT=abc         # ValidationError: Invalid float
DEBUG=yes           # ValidationError: Invalid boolean (only true/false)
```

### Enum Validation

```python
class Config(Config):
    environment: Literal['dev', 'staging', 'prod']

# .env
ENVIRONMENT=dev     # OK
ENVIRONMENT=prod    # OK
ENVIRONMENT=test    # ValidationError: Invalid literal

# Error:
ValidationError: 1 validation error for Config
environment
  Input should be 'dev', 'staging' or 'prod'
```

## Environment Setup

### Development

```bash
# .env.development
DEBUG=true
LOG_LEVEL=debug
DATABASE_URL=sqlite:///dev.db
JWT_SECRET=dev-secret-not-secure
ENABLE_SWAGGER=true
CORS_ORIGINS=*
```

### Staging

```bash
# .env.staging
DEBUG=false
LOG_LEVEL=info
DATABASE_URL=postgresql://staging.db.local/app
JWT_SECRET=staging-secret-key
ENABLE_SWAGGER=true
CORS_ORIGINS=https://staging.example.com
```

### Production

```bash
# .env.production (never commit!)
DEBUG=false
LOG_LEVEL=warning
DATABASE_URL=postgresql://prod.db.aws.com/app
JWT_SECRET=<generate-strong-key>
ENABLE_SWAGGER=false
CORS_ORIGINS=https://app.example.com,https://www.example.com
```

## Best Practices

### 1. Use .env.example as Template

```bash
# Create and commit template
cp .env.example .env

# Add to .gitignore
echo ".env" >> .gitignore
echo ".env.production" >> .gitignore

# Developers copy template
cp .env.example .env
# Then edit with their local values
```

### 2. Define Config Once

```python
# config.py
from sillo.config import Config

class AppConfig(Config):
    database_url: str
    jwt_secret: str
    debug: bool = False

config = AppConfig()

# Use throughout app
# from config import config
```

### 3. Validate at Startup

```python
# main.py
try:
    config = AppConfig()
except ValidationError as e:
    print(f"Invalid configuration: {e}")
    sys.exit(1)

# Proceed only if config is valid
app = SilloApp(debug=config.debug)
```

### 4. Document All Settings

```python
class AppConfig(Config):
    """Application configuration.
    
    Load from .env file. See .env.example for template.
    """
    
    database_url: str = Field(
        ...,
        description="PostgreSQL connection string"
    )
    
    jwt_secret: str = Field(
        ...,
        description="Secret key for JWT signing"
    )
    
    debug: bool = Field(
        default=False,
        description="Enable debug mode (never in production)"
    )
```

### 5. Use Type Hints Everywhere

```python
# Good
db_url: str = config.database_url
port: int = config.port

# Avoid
db_url = config.database_url  # Type not clear
```

### 6. Never Commit Secrets

```bash
# .gitignore
.env
.env.production
.env.*.local

# OK to commit
.env.example
```

## Troubleshooting

### ValidationError: Field required

**Problem:** Required field missing from .env

**Solution:** Add the field to .env file

```python
# config.py
class AppConfig(Config):
    database_url: str  # Required

# .env file must have:
DATABASE_URL=postgresql://localhost/db
```

### ValidationError: Input should be a valid integer

**Problem:** Non-integer value for integer field

```python
PORT=eight  # Wrong

# Fix:
PORT=8000   # Right
```

### Config not loading from .env

**Problem:** The file is not where the search looks, or the variable is
already set in the real environment (which wins).

Check what the search finds, and what the file actually parses to:

```python
from sillo.env import find_env, parse_env

print(find_env())                     # the file being used, or None
print(parse_env(open('.env').read())) # what it parses to
```

The search runs upward from the working directory and stops at the project
root, so a `.env` above the project is deliberately ignored. Name the file
outright when it lives somewhere else:

```python
from pathlib import Path

class AppConfig(Config):
    database_url: str

    class Env:
        env_file = str(Path(__file__).parent / '.env')
```

If the value is stale rather than missing, something exported it before the
process started — `echo $DATABASE_URL` — and the real environment beats the
file by design. Use `load_env(..., override=True)` to reverse that.

### Secrets appear in logs

**Problem:** Sensitive values logged

**Solution:** Config automatically masks common secret fields

```python
# These are automatically masked:
jwt_secret: str        # Appears as ***
api_key: str          # Appears as ***
password: str         # Appears as ***
access_token: str     # Appears as ***
```

## See Also

- [Environment & .env](/guides/environment/) - The file format, precedence, and `sillo.env`
- [Security](/guides/security) - Security best practices
- [Deployment](/guides/start/deployment/) - Deployment configuration
- [Pydantic Docs](https://docs.pydantic.dev/) - Full Pydantic reference
