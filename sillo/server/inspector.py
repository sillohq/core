"""The request inspector behind the clickable log lines.

Every access line the development server prints is a hyperlink. Clicking it
opens a page served by the same process, showing what that request actually
was: the timing, both sets of headers, the query parameters, the client, the
response size. The terminal keeps one line per request and the detail lives a
click away, which is the right split — a log you can read and a record you can
dig into, instead of one line trying to be both.

**This is a development tool and it is guarded like one.** The recorded
headers include whatever the client sent, so a page that renders them verbatim
would publish session cookies and bearer tokens to anyone who can reach the
port. Three things follow, and none of them are optional:

- The inspector is only mounted when the server is bound to a loopback
  address. On any other interface it refuses, and says so.
- Sensitive headers are redacted to a short prefix and a length. That is
  enough to tell *which* token was sent without reproducing it.
- Records live in a bounded, in-memory ring buffer that dies with the process.
  Nothing is written to disk.
"""

from __future__ import annotations

import html
import itertools
import json
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

#: Where the inspector mounts. Underscored so it cannot collide with an
#: application route that anyone would plausibly write.
MOUNT = "/__sillo/requests"

#: Header names whose values are never rendered in full.
SENSITIVE = frozenset(
    {
        "authorization",
        "proxy-authorization",
        "cookie",
        "set-cookie",
        "x-api-key",
        "x-auth-token",
        "x-csrf-token",
        "x-xsrf-token",
    }
)


def redact(name: str, value: str) -> str:
    """Return a header value safe to render.

    Args:
        name: The header name, any case.
        value: The header value as sent.

    Returns:
        The value unchanged, or — for a sensitive header — a short prefix and
        the length. The prefix is what makes the redaction useful rather than
        merely safe: it is enough to tell one token from another when you are
        working out which credential a request carried.
    """
    if name.lower() not in SENSITIVE:
        return value
    if not value:
        return "(empty)"
    head = value[:8]
    return f"{head}… ({len(value)} chars, redacted)"


@dataclass
class RequestRecord:
    """One request, as the inspector remembers it.

    Attributes:
        id: Monotonic identifier, used in the URL.
        method: HTTP method.
        path: Path, without the query string.
        query: Raw query string.
        status: Response status, or 0 if the application never sent one.
        duration_ms: Wall time from the server receiving the request to the
            application returning.
        started_at: Unix timestamp when handling began.
        request_headers: What the client sent, in order.
        response_headers: What the application sent back.
        client: ``host:port`` of the peer, when the server knows it.
        http_version: The protocol version.
        scheme: ``http`` or ``https``.
        response_bytes: Body bytes sent.
        error: The exception's repr, when the application raised.
    """

    id: int
    method: str
    path: str
    query: str
    status: int
    duration_ms: float
    started_at: float
    request_headers: list[tuple[str, str]] = field(default_factory=list)
    response_headers: list[tuple[str, str]] = field(default_factory=list)
    client: str = ""
    http_version: str = ""
    scheme: str = "http"
    response_bytes: int = 0
    error: str = ""

    @property
    def full_path(self) -> str:
        """The path with its query string, as the client asked for it."""
        return f"{self.path}?{self.query}" if self.query else self.path


class RequestLog:
    """A bounded, in-memory ring of recent requests.

    Bounded because a development server left running all day would otherwise
    hold every request it ever served. The oldest fall off the end, which is
    the right thing to lose: the interesting request is nearly always a recent
    one.

    Attributes:
        capacity: How many records are kept.
    """

    def __init__(self, capacity: int = 200) -> None:
        """Create the ring.

        Args:
            capacity: How many records to keep before discarding the oldest.
        """
        self.capacity = capacity
        self._records: deque[RequestRecord] = deque(maxlen=capacity)
        self._ids = itertools.count(1)

    def next_id(self) -> int:
        """Return the identifier for the next request to be recorded."""
        return next(self._ids)

    def add(self, record: RequestRecord) -> None:
        """Remember one request.

        Args:
            record: The completed record.
        """
        self._records.append(record)

    def all(self) -> list[RequestRecord]:
        """Return every remembered request, newest first."""
        return list(reversed(self._records))

    def get(self, record_id: int) -> RequestRecord | None:
        """Return one request by id.

        Args:
            record_id: The identifier from the log line's URL.

        Returns:
            The record, or ``None`` if it has aged out of the ring.
        """
        for record in self._records:
            if record.id == record_id:
                return record
        return None


def is_loopback(host: str) -> bool:
    """Return whether *host* is an address only this machine can reach.

    Args:
        host: The interface the server is bound to.

    Returns:
        True for the loopback addresses. Anything else — including
        ``0.0.0.0``, which is every interface — is treated as reachable by
        other machines, and the inspector will not mount there.
    """
    return host in ("127.0.0.1", "::1", "localhost", "127.0.1.1")


# -- rendering ---------------------------------------------------------


def _status_class(status: int) -> str:
    """Return the CSS class for a status code."""
    if status >= 500:
        return "s5"
    if status >= 400:
        return "s4"
    if status >= 300:
        return "s3"
    return "s2"


_STYLE = """
:root {
  --bg: #ffffff; --fg: #1a1a1a; --muted: #6b6b6b; --line: #e6e6e6;
  --panel: #fafafa; --brand: #fc0345;
  --ok: #1a7f37; --redirect: #0969da; --warn: #9a6700; --bad: #cf222e;
}
:root:not([data-theme="light"]) { color-scheme: light dark; }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #0b0b0c; --fg: #ededed; --muted: #9b9b9b; --line: #232326;
    --panel: #141416;
    --ok: #3fb950; --redirect: #58a6ff; --warn: #d29922; --bad: #ff7b72;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--fg);
  font: 14px/1.55 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
.wrap { max-width: 1000px; margin: 0 auto; padding: 32px 20px 64px; }
h1 { font-size: 17px; margin: 0; font-weight: 600; letter-spacing: -0.01em; }
h2 { font-size: 12px; margin: 32px 0 10px; font-weight: 600;
     text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted); }
a { color: inherit; }
.head { display: flex; align-items: baseline; gap: 12px;
        padding-bottom: 14px; border-bottom: 1px solid var(--line); }
.dot { color: var(--brand); }
.muted { color: var(--muted); }
table { width: 100%; border-collapse: collapse; }
td, th { text-align: left; padding: 7px 10px; border-bottom: 1px solid var(--line);
         vertical-align: top; font-weight: normal; }
th { color: var(--muted); font-size: 12px; }
tr:last-child td { border-bottom: none; }
td.k { color: var(--muted); width: 210px; white-space: nowrap; }
td.v { word-break: break-word; }
.panel { background: var(--panel); border: 1px solid var(--line); border-radius: 6px; }
.scroll { overflow-x: auto; }
.s2 { color: var(--ok); } .s3 { color: var(--redirect); }
.s4 { color: var(--warn); } .s5 { color: var(--bad); }
.rows a { display: grid; grid-template-columns: 78px 62px 46px 1fr auto;
          gap: 12px; padding: 8px 10px; text-decoration: none;
          border-bottom: 1px solid var(--line); align-items: baseline; }
.rows a:last-child { border-bottom: none; }
.rows a:hover { background: var(--panel); }
.rows .p { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.num { font-variant-numeric: tabular-nums; }
.empty { padding: 40px 10px; color: var(--muted); }
.back { display: inline-block; margin-bottom: 18px; color: var(--muted);
        text-decoration: none; font-size: 13px; }
.back:hover { color: var(--fg); }
.err { border-left: 2px solid var(--bad); padding-left: 12px; color: var(--bad); }
"""


def _page(title: str, body: str) -> bytes:
    """Wrap rendered body content in the inspector's shell.

    Args:
        title: The document title.
        body: Already-escaped HTML.

    Returns:
        The encoded page.
    """
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{html.escape(title)}</title><style>{_STYLE}</style></head>"
        f"<body><div class='wrap'>{body}</div></body></html>"
    ).encode()


def _duration(milliseconds: float) -> str:
    """Render a duration for the page."""
    if milliseconds < 1:
        return f"{milliseconds * 1000:.0f}µs"
    if milliseconds < 1000:
        return f"{milliseconds:.1f}ms"
    return f"{milliseconds / 1000:.2f}s"


def render_index(log: RequestLog) -> bytes:
    """Render the list of recent requests.

    Args:
        log: The ring buffer.

    Returns:
        The encoded page.
    """
    records = log.all()
    if not records:
        rows = (
            "<div class='empty'>No requests yet. Make one and it will "
            "appear here.</div>"
        )
    else:
        rows = "".join(
            "<a href='{href}'>"
            "<span class='muted num'>{when}</span>"
            "<span>{method}</span>"
            "<span class='{cls} num'>{status}</span>"
            "<span class='p'>{path}</span>"
            "<span class='muted num'>{took}</span>"
            "</a>".format(
                href=f"{MOUNT}/{record.id}",
                when=time.strftime("%H:%M:%S", time.localtime(record.started_at)),
                method=html.escape(record.method),
                cls=_status_class(record.status),
                status=record.status or "—",
                path=html.escape(record.full_path),
                took=_duration(record.duration_ms),
            )
            for record in records
        )
        rows = f"<div class='panel rows'>{rows}</div>"

    return _page(
        "Requests · sillo",
        "<div class='head'><span class='dot'>●</span><h1>requests</h1>"
        f"<span class='muted'>most recent {len(records)} of "
        f"{log.capacity} kept</span></div>"
        f"<h2>Recent</h2>{rows}",
    )


def _rows(pairs: list[tuple[str, str]], redacted: bool = False) -> str:
    """Render a key/value table body.

    Args:
        pairs: The name/value pairs, in order.
        redacted: Whether to pass values through :func:`redact`.

    Returns:
        The table HTML, or a muted placeholder when there is nothing.
    """
    if not pairs:
        return "<div class='empty'>None.</div>"
    body = "".join(
        f"<tr><td class='k'>{html.escape(name)}</td>"
        f"<td class='v'>{html.escape(redact(name, value) if redacted else value)}</td></tr>"
        for name, value in pairs
    )
    return f"<div class='panel scroll'><table>{body}</table></div>"


def render_detail(record: RequestRecord) -> bytes:
    """Render one request in full.

    Args:
        record: The request to show.

    Returns:
        The encoded page.
    """
    query_pairs: list[tuple[str, str]] = []
    if record.query:
        from urllib.parse import parse_qsl

        query_pairs = parse_qsl(record.query, keep_blank_values=True)

    overview = [
        ("method", record.method),
        ("path", record.path),
        ("status", str(record.status or "—")),
        ("duration", _duration(record.duration_ms)),
        ("started", time.strftime("%H:%M:%S", time.localtime(record.started_at))),
        ("client", record.client or "unknown"),
        ("protocol", f"{record.scheme.upper()}/{record.http_version}"),
        ("response size", f"{record.response_bytes:,} bytes"),
    ]

    error_block = ""
    if record.error:
        error_block = (
            "<h2>Unhandled exception</h2>"
            f"<div class='panel'><div class='err' style='padding:12px'>"
            f"{html.escape(record.error)}</div></div>"
        )

    body = (
        f"<a class='back' href='{MOUNT}'>← all requests</a>"
        "<div class='head'><span class='dot'>●</span>"
        f"<h1>{html.escape(record.method)} {html.escape(record.full_path)}</h1>"
        f"<span class='{_status_class(record.status)}'>{record.status or '—'}</span>"
        f"<span class='muted'>{_duration(record.duration_ms)}</span></div>"
        f"{error_block}"
        f"<h2>Overview</h2>{_rows(overview)}"
        f"<h2>Query parameters</h2>{_rows(query_pairs)}"
        f"<h2>Request headers</h2>{_rows(record.request_headers, redacted=True)}"
        f"<h2>Response headers</h2>{_rows(record.response_headers, redacted=True)}"
    )
    return _page(f"{record.method} {record.path} · sillo", body)


class Inspector:
    """Serves the inspector, and passes everything else through.

    Sits outside the application so its own pages never touch the
    application's middleware, never appear in its logs, and cannot be
    intercepted by an authentication layer that would make them unreachable.

    Attributes:
        app: The application being served.
        log: The ring buffer of records.
    """

    def __init__(self, app: Any, log: RequestLog) -> None:
        """Mount the inspector in front of *app*.

        Args:
            app: The next ASGI application.
            log: The request log to read.
        """
        self.app = app
        self.log = log

    async def __call__(self, scope, receive, send) -> None:
        """Serve an inspector page, or hand the request on.

        Args:
            scope: The ASGI scope.
            receive: Passed through.
            send: Used directly for inspector responses.
        """
        if scope["type"] != "http" or not scope.get("path", "").startswith(MOUNT):
            await self.app(scope, receive, send)
            return

        remainder = scope["path"][len(MOUNT) :].strip("/")

        if not remainder:
            await self._respond(send, 200, render_index(self.log))
            return

        if remainder == "json":
            payload = json.dumps(
                [
                    {
                        "id": r.id,
                        "method": r.method,
                        "path": r.full_path,
                        "status": r.status,
                        "duration_ms": round(r.duration_ms, 3),
                    }
                    for r in self.log.all()
                ],
                indent=2,
            ).encode()
            await self._respond(send, 200, payload, "application/json")
            return

        try:
            record = self.log.get(int(remainder))
        except ValueError:
            record = None

        if record is None:
            await self._respond(
                send,
                404,
                _page(
                    "Not found · sillo",
                    f"<a class='back' href='{MOUNT}'>← all requests</a>"
                    "<div class='head'><h1>No such request</h1></div>"
                    "<p class='muted'>It may have aged out of the ring buffer, "
                    "which keeps only the most recent requests.</p>",
                ),
            )
            return

        await self._respond(send, 200, render_detail(record))

    @staticmethod
    async def _respond(
        send, status: int, body: bytes, content_type: str = "text/html; charset=utf-8"
    ) -> None:
        """Send a complete response.

        Args:
            send: The ASGI send callable.
            status: The status code.
            body: The encoded body.
            content_type: The content type header value.
        """
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", content_type.encode()),
                    (b"content-length", str(len(body)).encode()),
                    # The inspector renders request headers. Nothing should be
                    # caching that, and nothing should be framing it.
                    (b"cache-control", b"no-store"),
                    (b"x-frame-options", b"DENY"),
                    (b"referrer-policy", b"no-referrer"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body, "more_body": False})
