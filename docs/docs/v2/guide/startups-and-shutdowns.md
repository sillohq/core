---
title: Startup And Shutdowns ⏻
description: In ASGI (Asynchronous Server Gateway Interface), startup and shutdown refer to the lifecycle events of an application. These events allow you to perform initialization and cleanup tasks when the application starts up or shuts down.
head:
  - - meta
    - property: og:title
      content: Startup And Shutdowns ⏻
  - - meta
    - property: og:description
      content: In ASGI (Asynchronous Server Gateway Interface), startup and shutdown refer to the lifecycle events of an application. These events allow you to perform initialization and cleanup tasks when the application starts up or shuts down.
---
# Startup And Shutdowns 
In ASGI (Asynchronous Server Gateway Interface), startup and shutdown refer to the lifecycle events of an application. These events allow you to perform initialization and cleanup tasks when the application starts up or shuts down.


The Nexios framework provides a simple way to run code during startup and shutdown. The ``on_startup`` and ``on_shutdown`` functions are the two main functions that are used to do this.

## Startup

The ``on_startup`` function is used to run code when the application is starting up. It can be used to setup the database connection, setup the routes, and other things.


```python{3}
from nexios import NexioApp
app = NexioApp()
@app.on_startup
async def startup():
    print("Application starting up...")
    # Do something when the application starts up
```

## Shutdown

The ``on_shutdown`` function is used to run code when the application is shutting down. It can be used to close database connections, free resources, and other things.


```python{3}
from nexios import NexioApp
app = NexioApp()
@app.on_shutdown
async def shutdown():
    print("Application shutting down...")
    # Do something when the application shuts down
```

::: info ℹ️Info

if an exception occurs during startup, the ASGI server may fail to start entirely.

:::

## Lifespan Async Context Manager

Nexios also supports using an asynchronous context manager to handle both startup and shutdown events in a single construct. This is achieved by defining a lifespan function and passing it to the application via the `lifespan` argument. This approach encapsulates initialization and cleanup logic in one place.



```python
from nexios import NexioApp
from contextlib import asynccontextmanager


@asynccontextmanager
async def app_lifespan(app):
    # Application startup logic
    print("Application started successfully!")
    yield
    # Application shutdown logic
    print("Application shutting down...")

app = NexioApp(lifespan=app_lifespan)
```

::: tip 💡Tip

You cannot use ``on_startup`` and ``on_shutdown`` together with ``lifespan`` But You can use this trick 

```py
from nexios import NexioApp
from contextlib import asynccontextmanager


@asynccontextmanager
async def app_lifespan(app):
    # Application startup logic

    await app._startup()
    print("Application started successfully!")
    yield
    # Application shutdown logic
    await app._shutdown()
    print("Application shutting down...")

app = NexioApp(lifespan=app_lifespan)

```
:::