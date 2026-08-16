"""The Django application under test.

Django is configured in code rather than through a generated project, so that
everything affecting the result is visible in one file instead of spread across
a settings module somebody has to go and read.

**The middleware question.** Django ships a default ``MIDDLEWARE`` list —
security headers, sessions, CSRF, auth, messages, clickjacking — and a bare
Sillo or FastAPI application has no equivalent. Benchmarking Django's default
stack against nothing measures the stack, not the framework, and every Django
developer reading the result would be right to object.

So the default here is an empty middleware list, which is the honest analogue
of the other two. The full default stack is one environment variable away, and
running both is the interesting comparison rather than a footnote:

    SILLO_BENCH_DJANGO_MIDDLEWARE=default

Views are ``async def``. Django has supported them since 3.1, and under ASGI a
sync view is pushed to a thread pool — measuring that instead would be
measuring a deployment choice.
"""

from __future__ import annotations

import os

import django
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.urls import path

from sillo_bench.payloads import PLAINTEXT, ROWS_RESPONSE, SMALL_JSON

#: Django's own defaults, opt-in via ``SILLO_BENCH_DJANGO_MIDDLEWARE=default``.
DEFAULT_MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


def middleware_mode() -> str:
    """Return which middleware stack this process is configured with.

    Returns:
        Either ``"none"`` (the default, comparable to a bare Sillo or FastAPI
        app) or ``"default"`` (Django's shipped stack).
    """
    mode = os.environ.get("SILLO_BENCH_DJANGO_MIDDLEWARE", "none").strip().lower()
    return "default" if mode == "default" else "none"


def configure() -> None:
    """Configure Django settings, once per process.

    Safe to call more than once; the second call is a no-op. Nothing here
    touches a database — no scenario reads one, and requiring Postgres to run a
    routing benchmark would put the suite out of reach for most people.
    """
    if settings.configured:
        return

    use_default = middleware_mode() == "default"

    installed = ["django.contrib.contenttypes", "django.contrib.auth"]
    if use_default:
        installed += ["django.contrib.sessions", "django.contrib.messages"]

    settings.configure(
        DEBUG=False,
        # Fixed rather than random so two runs are byte-identical in every way
        # that could affect the result. Nothing here signs anything a client
        # sees, and the server is only ever reachable on localhost.
        SECRET_KEY="sillo-bench-not-a-secret",  # noqa: S106
        ALLOWED_HOSTS=["*"],
        ROOT_URLCONF=__name__,
        MIDDLEWARE=DEFAULT_MIDDLEWARE if use_default else [],
        INSTALLED_APPS=installed,
        DATABASES={},
        USE_TZ=True,
        # Django logs every request through this logger under ASGI; the other
        # two servers run with access logging off, so this evens it up.
        LOGGING={
            "version": 1,
            "disable_existing_loggers": False,
            "handlers": {"null": {"class": "logging.NullHandler"}},
            "loggers": {
                "django": {"handlers": ["null"], "level": "ERROR"},
                "django.request": {"handlers": ["null"], "level": "ERROR"},
                "django.server": {"handlers": ["null"], "level": "ERROR"},
            },
        },
        TEMPLATES=[
            {
                "BACKEND": "django.template.backends.django.DjangoTemplates",
                "DIRS": [],
                "APP_DIRS": False,
                "OPTIONS": {"context_processors": []},
            }
        ],
    )
    django.setup()


async def plaintext(request):
    """Serve the plaintext scenario."""
    return HttpResponse(PLAINTEXT, content_type="text/plain; charset=utf-8")


async def json_small(request):
    """Serve the small-object scenario."""
    return JsonResponse(SMALL_JSON)


async def item(request, item_id: int):
    """Serve the path-parameter scenario.

    Args:
        request: The Django request.
        item_id: Already an ``int`` — the ``<int:...>`` converter in the URL
            pattern does the coercion, which is Django's equivalent of what the
            other two frameworks do from a type annotation.
    """
    return JsonResponse({"id": item_id})


async def search(request):
    """Serve the query-parameter scenario.

    Django does not coerce query parameters, so the view does it. That is a
    real difference in what the framework offers rather than something to hide:
    the work still has to happen, and here it happens in application code.
    """
    params = request.GET
    return JsonResponse(
        {
            "q": params.get("q", ""),
            "page": int(params.get("page", 1)),
            "per_page": int(params.get("per_page", 20)),
        }
    )


async def rows(request):
    """Serve the 200-row scenario."""
    return JsonResponse(ROWS_RESPONSE)


urlpatterns = [
    path("plaintext", plaintext),
    path("json", json_small),
    path("items/<int:item_id>", item),
    path("search", search),
    path("rows", rows),
]


def create_app():
    """Build the Django ASGI application.

    Returns:
        The ASGI callable produced by ``get_asgi_application()``.
    """
    configure()
    from django.core.asgi import get_asgi_application

    return get_asgi_application()


app = create_app()
