# Configuration Management with Sillo

Type-safe configuration management using Pydantic and .env files.

## Overview

Sillo's configuration system provides:

- **Type safety** - Full type hints and IDE autocomplete
- **Validation** - Pydantic validates all values on load
- **Environment-specific** - Different configs per environment
- **Secret masking** - Automatically hides secrets in repr
- **.env file support** - Read by sillo itself; `python-dotenv` is not needed
- **Required vs optional** - Clear which fields are required
- **Smart defaults** - Default values for optional fields

## Quick Start

### 1. Define Configuration

```python
from sillo.config import Config, Field
from typing import Literal

class AppConfig(Config):
    # Required fields
    database_url: str
    jwt_secret: str
    
    # Optional fields with defaults
    debug: bool = False
    log_level: Literal['debug', 'info', 'warning', 'error'] = 'info'
    port: int = 8000

config = AppConfig()   # .env is found and read automatically
```

### 2. Create .env File

```bash
# .env
DATABASE_URL=postgresql://localhost/mydb
JWT_SECRET=super-secret-key
DEBUG=true
LOG_LEVEL=debug
PORT=8000
```

### 3. Use in Application

```python
from sillo import SilloApp

app = SilloApp(debug=config.debug, title="My API")

@app.get("/health")
async def health(request, response):
    return response.json({"status": "ok", "debug": config.debug})
```

## Files

- `01_basic_config.py` - Simple configuration example
- `02_web_app.py` - Full Sillo app with configuration
- `.env.example` - Template for .env file
- `.env.development` - Development environment settings
- `.env.production` - Production environment settings

## Usage Examples

### Basic Configuration

```bash
uv run python examples/config/01_basic_config.py
```

Output:
```
Configuration loaded successfully!

Database: postgresql://localhost/mydb
Debug Mode: true
Log Level: debug
Server: 127.0.0.1:8000
JWT Secret: ***

Full config:
<AppConfig {'debug': True, 'log_level': 'debug', 'port': 8000, 'host': '127.0.0.1', 'database_url': 'postgresql://localhost/mydb', 'jwt_secret': '***'}>
```

### Web Application

```bash
uv run uvicorn examples/config/02_web_app:app --reload
```

Then access:
- http://localhost:8000/ - Home endpoint
- http://localhost:8000/config - View all config
- http://localhost:8000/status - Health check
- http://localhost:8000/settings - Specific settings

## Configuration Structure

### Required vs Optional

```python
class Config(Config):
    # Required - must be in .env or will raise ValidationError
    database_url: str
    jwt_secret: str
    
    # Optional - has default value
    debug: bool = False
    port: int = 8000
```

### Type Validation

All types are validated on load:

```python
port: int = 8000              # Converted to int
debug: bool = False           # Converted to bool
timeout: float = 30.0         # Converted to float
log_level: Literal['debug', 'info', 'warning', 'error'] = 'info'  # Must be one of these
```

### Environment Variables

Use `Field()` to map environment variables:

```python
from sillo.config import Config, Field

class AppConfig(Config):
    # Reads DB_URL instead of DATABASE_URL
    database_url: str = Field(..., alias='db_url')

    # Custom description for validation errors
    port: int = Field(default=8000, description='Server port')
```

Or prefix a whole class, so one .env can hold several subsystems:

```python
class DatabaseConfig(Config):
    url: str              # DATABASE_URL
    pool_size: int = 10   # DATABASE_POOL_SIZE

    class Env:
        env_prefix = 'DATABASE_'
```

## Environment-Specific Configs

### Development

```bash
cp .env.development .env
uv run uvicorn app:app --reload
```

Features:
- SQLite database
- Debug mode enabled
- Full logging
- Swagger UI enabled
- CORS from localhost

### Production

```bash
cp .env.production .env
uv run uvicorn app:app
```

Features:
- PostgreSQL database
- Debug mode disabled
- Minimal logging
- Swagger UI disabled
- Restricted CORS

## Best Practices

### 1. Use .env.example as Template

```bash
# Copy template
cp .env.example .env

# Edit with your values
# Never commit .env to git
```

### 2. Define All Config at Startup

```python
# app.py
from sillo.config import Config

class AppConfig(Config):
    database_url: str
    jwt_secret: str
    debug: bool = False

config = AppConfig()  # Loads from .env

# Use throughout app
app = SilloApp(debug=config.debug)
```

### 3. Use Type Hints

```python
# Proper typing
debug: bool = config.debug
port: int = config.port
level: Literal['debug', 'info'] = config.log_level
```

### 4. Mask Secrets

```python
# Config automatically masks secrets
config = AppConfig()
print(config)  # JWT_SECRET shows as ***
```

### 5. Validate Required Values

```python
# Validation happens on load
try:
    config = AppConfig()
except ValidationError as e:
    print(f"Missing config: {e}")
    exit(1)
```

## Common Patterns

### Database URL Based on Environment

```python
class Config(Config):
    environment: Literal['development', 'staging', 'production']
    
    @property
    def database_url(self) -> str:
        if self.environment == 'development':
            return 'sqlite:///dev.db'
        elif self.environment == 'staging':
            return 'postgresql://staging-db/db'
        else:
            return os.getenv('DATABASE_URL')
```

### Feature Flags

```python
class Config(Config):
    enable_payments: bool = False
    enable_notifications: bool = False
    enable_analytics: bool = False

# Use in app
if config.enable_payments:
    setup_stripe()

if config.enable_notifications:
    setup_email()
```

### Database Credentials

```python
class Config(Config):
    database_host: str
    database_port: int = 5432
    database_user: str
    database_password: str
    database_name: str
    
    @property
    def database_url(self) -> str:
        return (
            f"postgresql://"
            f"{self.database_user}:{self.database_password}"
            f"@{self.database_host}:{self.database_port}"
            f"/{self.database_name}"
        )
```

### Multi-Environment Setup

From the outside, so the code does not have to know:

```bash
SILLO_ENV_FILE=.env.production uv run uvicorn app:app
```

Or in the class:

```python
import os

class AppConfig(Config):
    database_url: str

    class Env:
        env_file = f".env.{os.getenv('ENVIRONMENT', 'development')}"
```

## Troubleshooting

### ValidationError: Field Required

```
ValidationError: 1 validation error for AppConfig
database_url
  Field required (type=missing)
```

**Fix:** Add missing field to .env file

```bash
DATABASE_URL=postgresql://localhost/db
```

### ValidationError: Value is not a valid integer

```
ValidationError: 1 validation error for AppConfig
port
  Input should be a valid integer (type=int_parsing)
```

**Fix:** Ensure value is valid for type

```bash
# Wrong
PORT=eight-thousand

# Right
PORT=8000
```

### Secret appears in logs

**Solution:** Config automatically masks known secret fields

```python
# These fields are automatically masked:
# secret, key, password, token, apikey, api_key, auth, credential, private

jwt_secret: str  # Appears as *** in repr
database_password: str  # Appears as *** in repr
```

## See Also

- [Environment & .env](https://docs.sillo.build/guides/environment/) - .env file format, precedence, `sillo.env`
- [Pydantic Documentation](https://docs.pydantic.dev/) - Full Pydantic reference
- [Sillo Authentication](/guides/authentication) - Using config for auth
- [Sillo Users](/guides/users) - Integrating with user system
