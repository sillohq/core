import http
import traceback
import typing

from sillo.core.http import Request, Response
from sillo.exceptions import NotFoundException

#: Body text used when debug is off, so nothing internal is disclosed.
GENERIC_MESSAGE = "The page you are looking for does not exist."


def generate_html_page(title: str, message: str) -> str:
    """Generate a self-contained HTML error page without external dependencies.

    Builds a complete HTML5 document with inline CSS styling suitable for
    displaying error messages to end users. The page uses a centered layout
    with a styled heading and paragraph for the error content.

    Args:
        title: The text displayed as both the browser tab title and the
            primary heading (h1) on the error page.
        message: The descriptive error message rendered as a paragraph
            below the heading.

    Returns:
        A fully-formed HTML string containing the styled error page,
        ready to be sent as an HTTP response body.

    Raises:
        None
    """
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            text-align: center;
            margin: 50px;
            color: #333;
        }}
        h1 {{
            font-size: 48px;
            color: #d9534f;
        }}
        p {{
            font-size: 18px;
            margin-top: 10px;
        }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    <p>{message}</p>
</body>
</html>"""


async def handle_404_error(
    request: Request,
    response: Response,
    exception: NotFoundException,
) -> Response:
    """Handle 404 Not Found errors, negotiating the response format.

    The response format follows the client's ``Accept`` header rather than a
    server-side setting: a client that asks for JSON gets JSON, a browser gets
    the HTML page, and anything else gets plain text. JSON is the default when
    the header expresses no preference, which is the right default for an API.

    How much detail the body carries depends on the application's ``debug``
    flag, read from ``request.app``. With debug on, the exception's own
    ``detail`` is returned along with a traceback; with debug off — and when
    the flag cannot be read at all — a generic message is returned instead, so
    a misconfigured application errs towards saying less rather than more.

    Args:
        request: The incoming HTTP request, used for the application's debug
            flag and for ``Accept``-header negotiation.
        response: A response factory object providing ``.json()``, ``.html()``,
            and ``.text()`` methods for constructing typed HTTP responses.
        exception: The ``NotFoundException`` instance that triggered this
            handler, whose ``detail`` supplies the message in debug mode.

    Returns:
        A ``Response`` with status code 404, formatted as JSON, HTML, or plain
        text according to what the client asked for.
    """
    debug = _debug_enabled(request)

    if debug:
        error_message = exception.detail
        traceback_info = traceback.format_exc()
        if traceback_info.strip() == "NoneType: None":
            traceback_info = None
    else:
        error_message = GENERIC_MESSAGE
        traceback_info = None

    if _prefers_html(request):
        return response.html(
            generate_html_page("404 - Not Found", error_message), status_code=404
        )

    if request.accepts_json:
        error_details: dict[str, typing.Any] = {
            "status": 404,
            "error": http.HTTPStatus(404).phrase,
            "message": error_message,
        }
        if traceback_info:
            error_details["traceback"] = traceback_info
        return response.json(error_details, status_code=404)

    return response.text(f"404 - Not Found\n{error_message}", status_code=404)


def _debug_enabled(request: Request) -> bool:
    """Read the application's debug flag, defaulting to off.

    The flag lives on the application, which the scope stores under
    ``base_app``; ``app`` holds the router that is actually handling the
    request and carries no debug flag of its own.

    The handler can be invoked outside a fully-built application — in a test
    harness, or against a bare ASGI scope — so a missing app or missing flag
    is treated as production rather than as debug. Erring the other way would
    leak internal paths and tracebacks from any misconfigured deployment.

    Args:
        request: The request whose application should be consulted.

    Returns:
        ``True`` only when the application explicitly has debug enabled.
    """
    scope = getattr(request, "scope", {}) or {}
    for key in ("base_app", "app"):
        candidate = scope.get(key)
        if candidate is not None and hasattr(candidate, "debug"):
            return bool(candidate.debug)
    return False


def _prefers_html(request: Request) -> bool:
    """Decide whether the client would rather have the HTML page.

    A browser sends ``text/html`` ahead of anything else; an API client asks
    for ``application/json`` or sends no preference at all. Only the first of
    those should get the styled page, so a wildcard ``*/*`` is not treated as
    a request for HTML.

    Args:
        request: The request whose ``Accept`` header should be inspected.

    Returns:
        ``True`` when the client explicitly listed an HTML media type.
    """
    accept = request.headers.get("accept", "")
    return "text/html" in accept or "application/xhtml+xml" in accept
