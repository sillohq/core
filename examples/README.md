# Nexios Examples

Welcome to the Nexios examples directory! This folder contains comprehensive examples demonstrating various features of the Nexios web framework.

## Directory Structure

```
examples/
├── getting_started/      # Basic examples for newcomers
├── routing/              # Routing patterns and techniques
├── responses/            # Different response types
├── middleware/           # Middleware implementations
├── auth/                 # Authentication examples
├── websockets/           # WebSocket functionality
├── request_inputs/       # Handling different request types
├── database/             # Database integrations
├── templating/           # Template engine usage
├── validation/           # Data validation patterns
├── exception_handling/   # Error handling
└── file_handling/        # File uploads and downloads
```

## Quick Navigation

| Category | Description |
|----------|-------------|
| [Getting Started](./getting_started/) | Hello world, REST API, enhanced demos |
| [Routing](./routing/) | Basic routes, path parameters, routers |
| [Responses](./responses/) | JSON, HTML, text, file responses |
| [Middleware](./middleware/) | Function-based, class-based, ASGI middleware |
| [Authentication](./auth/) | Session, JWT, custom backends |
| [WebSockets](./websockets/) | Echo, chat rooms, history managers |
| [Request Inputs](./request_inputs/) | JSON, form data, raw body, streaming |
| [Database](./database/) | SQLite, Tortoise ORM examples |
| [Templating](./templating/) | Jinja2 templates, inheritance, filters |
| [Validation](./validation/) | Pydantic models, custom validation |
| [Exception Handling](./exception_handling/) | Custom exceptions, error handlers |
| [File Handling](./file_handling/) | Upload, download, streaming |

## Running Examples

Most examples can be run directly:

```bash
python example_file.py
```

Or with uvicorn:

```bash
uvicorn example_file:app --reload
```

## Prerequisites

Some examples require additional dependencies:

- **Templating**: `jinja2`
- **Database (Tortoise)**: `tortoise-orm`
- **Validation**: `pydantic`
- **File Handling**: `aiofiles`

Install extras:
```bash
pip install nexios[all]
```