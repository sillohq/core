---
title: Coming from FastAPI, Django or Flask
description: Translation tables and side-by-side code for developers arriving from FastAPI, Django or Flask — what transfers unchanged, what has a different name, and which habits do not survive the move.
head:
- tag: meta
  attrs:
    property: og:title
    content: "Sillo for FastAPI, Django and Flask developers"
- tag: meta
  attrs:
    property: og:description
    content: What transfers unchanged, what is renamed, and which habits do not survive the move.
---

#  Coming from FastAPI, Django or Flask

Almost everything you know transfers. This page is about the small part that
does not, so you can stop looking for it.

Pick the section for where you are coming from; the last two sections apply to
everybody.

##  Coming from FastAPI

The request layer will feel familiar immediately: typed parameters, Pydantic
validation, `async` handlers, generated OpenAPI. The differences are mostly
naming, plus one real change — the handler signature.

| FastAPI | Sillo |
|---|---|
| `FastAPI()` | `SilloApp()` |
| `APIRouter(prefix="/v1")` | `Router(prefix="/v1")` |
| `app.include_router(r)` | `app.mount_router(r)` — the prefix lives on the `Router` |
| `def f(item: Item)` for a body | `@app.post(..., request_model=Item)` |
| `response_model=Model` | `response_model=Model` (plus `response_model_many=True` for lists) |
| `Depends(fn)` | `Depend(fn)` |
| `Query`, `Path`, `Header`, `Cookie`, `Form`, `File` | the same names, imported from `sillo` |
| `Request` as a parameter | `request` and `response`, always the first two parameters |
| `JSONResponse({...}, status_code=201)` | `response.json({...}, status_code=201)` |
| `HTTPException(status_code=404, detail=...)` | `HTTPException(detail=..., status=404)` from `sillo.exceptions` |
| `@app.on_event("startup")` / lifespan | `@app.on_startup` and `@app.on_shutdown` |
| `Security(...)`, `OAuth2PasswordBearer` | `auth=useAuth(...)` on the route |
| `BackgroundTasks` | [background work, queues and a scheduler](/v0.x/guides/work/) |
| `TestClient` | `TestClient` / `AsyncTestClient` from `sillo.testclient` |
| SQLAlchemy, Alembic, `python-jose`, `passlib`… | first-party: [Record](/v0.x/orm/), migrations, [JWT](/v0.x/guides/jwt-auth/), [hashing](/v0.x/guides/hashing/) |

The same endpoint in both:

```python
# FastAPI
from fastapi import FastAPI, Depends
from pydantic import BaseModel

app = FastAPI()

class CreateProject(BaseModel):
    name: str

@app.post("/teams/{team_id}/projects", status_code=201)
async def create(team_id: int, body: CreateProject, db=Depends(get_db)):
    return {"team_id": team_id, "project": body.model_dump()}
```

```python
# Sillo
from sillo import SilloApp, Depend
from pydantic import BaseModel

app = SilloApp()

class CreateProject(BaseModel):
    name: str

@app.post("/teams/{team_id}/projects", request_model=CreateProject)
async def create(request, response, team_id: int, project: CreateProject, db=Depend(get_db)):
    return response.json(
        {"team_id": team_id, "project": project.model_dump()},
        status_code=201,
    )
```

Two things to notice. The body model is declared on the decorator rather than
inferred from a parameter's type — Sillo does not guess which parameter is the
body. And `request` and `response` come first, always, rather than being
injected by type annotation.

:::note
This is the 0.x signature. In 1.0 the two collapse into a single
`ctx: HttpContext` and returning a `dict` is enough — see
[what changes in 1.0](/v0.x/guides/faq/#what-changes-in-10).
:::

**Where to go next:** [Routing](/v0.x/guides/routing/) →
[Handlers](/v0.x/guides/handlers/) → [Validation](/v0.x/guides/validation/).
Roughly an hour, and you will be productive.

##  Coming from Django

The ORM will feel like home — Tortoise borrows Django's query API on purpose.
The application layer will not: there is no settings module, no `urls.py`, no
app registry, and handlers are `async`.

| Django | Sillo |
|---|---|
| `settings.py` | a [`Config`](/v0.x/guides/configuration/) subclass — a Pydantic model, validated at startup |
| `os.environ` / `django-environ` | [`.env` loading](/v0.x/guides/environment/), typed through the same `Config` |
| `urls.py`, `path()`, `include()` | route decorators, and [`Router`](/v0.x/guides/routers-and-subapps/) for grouping |
| `manage.py` | the [`sillo` CLI](/v0.x/cli/) |
| `makemigrations` / `migrate` | `sillo db:make` / `sillo db:migrate` (plus `db:plan`, `db:rollback`, `db:status`) |
| `models.Model` | `sillo.record.Model` |
| `Model.objects.filter(...)` | `Model.filter(...)` — no manager in between |
| `Q`, `F`, `name__icontains` | `Q`, `F`, `name__icontains` — unchanged |
| `select_related` / `prefetch_related` | [eager loading](/v0.x/orm/eager-loading/) |
| `MIDDLEWARE` list | `app.use(fn)` and `BaseMiddleware` |
| `django.contrib.auth` | [first-party auth](/v0.x/guides/authentication/), users, permissions and groups |
| `@login_required`, `@permission_required` | `auth=useAuth(...)` on the route |
| `django.contrib.admin` | the [built-in admin](/v0.x/orm/admin/) (it becomes [`warder`](/packages/warder/) in 1.0) |
| Django templates | [Jinja templating](/v0.x/guides/templating/), or [Inertia](/v0.x/guides/inertia/), or JSON |
| DRF serializers | Pydantic models |
| Celery + beat | [queues, jobs and the scheduler](/v0.x/guides/work/), first-party |
| Django Channels | [WebSockets](/v0.x/guides/websockets/), with [channels and groups](/v0.x/guides/websockets/channels/) built in |
| `startapp` | nothing — organise modules however you like |

The largest adjustment is not the ORM, it is that **there is no project
skeleton the framework insists on**. `sillo-start` gives you a working
application to copy, but nothing scans for an `apps.py` or requires a
particular directory name. See [Project Structure](/v0.x/guides/start/structure/)
for the layout the starter uses and why.

The second adjustment is async. Django's ORM has a sync core with async
wrappers; Record is async all the way down, so every query is awaited:

```python
# Django
posts = Post.objects.filter(author=user).select_related("author")[:10]

# Sillo
posts = await Post.filter(author=user).select_related("author").limit(10)
```

**Where to go next:** [Configuration](/v0.x/guides/configuration/) →
[Routing](/v0.x/guides/routing/) → [the ORM manual](/v0.x/orm/). The ORM is the
part you will read fastest.

##  Coming from Flask

You are trading a small core plus extensions for a large core. The routing will
feel similar; the request object is the main day-one difference.

| Flask | Sillo |
|---|---|
| `Flask(__name__)` | `SilloApp()` |
| `@app.route("/", methods=["GET"])` | `@app.get("/")` |
| `Blueprint` | [`Router`](/v0.x/guides/routers-and-subapps/) |
| the `request` global | `request`, passed to the handler |
| `g` | `request.state` |
| `jsonify({...})` | `response.json({...})` |
| `abort(404)` | `raise HTTPException(detail="...", status=404)` |
| `@app.before_request` | [middleware](/v0.x/guides/middleware/) via `app.use` |
| `app.config` | a [`Config`](/v0.x/guides/configuration/) model |
| Flask-SQLAlchemy + Flask-Migrate | [Record](/v0.x/orm/) and `sillo db:*` |
| Flask-Login | [authentication and sessions](/v0.x/guides/authentication/) |
| Flask-Caching | [caching](/v0.x/guides/cache/) |
| Flask-WTF / marshmallow | Pydantic and `request_model=` |
| Celery | [queues and jobs](/v0.x/guides/work/) |
| Gunicorn + `wsgi.py` | uvicorn (or granian) + an ASGI app |

The important one is the request global. Flask binds `request` to the current
context so any function deep in your call stack can reach it; Sillo passes it
explicitly as a parameter and does not provide a global equivalent. Functions
that need request data take it as an argument, or receive it through
[dependency injection](/v0.x/guides/dependency-injection/). This is more typing
and considerably less debugging.

**Where to go next:** [Routing](/v0.x/guides/routing/) →
[Request Information](/v0.x/guides/request-info/) →
[Sending Responses](/v0.x/guides/sending-responses/).

##  Habits that do not transfer

Regardless of where you are arriving from.

**Synchronous I/O in a handler.** `requests.get(...)`, a sync database driver,
`time.sleep`, a blocking file read of any size — each one stops the event loop
and every concurrent request behind it. This is the single most common
production surprise. [Concurrency](/v0.x/guides/concurrency/) covers the thread
pool and when to reach for it.

**Reaching for the request from anywhere.** There is no thread-local `request`,
no `current_app`, no `g` visible from an arbitrary module. Pass the `request`
object, or declare a dependency.

**Import-time side effects.** Registering things by importing a module — Django
apps, Flask extensions bound at import — is not how anything here works.
Routes, middleware, startup hooks and jobs are all registered by calling
something on the app.

**Config as a module of globals.** `Config` is a validated Pydantic model. A
missing or malformed value fails at startup with a message naming the field,
rather than at 3am with an `AttributeError` in a worker.

**Assuming migrations are magic.** `db:make` writes a migration from your model
changes and `db:plan` shows you what it would run. Read the plan. See
[Migrations](/v0.x/orm/migrations/).

##  What to read next

You do not need the whole manual. Pick the shape of what you are building:

- **A JSON API** — [Routing](/v0.x/guides/routing/) →
  [Handlers](/v0.x/guides/handlers/) →
  [Validation](/v0.x/guides/validation/) →
  [Error Handling](/v0.x/guides/error-handling/)
- **Something with users** — [Authentication](/v0.x/guides/authentication/) →
  [Protecting Routes](/v0.x/guides/protecting-routes/) →
  [Sessions](/v0.x/guides/sessions/) → [CSRF](/v0.x/guides/csrf/)
- **Something with a database** — [the ORM manual](/v0.x/orm/), start at
  [Setup](/v0.x/orm/setup/)
- **Anything going to production** —
  [Security](/v0.x/guides/security/) →
  [Startup & Shutdown](/v0.x/guides/startups-and-shutdowns/) →
  [Concurrency](/v0.x/guides/concurrency/)

And [What's in the Box](/v0.x/guides/ecosystem/) if you want to know what you
just installed before you start using it.
