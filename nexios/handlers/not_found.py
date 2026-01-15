import http
import traceback
import typing

from nexios.config import get_config
from nexios.exceptions import NotFoundException
from nexios.http import Request, Response


def generate_html_page(title: str, message: str) -> str:
    """Generates a simple HTML page without using Jinja2."""
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
) -> typing.Any:
    """
    Handles 404 errors dynamically, supporting JSON, HTML, and plain text responses.

    Args:
        request: The request object (not used here but kept for flexibility).
        response: A callable that returns a response.
        exception: The NotFoundException instance.
        settings: A dictionary of settings to determine the response format.

    Returns:
        A response based on the settings.
    """
    try:
        settings = get_config()
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
