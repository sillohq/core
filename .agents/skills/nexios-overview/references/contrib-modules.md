# Nexios Contrib Modules

Use this reference when the request is about `nexios-contrib` or related integrations rather than the core framework alone.

## Table of Contents

1. [Redis](#redis)
2. [Background Tasks](#background-tasks)
3. [Mail](#mail)
4. [Tortoise ORM](#tortoise-orm)
5. [How To Teach Contrib Modules](#how-to-teach-contrib-modules)

## Redis

Basic setup:

```python
from nexios import NexiosApp
from nexios_contrib.redis import init_redis

app = NexiosApp()
init_redis(app)
```

Dependency injection pattern:

```python
from nexios import Depend
from nexios_contrib.redis import get_redis

@app.get("/user/{user_id}")
async def get_user(request, response, user_id: str, redis = Depend(get_redis)):
    cached_user = await redis.json_get(f"user:{user_id}")
    return response.json({"user": cached_user})
```

Other documented Redis patterns include:

- `RedisDepend()`
- `RedisOperationDepend(...)`
- `RedisKeyDepend(...)`
- `RedisCacheDepend(...)`

Teach Redis as the caching and data-store integration layer, especially when the user wants async caching or shared state.

## Background Tasks

Basic setup:

```python
from nexios import NexiosApp
from nexios_contrib.tasks import setup_tasks, create_task

app = NexiosApp()
task_manager = setup_tasks(app)
```

Creating a task from a route:

```python
async def process_data(data: dict) -> dict:
    return {"status": "completed", "data": data}

@app.post("/process")
async def start_processing(request, response):
    data = await request.json
    task = await create_task(func=process_data, data=data, name="data_processing")
    return response.json({"task_id": task.id})
```

Dependency injection variant:

```python
from nexios_contrib.tasks import TaskDependency

@app.post("/process-with-deps")
async def process_with_deps(request, response, task_dep: TaskDependency = TaskDependency()):
    data = await request.json
    task = await task_dep.create(func=process_data, data=data, name="data_processing")
    return response.json({"task_id": task.id})
```

## Mail

Application setup:

```python
from nexios import NexiosApp
from nexios_contrib.mail import setup_mail, MailConfig

app = NexiosApp()
mail_client = setup_mail(app, config=MailConfig(
    smtp_host="smtp.gmail.com",
    smtp_port=587,
    smtp_username="your-email@gmail.com",
    smtp_password="your-app-password",
    use_tls=True
))
```

Direct send example:

```python
result = await mail_client.send_email(
    to="recipient@example.com",
    subject="Hello World",
    body="Plain text",
    html_body="<h1>Hello World</h1>"
)
```

Teach mail as the email delivery layer, often paired with background tasks or events.

## Tortoise ORM

Basic initialization:

```python
from nexios import NexiosApp
from nexios_contrib.tortoise import init_tortoise

app = NexiosApp()

init_tortoise(
    app,
    db_url="sqlite://db.sqlite3",
    modules={"models": ["app.models"]},
    generate_schemas=True
)
```

Handler example:

```python
@app.get("/users")
async def list_users(request, response):
    users = await User.all()
    return response.json([
        {"id": user.id, "name": user.name, "email": user.email}
        for user in users
    ])
```

Teach this integration as the ORM bridge for async model-based persistence.

## How To Teach Contrib Modules

- Start with what the module adds to core Nexios
- Show the one-line or one-function setup
- Give one practical route example
- Mention whether DI support exists
- Keep core Nexios concepts separate from contrib-specific helpers
