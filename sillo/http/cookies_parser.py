import typing
from urllib.parse import unquote


def parse_cookies(
    cookie_string: typing.Union[str, None],
) -> typing.Dict[str, typing.Any]:
    """
    Parses a ``Cookie`` HTTP header into a dictionary of key/value pairs.

    Mimics browser cookie parsing behavior, which is often less strict than the spec (RFC 6265).
    This function handles common scenarios that browsers and web servers often ignore in cookie parsing.

    Adapted from Django 3.1.0, but avoids using outdated `SimpleCookie.load`.
    """

    if cookie_string is None:
        return {}
    cookie_dict: typing.Dict[str, typing.Optional[str]] = {}

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
