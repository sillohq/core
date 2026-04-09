"""
Example application demonstrating Nexios lifespan handling with Granian.

This example shows:
1. Regular startup/shutdown handlers
2. Custom lifespan context manager
3. Error handling

Run with:
    granian --interface asgi --workers 2 lifespan_example:app
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from nexios import NexiosApp
from nexios.http.request import Request
from nexios.http.response import Response

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("lifespan-example")


# Simulate database connection
class Database:
    def __init__(self):
        self.connected = False
        self.data = {}

    async def connect(self):
        logger.info("Connecting to database...")
        await asyncio.sleep(0.5)  # Simulate connection time
        self.connected = True
        logger.info("Database connected")

    async def disconnect(self):
        if self.connected:
            logger.info("Disconnecting from database...")
            await asyncio.sleep(0.3)  # Simulate disconnection time
            self.connected = False
            logger.info("Database disconnected")

    async def get(self, key):
        if not self.connected:
            raise RuntimeError("Database not connected")
        return self.data.get(key)

    async def set(self, key, value):
        if not self.connected:
            raise RuntimeError("Database not connected")
        self.data[key] = value


# Create a global database instance
db = Database()


# Custom lifespan context manager
@asynccontextmanager
async def lifespan_context(app):
    """
    Custom lifespan context manager that handles both startup and shutdown.

    This demonstrates how to use a custom lifespan with proper cleanup handling.
    """
    logger.info("Application startup: Custom lifespan context manager")

    # Startup phase
    try:
        # Initialize resources
        await db.connect()

        # Store the database on the app for access in routes
        app.db = db

        # Set application state
        app.state = {"initialized_at": asyncio.get_event_loop().time()}

        logger.info("Application ready")
        yield
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        # Make sure to clean up resources even if startup fails
        if db.connected:
            await db.disconnect()
        raise
    finally:
        # Shutdown phase - this runs regardless of how the context is exited
        logger.info("Application shutdown: Custom lifespan context manager")
        await db.disconnect()
        logger.info("Cleanup complete")


# Create application instances to demonstrate different approaches

# 1. Application with regular startup/shutdown handlers
regular_app = NexiosApp(title="Regular Handlers Example")


@regular_app.on_startup()
async def startup_handler1():
    """First startup handler"""
    logger.info("Regular startup handler 1 running")
    await db.connect()


@regular_app.on_startup()
async def startup_handler2():
    """Second startup handler that depends on the first"""
    logger.info("Regular startup handler 2 running")
    await db.set("startup_key", "initialized")


@regular_app.on_shutdown()
async def shutdown_handler1():
    """First shutdown handler"""
    logger.info("Regular shutdown handler 1 running")
    await db.set("shutdown_key", "cleaning_up")


@regular_app.on_shutdown()
async def shutdown_handler2():
    """Second shutdown handler that should run even if the first fails"""
    logger.info("Regular shutdown handler 2 running")
    await db.disconnect()


# 2. Application with custom lifespan context manager
custom_app = NexiosApp(title="Custom Lifespan Example", lifespan=lifespan_context)


# 3. Application demonstrating error handling
error_app = NexiosApp(title="Error Handling Example")


@error_app.on_startup()
async def failing_startup():
    """Startup handler that intentionally raises an exception"""
    logger.info("Running startup handler that will fail")
    raise ValueError("Intentional startup error for demonstration")


@error_app.on_shutdown()
async def error_cleanup():
    """Shutdown handler that should run despite startup failure"""
    logger.info("Running shutdown handler after startup error")
    if db.connected:
        await db.disconnect()


# Main application that combines regular handlers and custom lifespan
app = NexiosApp(title="Nexios Lifespan Demo", lifespan=lifespan_context)


# Add some regular handlers too (these won't run when custom lifespan is used)
@app.on_startup()
async def additional_startup():
    logger.info("Additional startup handler (won't run with custom lifespan)")


@app.on_shutdown()
async def additional_shutdown():
    logger.info("Additional shutdown handler (won't run with custom lifespan)")


# Example routes
@app.get("/")
async def home(request: Request, response: Response):
    """Simple endpoint to verify the app is running"""
    return response.json({"status": "ok", "message": "Nexios lifespan demo is running"})


@app.get("/db-status")
async def db_status(request: Request, response: Response):
    """Endpoint that uses the database connection"""
    return response.json(
        {
            "database_connected": app.db.connected,
            "startup_time": app.state.get("initialized_at", None),
        }
    )


@app.get("/error")
async def trigger_error(request: Request, response: Response):
    """Endpoint that raises an exception to test error handling"""
    logger.info("Triggering a test error")
    raise ValueError("This is a test error to demonstrate exception handling")


if __name__ == "__main__":
    # Instructions for running with different servers
    print("""
Nexios Lifespan Demo Application
--------------------------------

Run with Granian:
    granian --interface asgi --workers 2 lifespan_example:app

Run with Uvicorn:
    uvicorn lifespan_example:app

Run with Hypercorn:
    hypercorn lifespan_example:app
    """)

    # Default to uvicorn if run directly
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
