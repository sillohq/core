"""Web app with configuration example.

Run with:
    uv run uvicorn examples/config/02_web_app:app --reload
"""

from sillo import silloApp, Query
from sillo.config import Config, Field
from sillo.objects.http import Request, Response
from typing import Literal, Optional


class AppConfig(Config):
    """Application configuration."""

    # Core settings
    app_name: str = "Config Example API"
    environment: Literal['development', 'staging', 'production'] = 'development'
    debug: bool = False

    # Server settings
    host: str = '127.0.0.1'
    port: int = 8000

    # Database
    database_url: str
    database_pool_size: int = 10

    # Security
    jwt_secret: str
    jwt_algorithm: str = 'HS256'
    jwt_expiration_hours: int = 24

    # Logging
    log_level: Literal['debug', 'info', 'warning', 'error'] = 'info'

    # Optional features
    enable_swagger: bool = True
    enable_cors: bool = True
    cors_origins: str = '*'

    class Config:
        env_file = '.env'
        case_sensitive = False


# Load config
config = AppConfig()

# Create app with config
app = silloApp(
    title=config.app_name,
    debug=config.debug,
)


@app.get('/')
async def home(request: Request, response: Response):
    """Home endpoint."""
    return response.json({
        "app": config.app_name,
        "environment": config.environment,
        "debug": config.debug,
    })


@app.get('/config')
async def get_config(request: Request, response: Response):
    """Show current configuration (non-secret fields)."""
    return response.json({
        "app_name": config.app_name,
        "environment": config.environment,
        "debug": config.debug,
        "host": config.host,
        "port": config.port,
        "log_level": config.log_level,
        "enable_swagger": config.enable_swagger,
        "enable_cors": config.enable_cors,
        "database_pool_size": config.database_pool_size,
        "jwt_algorithm": config.jwt_algorithm,
        "jwt_expiration_hours": config.jwt_expiration_hours,
    })


@app.get('/status')
async def status(request: Request, response: Response):
    """Health check with config info."""
    return response.json({
        "status": "healthy",
        "app": config.app_name,
        "env": config.environment,
    })


@app.get('/settings')
async def settings(request: Request, response: Response):
    """Get specific settings."""
    return response.json({
        "debug_mode": config.debug,
        "log_level": config.log_level,
        "database": {
            "url": config.database_url[:20] + "...",  # Hide full URL
            "pool_size": config.database_pool_size,
        },
        "jwt": {
            "algorithm": config.jwt_algorithm,
            "expiration_hours": config.jwt_expiration_hours,
        },
        "cors": {
            "enabled": config.enable_cors,
            "origins": config.cors_origins,
        },
    })


@app.post('/api/greet')
async def greet(
    request: Request,
    response: Response,
    name: str = Query(...),
):
    """Greeting endpoint with config-based behavior."""

    message = f"Hello {name}!"

    # Behavior changes based on config
    if config.debug:
        message += " (DEBUG MODE)"

    if config.environment == 'development':
        message += f" [Running on {config.environment}]"

    return response.json({
        "greeting": message,
        "app": config.app_name,
    })


if __name__ == "__main__":
    import uvicorn

    print(f"Starting {config.app_name}...")
    print(f"Environment: {config.environment}")
    print(f"Debug: {config.debug}")
    print(f"Server: {config.host}:{config.port}")
    print()

    uvicorn.run(
        app,
        host=config.host,
        port=config.port,
        reload=config.debug,
        log_level=config.log_level.lower(),
    )
