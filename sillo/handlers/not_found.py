import http
import traceback
import typing

from sillo.exceptions import NotFoundException
from sillo.core.http import Request, Response


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
    """Handle 404 Not Found errors with content negotiation across multiple formats.

    Dynamically selects the appropriate response format (JSON, HTML, or plain text)
    based on application settings. In debug mode, detailed error messages and
    traceback information are included; in production, a sanitized custom message
    is returned instead to avoid leaking internal details.

    The function first attempts to load configuration from the application settings
    object. If settings are unavailable, it falls back to sensible defaults:
    JSON output enabled, HTML rendering enabled, and debug mode active.

    Args:
        request: The incoming HTTP request object. Not directly used in the
            current implementation but retained for interface compatibility
            with other error handlers.
        response: A response factory object providing ``.json()``, ``.html()``,
            and ``.text()`` methods for constructing typed HTTP responses.
        exception: The ``NotFoundException`` instance that triggered this handler,
            whose ``detail`` attribute supplies the error message in debug mode.

    Returns:
        A ``Response`` object with status code 404, formatted as JSON, HTML,
        or plain text depending on the resolved configuration.

    Raises:
        None: All exceptions during settings access are caught and silently
            ignored, causing the function to use default values.
    """
    try:
        settings = None
    except Exception:
        settings = None

    if settings:
        debug = settings.debug
        not_found_config = settings.not_found
    else:
        debug = True
        not_found_config = None

    if not_found_config:
        return_json = not_found_config.return_json
        custom_message = not_found_config.custom_message
        show_traceback = not_found_config.show_traceback
        use_html = not_found_config.use_html
    else:
        return_json = True
        custom_message = "The page you are looking for does not exist."
        show_traceback = False
        use_html = True

    error_message = exception.detail if debug else custom_message

    if show_traceback and debug:
        traceback_info = traceback.format_exc()
    else:
        traceback_info = None

    if return_json:
        error_details: typing.Dict[str, typing.Any] = {
            "status": 404,
            "error": http.HTTPStatus(404).phrase,
            "message": error_message,
        }
        if traceback_info:
            error_details["traceback"] = traceback_info

        return response.json(error_details, status_code=404)

    if use_html:
        html_content = generate_html_page("404 - Not Found", error_message)
        return response.html(html_content, status_code=404)

    # Plain Text Fallback
    return response.text(
        f"404 - Not Found\n{error_message}",
    )
