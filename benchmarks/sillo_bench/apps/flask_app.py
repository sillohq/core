"""The Flask application under test.

Flask is the only WSGI framework in this suite, and that asymmetry is the whole
story of its result. Three things are worth reading before comparing its numbers
to anything else here.

**It runs behind a WSGI-to-ASGI adapter.** Every other application is native
ASGI and is served directly by uvicorn. Flask cannot be, so ``a2wsgi`` bridges
it. Keeping uvicorn constant is what makes the rest of the table comparable, and
swapping in a second server for one row would break that far more than the
adapter distorts it — but the adapter is not free, and part of Flask's overhead
here is the bridge rather than Flask.

**WSGI is synchronous, so requests run in a thread pool.** Concurrency is capped
by pool size rather than by an event loop, which is a real property of WSGI and
not an artefact. The pool defaults to 32 threads and is tunable:

    SILLO_BENCH_FLASK_THREADS=64

**This is not how Flask is deployed.** Production Flask runs under gunicorn or
uWSGI with several worker *processes*, which sidesteps the GIL in a way a single
uvicorn worker cannot. A serious Flask deployment on this hardware would post a
considerably better number than the one measured here. Read this row as "Flask's
per-request cost under a controlled server", not as "what Flask can do".

Key sorting is switched off. Flask's JSON provider sorts keys by default and
nothing else in this suite does, so leaving it on would charge Flask for work no
other framework performs.
"""

from __future__ import annotations

import os

from a2wsgi import WSGIMiddleware
from flask import Flask, jsonify, request

from sillo_bench.payloads import PLAINTEXT, ROWS_RESPONSE, SMALL_JSON


def thread_count() -> int:
    """Return the WSGI adapter's thread pool size.

    Returns:
        The value of ``SILLO_BENCH_FLASK_THREADS``, or 32. Thirty-two is a
        middle setting: low enough that the pool is a visible constraint, as it
        genuinely is for WSGI, and high enough that the result is not simply a
        measurement of the pool.
    """
    raw = os.environ.get("SILLO_BENCH_FLASK_THREADS", "32")
    try:
        return max(1, int(raw))
    except ValueError:
        return 32


def create_wsgi_app() -> Flask:
    """Build the Flask application itself, before the ASGI bridge.

    Returns:
        A configured ``Flask`` instance serving every scenario route.
    """
    app = Flask(__name__)
    app.config["DEBUG"] = False
    app.config["TESTING"] = False
    # Flask sorts JSON object keys by default; no other framework here does.
    # Leaving it on would bill Flask for work nothing else performs.
    app.json.sort_keys = False

    @app.get("/plaintext")
    def plaintext():
        return PLAINTEXT, 200, {"Content-Type": "text/plain; charset=utf-8"}

    @app.get("/json")
    def json_small():
        return jsonify(SMALL_JSON)

    @app.get("/items/<int:item_id>")
    def item(item_id: int):
        return jsonify({"id": item_id})

    @app.get("/search")
    def search():
        args = request.args
        return jsonify(
            {
                "q": args.get("q", ""),
                "page": int(args.get("page", 1)),
                "per_page": int(args.get("per_page", 20)),
            }
        )

    @app.get("/rows")
    def rows():
        return jsonify(ROWS_RESPONSE)

    return app


def create_app():
    """Build the ASGI-callable Flask application.

    Returns:
        The Flask app wrapped in ``a2wsgi.WSGIMiddleware`` so uvicorn can serve
        it alongside the native ASGI applications.
    """
    return WSGIMiddleware(create_wsgi_app(), workers=thread_count())


app = create_app()
