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
| `Request` as a parameter | `ctx: HttpContext`, always the first parameter |
| `JSONResponse({...}, status_code=201)` | return a `dict`, or `created({...})` |
| `HTTPException(status_code=404, detail=...)` | `HTTPException(detail=..., status=404)` from `sillo.exceptions` |
| `@app.on_event("startup")` / lifespan | `@app.on_startup` and `@app.on_shutdown` |
| `Security(...)`, `OAuth2PasswordBearer` | `auth=useAuth(...)` on the route |
| `BackgroundTasks` | [background work, queues and a scheduler](/v1.0/guides/work/) |
| `TestClient` | `TestClient` / `AsyncTestClient` from `sillo.testclient` |
| SQLAlchemy, Alembic, `python-jose`, `passlib`… | first-party: [Record](/v1.0/orm/), migrations, [JWT](/v1.0/guides/jwt-auth/), [hashing](/v1.0/guides/hashing/) |

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
from sillo import SilloApp, HttpContext, Depend, created
from pydantic import BaseModel

app = SilloApp()

class CreateProject(BaseModel):
    name: str

@app.post("/teams/{team_id}/projects", request_model=CreateProject)
async def create(ctx: HttpContext, team_id: int, project: CreateProject, db=Depend(get_db)):
    return created({"team_id": team_id, "project": project.model_dump()})
```

Two things to notice. The body model is declared on the decorator rather than
inferred from a parameter's type — Sillo does not guess which parameter is the
body. And `ctx` comes first: one object carrying the request, the response
builder, the authenticated user and request-scoped state, rather than several
injectable parameters.

:::note
`ctx: HttpContext` is the 1.0 signature. In 0.x a handler takes `request` and
`response` separately and returns `response.json(...)`. If you are reading
0.x code, that is why it looks different.
:::

**Where to go next:** [Routing](/v1.0/guides/routing/) →
[Handlers](/v1.0/guides/handlers/) → [Validation](/v1.0/guides/validation/).
Roughly an hour, and you will be productive.

##  Coming from Django

The ORM will feel like home — Tortoise borrows Django's query API on purpose.
The application layer will not: there is no settings module, no `urls.py`, no
app registry, and handlers are `async`.

| Django | Sillo |
|---|---|
| `settings.py` | a [`Config`](/v1.0/guides/configuration/) subclass — a Pydantic model, validated at startup |
| `os.environ` / `django-environ` | [`.env` loading](/v1.0/guides/environment/), typed through the same `Config` |
| `urls.py`, `path()`, `include()` | route decorators, and [`Router`](/v1.0/guides/routers-and-subapps/) for grouping |
| `manage.py` | the [`sillo` CLI](/v1.0/cli/) |
| `makemigrations` / `migrate` | `sillo db:make` / `sillo db:migrate` (plus `db:plan`, `db:rollback`, `db:status`) |
| `models.Model` | `sillo.record.Model` |
| `Model.objects.filter(...)` | `Model.filter(...)` — no manager in between |
| `Q`, `F`, `name__icontains` | `Q`, `F`, `name__icontains` — unchanged |
| `select_related` / `prefetch_related` | [eager loading](/v1.0/orm/eager-loading/) |
| `MIDDLEWARE` list | `app.use(fn)` and `BaseMiddleware` |
| `django.contrib.auth` | [first-party auth](/v1.0/guides/authentication/), users, permissions and groups |
| `@login_required`, `@permission_required` | `auth=useAuth(...)` on the route |
| `django.contrib.admin` | [`warder`](/packages/warder/), a separate install |
| Django templates | none in 1.0 — return JSON, or use [Inertia](/v1.0/guides/inertia/) |
| DRF serializers | Pydantic models |
| Celery + beat | [queues, jobs and the scheduler](/v1.0/guides/work/), first-party |
| Django Channels | [WebSockets](/v1.0/guides/websockets/), and [`sillo-wire`](/packages/wire/) for rooms and presence |
| `startapp` | nothing — organise modules however you like |

The largest adjustment is not the ORM, it is that **there is no project
skeleton the framework insists on**. `sillo-start` gives you a working
application to copy, but nothing scans for an `apps.py` or requires a
particular directory name. See [Project Structure](/v1.0/guides/start/structure/)
for the layout the starter uses and why.

The second adjustment is async. Django's ORM has a sync core with async
wrappers; Record is async all the way down, so every query is awaited:

```python
# Django
posts = Post.objects.filter(author=user).select_related("author")[:10]

# Sillo
posts = await Post.filter(author=user).select_related("author").limit(10)
```

**Where to go next:** [Configuration](/v1.0/guides/configuration/) →
[Routing](/v1.0/guides/routing/) → [the ORM manual](/v1.0/orm/). The ORM is the
part you will read fastest.

##  Coming from Flask

You are trading a small core plus extensions for a large core. The routing will
feel similar; the request object is the main day-one difference.

| Flask | Sillo |
|---|---|
| `Flask(__name__)` | `SilloApp()` |
| `@app.route("/", methods=["GET"])` | `@app.get("/")` |
| `Blueprint` | [`Router`](/v1.0/guides/routers-and-subapps/) |
| the `request` global | `ctx`, passed to the handler |
| `g` | `ctx.state` |
| `jsonify({...})` | return a `dict` |
| `abort(404)` | `raise HTTPException(detail="...", status=404)` |
| `@app.before_request` | [middleware](/v1.0/guides/middleware/) via `app.use` |
| `app.config` | a [`Config`](/v1.0/guides/configuration/) model |
| Flask-SQLAlchemy + Flask-Migrate | [Record](/v1.0/orm/) and `sillo db:*` |
| Flask-Login | [authentication and sessions](/v1.0/guides/authentication/) |
| Flask-Caching | [caching](/v1.0/guides/cache/) |
| Flask-WTF / marshmallow | Pydantic and `request_model=` |
| Celery | [queues and jobs](/v1.0/guides/work/) |
| Gunicorn + `wsgi.py` | uvicorn (or granian) + an ASGI app |

The important one is the request global. Flask binds `request` to the current
context so any function deep in your call stack can reach it; Sillo passes
`ctx` explicitly and does not provide a global equivalent. Functions that need
request data take it as an argument, or receive it through
[dependency injection](/v1.0/guides/dependency-injection/). This is more typing
and considerably less debugging.

**Where to go next:** [Routing](/v1.0/guides/routing/) →
[Request Information](/v1.0/guides/request-info/) →
[Sending Responses](/v1.0/guides/sending-responses/).

##  Habits that do not transfer

Regardless of where you are arriving from.

**Synchronous I/O in a handler.** `requests.get(...)`, a sync database driver,
`time.sleep`, a blocking file read of any size — each one stops the event loop
and every concurrent request behind it. This is the single most common
production surprise. [Concurrency](/v1.0/guides/concurrency/) covers the thread
pool and when to reach for it.

**Reaching for the request from anywhere.** There is no thread-local `request`,
no `current_app`, no `g` visible from an arbitrary module. Pass `ctx`, or
declare a dependency.

**Import-time side effects.** Registering things by importing a module — Django
apps, Flask extensions bound at import — is not how anything here works.
Routes, middleware, startup hooks and jobs are all registered by calling
something on the app.

**Config as a module of globals.** `Config` is a validated Pydantic model. A
missing or malformed value fails at startup with a message naming the field,
rather than at 3am with an `AttributeError` in a worker.

**Assuming migrations are magic.** `db:make` writes a migration from your model
changes and `db:plan` shows you what it would run. Read the plan. See
[Migrations](/v1.0/orm/migrations/).

##  What to read next

You do not need the whole manual. Pick the shape of what you are building:

- **A JSON API** — [Routing](/v1.0/guides/routing/) →
  [Handlers](/v1.0/guides/handlers/) →
  [Validation](/v1.0/guides/validation/) →
  [Error Handling](/v1.0/guides/error-handling/)
- **Something with users** — [Authentication](/v1.0/guides/authentication/) →
  [Protecting Routes](/v1.0/guides/protecting-routes/) →
  [Sessions](/v1.0/guides/sessions/) → [CSRF](/v1.0/guides/csrf/)
- **Something with a database** — [the ORM manual](/v1.0/orm/), start at
  [Setup](/v1.0/orm/setup/)
- **Anything going to production** —
  [Security](/v1.0/guides/security/) →
  [Startup & Shutdown](/v1.0/guides/startups-and-shutdowns/) →
  [Concurrency](/v1.0/guides/concurrency/)

And [What's in the Box](/v1.0/guides/ecosystem/) if you want to know what you
just installed before you start using it.
