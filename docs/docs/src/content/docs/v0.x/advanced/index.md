---
title: "Sillo Internal Engineering Documentation"
description: "How Sillo works internally, documented subsystem by subsystem."
---

**Version:** 2026-08-11
**Audience:** Core maintainers, contributors, senior engineers, framework architects
**Purpose:** Preserve deep institutional knowledge about how Sillo works internally

---

## Part I: Architecture & Foundations

| # | Document | Description |
|---|----------|-------------|
| 01 | [Architecture Overview](/v0.x/advanced/architecture-overview/) | System layers, boundaries, component relationships, dependency graph |
| 02 | [Application Lifecycle](/v0.x/advanced/application-lifecycle/) | SilloApp, ASGI lifespan, startup/shutdown, state management |
| 03 | [Configuration System](/v0.x/advanced/configuration/) | Config class, .env loading, secret masking, environment variables |
| 04 | [Type System & Encoding](/v0.x/advanced/types-and-encoding/) | Core type aliases, jsonable_encoder, custom encoders, serialization |

## Part II: HTTP Layer

| # | Document | Description |
|---|----------|-------------|
| 05 | [Routing System](/v0.x/advanced/routing/) | Route compilation, path matching, typed converters, groups, mounted routers |
| 06 | [Middleware Pipeline](/v0.x/advanced/middleware/) | BaseMiddleware, ASGI bridge, middleware chain, execution order |
| 07 | [HTTP Request](/v0.x/advanced/http-request/) | HTTPConnection, Request, body parsing, form data, file uploads |
| 08 | [HTTP Response](/v0.x/advanced/http-response/) | BaseResponse, JSON/File/Streaming/Redirect responses, Responder pattern |
| 09 | [HTTP Correctness](/v0.x/advanced/http-correctness/) | Content negotiation, ETags, range requests, HTTP client |
| 10 | [Exception Handling](/v0.x/advanced/exception-handling/) | Exception hierarchy, ExceptionMiddleware, error handlers, status codes |

## Part III: Dependency Injection & Validation

| # | Document | Description |
|---|----------|-------------|
| 11 | [Dependency Injection](/v0.x/advanced/dependency-injection/) | Depend(), Dependant tree, execution plan, resolution algorithm |
| 12 | [Parameter Extraction](/v0.x/advanced/parameters/) | Query/Header/Cookie/Path/Form/File markers, dual-mode validation |
| 13 | [Validation System](/v0.x/advanced/validation/) | Pydantic compilation, LocationSpec, CompiledValidator, error accumulation |
| 14 | [OpenAPI Generation](/v0.x/advanced/openapi/) | Schema building, security schemes, documentation UIs, route iteration |

## Part IV: Authentication & Authorization

| # | Document | Description |
|---|----------|-------------|
| 15 | [Authentication Architecture](/v0.x/advanced/authentication/) | useAuth, AuthenticationBackend, AuthenticationMiddleware, scheme handling |
| 16 | [Auth Backends](/v0.x/advanced/auth-backends/) | Session auth, JWT auth, API key auth, token lifecycle |
| 17 | [User System](/v0.x/advanced/users/) | UserProtocol, UserBaseModel, UserManager, SimpleUser, mixins |
| 18 | [Permissions & Groups](/v0.x/advanced/permissions/) | Permission model, groups, PermissionMixin, cache, authorization flow |
| 19 | [Password Hashing](/v0.x/advanced/hashing/) | Schemes (bcrypt/argon2/scrypt/pbkdf2), verification, password utilities |

## Part V: Security

| # | Document | Description |
|---|----------|-------------|
| 20 | [Security Middleware](/v0.x/advanced/security/) | Shield (headers), CORS, CSRF, rate limiting strategies and backends |

## Part VI: Database & ORM

| # | Document | Description |
|---|----------|-------------|
| 21 | [Record ORM - Models](/v0.x/advanced/record-models/) | Model class, fields, mixins, casting, serialization, soft deletes |
| 22 | [Record ORM - Queries](/v0.x/advanced/record-queries/) | RecordQuerySet, scopes, RecordManager, query helpers, pagination |
| 23 | [Record ORM - Transactions](/v0.x/advanced/record-transactions/) | Transaction context, savepoints, manual control, DatabaseManager |
| 24 | [Record ORM - Migrations](/v0.x/advanced/record-migrations/) | Migration commands, MigrationHelper, bridge module, console commands |
| 25 | [Record ORM - Factories & Seeders](/v0.x/advanced/record-factories/) | Factory, FactoryBuilder, Seeder, FixtureLoader, test data generation |

## Part VII: Background Work

| # | Document | Description |
|---|----------|-------------|
| 26 | [Work - Task System](/v0.x/advanced/work-tasks/) | Task class, lifecycle, priorities, hooks, serialization |
| 27 | [Work - Queue System](/v0.x/advanced/work-queues/) | Queue backends, job dispatch, workers, middleware, batches, failed jobs |
| 28 | [Work - Scheduler](/v0.x/advanced/work-scheduler/) | Cron parser, triggers, scheduler manager, middleware |
| 29 | [Work - Background Tasks](/v0.x/advanced/work-background/) | BackgroundTask, Supervisor, restart policies, circuit breaker |

## Part VIII: Real-Time

| # | Document | Description |
|---|----------|-------------|
| 30 | [Events System](/v0.x/advanced/events/) | Event, EventEmitter, transports (memory/redis/persistent/record), propagation |
| 31 | [WebSockets](/v0.x/advanced/websockets/) | WebSocket state machine, consumers, channels, groups, history |

## Part IX: Application Features

| # | Document | Description |
|---|----------|-------------|
| 32 | [Session Management](/v0.x/advanced/sessions/) | SessionMiddleware, cookie/file backends, Session object, config |
| 33 | [Cache System](/v0.x/advanced/cache/) | MemoryCache, RedisCache, @cache decorator, serialization, tags |
| 34 | [Templating](/v0.x/advanced/templating/) | Jinja2 integration, TemplateEngine, middleware, context injection |
| 35 | [Mail Service](/v0.x/advanced/mail/) | MailClient, SMTP, templates, attachments, config |
| 36 | [Console Framework](/v0.x/advanced/console/) | Command, Console, arguments/options/flags, output, prompts, terminal |
| 37 | [Admin Panel](/v0.x/advanced/admin/) | AdminSite, registry, routes, auth, activity log, default user model |
| 38 | [Pagination](/v0.x/advanced/pagination/) | Strategies (PageNumber/LimitOffset/Cursor), data handlers, paginators |

## Part X: Testing & Tools

| # | Document | Description |
|---|----------|-------------|
| 39 | [Test Client](/v0.x/advanced/test-client/) | Sync/async ASGI test clients, transport, WebSocket testing, helpers |
| 40 | [Helpers & Utilities](/v0.x/advanced/helpers/) | Files, retry, crypto, JWT, network, HTML, strings, text utilities |

## Part XI: Ecosystem Packages

| # | Document | Description |
|---|----------|-------------|
| 41 | [sillo-oauth](/v0.x/advanced/oauth/) | Provider abstraction, OAuth flow, state management, PKCE, testing |
| 42 | [sillo-inertia](/v0.x/advanced/inertia/) | Adapter, HTML/JSON decision, props, Vite integration, version mismatch |
| 43 | [sillo-start](/v0.x/advanced/start/) | Project creation, tarball fetching, personalization, naming utilities |
| 44 | [@sillo/atlas](/v0.x/advanced/atlas/) | OpenAPI reference, DOM construction, API client, search, snippets |
| 45 | [records-orm](/v0.x/advanced/records-orm/) | Standalone pypika-based ORM, backend abstraction, SQLite backend |

## Part XII: Cross-Cutting Concerns

| # | Document | Description |
|---|----------|-------------|
| 46 | [Architectural Decisions](/v0.x/advanced/decisions/) | Key design choices, trade-offs, rejected alternatives |
| 47 | [Debugging Guide](/v0.x/advanced/debugging/) | Symptom → cause → resolution chains, inspection points |
| 48 | [Extending Sillo](/v0.x/advanced/extending/) | Extension patterns, contracts, where new code lives |
| 49 | [Change Impact Analysis](/v0.x/advanced/change-impact/) | Module dependency chains, modification consequences |
| 50 | [Glossary](/v0.x/advanced/glossary/) | Sillo-specific terminology, framework concepts |

---

## How to Use This Documentation

**New to the codebase?** Start with [01-ARCHITECTURE-OVERVIEW.md](/v0.x/advanced/architecture-overview/), then read [02-APPLICATION-LIFECYCLE.md](/v0.x/advanced/application-lifecycle/).

**Debugging a production issue?** Go to [47-DEBUGGING.md](/v0.x/advanced/debugging/) for symptom-based diagnosis.

**Adding a new feature?** Read [48-EXTENDING.md](/v0.x/advanced/extending/) for extension patterns, then [49-CHANGE-IMPACT.md](/v0.x/advanced/change-impact/) to understand blast radius.

**Modifying core code?** Check [49-CHANGE-IMPACT.md](/v0.x/advanced/change-impact/) first to understand dependencies.

**Understanding a specific subsystem?** Use the table above to find the relevant document.

---

## Source Traceability

All technical claims in this documentation are derived from actual source code analysis of the Sillo repository at `/Users/admin/sillo.build/`. File paths reference the working tree as of 2026-08-11.

Key source locations:
- **Core framework:** `/Users/admin/sillo.build/core/sillo/`
- **Tests:** `/Users/admin/sillo.build/core/tests/`
- **OAuth:** `/Users/admin/sillo.build/oauth/sillo_oauth/`
- **Inertia:** `/Users/admin/sillo.build/inertia/sillo_inertia/`
- **Start:** `/Users/admin/sillo.build/start/sillo_start/`
- **Starter:** `/Users/admin/sillo.build/starter/`
- **Atlas:** `/Users/admin/sillo.build/atlas/src/`
- **records-orm:** `/Users/admin/sillo.build/records-orm/records_orm/`
