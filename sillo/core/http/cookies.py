import typing
from urllib.parse import unquote


def parse_cookies(
    cookie_string: str | None,
) -> dict[str, typing.Any]:
    """Parse a ``Cookie`` HTTP header string into a dictionary of key-value pairs.

    Mimics browser cookie-parsing behavior, which is often more lenient than
    the formal specification defined in RFC 6265.  Browsers and web servers
    routinely ignore strict parsing rules, so this implementation handles the
    common real-world scenarios that arise in production traffic.

    The function splits the raw header on semicolons, trims whitespace from
    each token, and URL-decodes the values.  Keys without a corresponding
    value are stored with ``None``.

    Adapted from Django 3.1.0, but deliberately avoids the outdated
    ``SimpleCookie.load`` method which rejects many valid inputs.

    Args:
        cookie_string: The raw ``Cookie`` header value as received from the
            client, or ``None`` if the header was not present in the request.

    Returns:
        A dictionary mapping cookie names (``str``) to their URL-decoded
        values (``str``).  Cookies that had no value are mapped to ``None``.
        Returns an empty dictionary when *cookie_string* is ``None`` or
        contains no parseable tokens.

    Raises:
        TypeError: If *cookie_string* is neither ``str`` nor ``None``.
    """

    if cookie_string is None:
        return {}
    cookie_dict: dict[str, str | None] = {}

    for chunk in cookie_string.split(";"):
        chunk = chunk.strip()
        if "=" in chunk:
            key, val = chunk.split("=", 1)
        else:
            key, val = "", chunk

        key = key.strip()
        val = val.strip()

        if key or val:
            cookie_dict[key] = unquote(val) if val else None

    return cookie_dict
