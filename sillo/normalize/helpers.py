from __future__ import annotations

from urllib.parse import urlparse, urlunparse


def normalize_path(path: str, remove_double_slashes: bool = True) -> str:
    """
    Normalizes a URL path by collapsing consecutive slashes and stripping whitespace.

    Processes the given path string by optionally replacing all occurrences of
    double slashes with single slashes in an iterative manner until no consecutive
    slashes remain. Leading and trailing whitespace is always removed from the
    resulting path string.

    Args:
        path (str): The raw URL path string to normalize. May contain double
            slashes, extra whitespace, or other irregularities that need cleanup.
        remove_double_slashes (bool): Whether to collapse consecutive forward
            slashes into a single slash. Defaults to True. Set to False if the
            path contains intentional double slashes that should be preserved.

    Returns:
        str: The normalized path string with double slashes removed (if requested)
        and leading/trailing whitespace stripped.
    """
    if remove_double_slashes:
        while "//" in path:
            path = path.replace("//", "/")
    path = path.strip()
    return path


def has_trailing_slash(path: str) -> bool:
    """
    Checks whether a URL path ends with a trailing forward slash.

    Evaluates the given path string to determine if it has a trailing slash
    character. A single root path consisting of only ``/`` is not considered
    to have a trailing slash, as removing it would produce an empty string.

    Args:
        path (str): The URL path string to check for a trailing slash character.

    Returns:
        bool: True if the path has more than one character and ends with a
        forward slash, False otherwise including for the root path ``/``.
    """
    return len(path) > 1 and path.endswith("/")


def add_trailing_slash(path: str) -> str:
    """
    Appends a trailing forward slash to a URL path if one is not already present.

    Examines the given path and adds a trailing slash character to the end if
    the path does not already end with one. If the path already has a trailing
    slash, it is returned unchanged. This is useful for enforcing consistent
    URL formatting in web applications that require trailing slashes.

    Args:
        path (str): The URL path string to which a trailing slash should be
            appended if not already present.

    Returns:
        str: The path string guaranteed to end with a forward slash character.
    """
    if not has_trailing_slash(path):
        path += "/"
    return path


def remove_trailing_slash(path: str) -> str:
    """
    Removes a trailing forward slash from a URL path if one is present.

    Examines the given path and strips the trailing slash character from the
    end if one exists. If the path does not have a trailing slash, it is
    returned unchanged. The root path ``/`` is preserved as-is since removing
    it would produce an empty string.

    Args:
        path (str): The URL path string from which a trailing slash should be
            removed if present.

    Returns:
        str: The path string with any trailing forward slash removed, or the
        original path if no trailing slash was present.
    """
    if has_trailing_slash(path):
        path = path[:-1]
    return path


def should_skip_path_processing(path: str) -> bool:
    """
    Determines whether URL path normalization should be skipped for a given path.

    Checks the path string against a set of patterns that indicate the path
    should not be processed by the normalization middleware. Paths containing
    file extensions (dots), query string indicators (question marks), or
    fragment identifiers (hash symbols) are flagged for skipping to avoid
    corrupting these special URL components during normalization.

    Args:
        path (str): The URL path string to evaluate for processing eligibility.

    Returns:
        bool: True if the path contains any skip pattern characters (``.``,
        ``?``, or ``#``) indicating it should bypass normalization, False
        if the path is safe to process normally.
    """
    skip_patterns = [".", "?", "#"]
    return any(pattern in path for pattern in skip_patterns)


def build_normalized_url(
    base_url: str,
    path: str,
    preserve_query: bool = True,
    preserve_fragment: bool = True,
) -> str:
    """
    Constructs a normalized URL by combining a base URL with a new path component.

    Parses the base URL into its constituent parts and replaces the path with
    the provided path argument while optionally preserving the original query
    string and fragment components. This is useful for redirect scenarios where
    the path needs to be modified while maintaining other URL components.

    Args:
        base_url (str): The original URL string whose scheme, netloc, and
            optionally query and fragment components will be preserved.
        path (str): The new path string to use in the constructed URL,
            replacing the path component of the base URL.
        preserve_query (bool): Whether to retain the query string from the
            base URL in the resulting URL. Defaults to True.
        preserve_fragment (bool): Whether to retain the fragment identifier
            from the base URL in the resulting URL. Defaults to True.

    Returns:
        str: A fully constructed URL string combining the base URL's scheme
        and netloc with the new path and optionally preserved query/fragment.
    """
    parsed = urlparse(base_url)
    components = [
        parsed.scheme,
        parsed.netloc,
        path,
        parsed.params,
        parsed.query if preserve_query else "",
        parsed.fragment if preserve_fragment else "",
    ]
    return urlunparse(components)


def clean_url_path(url: str) -> str:
    """
    Cleans the path component of a URL by normalizing consecutive slashes.

    Parses the given URL and applies path normalization to the path component
    only, collapsing any double slashes into single slashes. All other URL
    components including scheme, netloc, query string, and fragment are
    preserved unchanged in the resulting URL.

    Args:
        url (str): The full URL string whose path component should be cleaned
            of double slashes and other path irregularities.

    Returns:
        str: The URL string with its path component normalized, while all
        other URL components remain intact and unmodified.
    """
    parsed = urlparse(url)
    normalized_path = normalize_path(parsed.path)
    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            normalized_path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        )
    )


def get_path_segments(path: str) -> list[str]:
    """
    Splits a URL path into its individual non-empty segment components.

    Strips leading and trailing slashes from the path and then splits the
    remaining string on forward slash characters to produce a list of
    individual path segments. An empty or root-only path produces an empty
    list rather than a list containing empty strings.

    Args:
        path (str): The URL path string to split into individual segments.
            Leading and trailing slashes are stripped before splitting.

    Returns:
        List[str]: A list of non-empty path segment strings. Returns an
        empty list if the path is empty or consists only of slashes.
    """
    path = path.strip("/")
    if not path:
        return []
    return path.split("/")


def join_path_segments(segments: list[str], trailing_slash: bool = False) -> str:
    """
    Joins a list of path segments into a single URL path string.

    Combines the provided path segments with forward slash separators and
    prepends a leading slash to form a valid URL path. Optionally appends
    a trailing slash to the resulting path based on the ``trailing_slash``
    parameter.

    Args:
        segments (List[str]): A list of individual path segment strings to
            join together with forward slash separators.
        trailing_slash (bool): Whether to append a trailing forward slash
            to the resulting path. Defaults to False.

    Returns:
        str: A properly formatted URL path string with a leading slash and
        segments joined by forward slashes, optionally with a trailing slash.
    """
    path = "/" + "/".join(segments)
    if trailing_slash and not path.endswith("/"):
        path += "/"
    return path


def is_absolute_url(url: str) -> bool:
    """
    Determines whether a URL string is an absolute URL with scheme and netloc.

    Parses the given URL string and checks whether it contains both a scheme
    component (such as ``http`` or ``https``) and a network location component
    (such as a domain name or IP address). Relative URLs and protocol-relative
    URLs without a scheme will return False.

    Args:
        url (str): The URL string to evaluate for absolute URL characteristics.

    Returns:
        bool: True if the URL contains both a valid scheme and a netloc
        component, False otherwise.
    """
    parsed = urlparse(url)
    return bool(parsed.scheme and parsed.netloc)


def normalize_url(url: str, preserve_case: bool = True) -> str:
    """
    Normalizes a URL string by cleaning its path component of double slashes.

    Handles both absolute and relative URLs. For absolute URLs, the path
    component is parsed and normalized while preserving all other URL parts.
    For relative URLs, the entire string is treated as a path and normalized
    directly. The ``preserve_case`` parameter is accepted for API compatibility
    but path case normalization is not currently implemented.

    Args:
        url (str): The URL string to normalize. Can be either an absolute URL
            with scheme and netloc or a relative path string.
        preserve_case (bool): Whether to preserve the original case of the URL
            path. Defaults to True. Reserved for future case normalization.

    Returns:
        str: The normalized URL string with double slashes collapsed in the
        path component while all other parts remain unchanged.
    """
    if not is_absolute_url(url):
        return normalize_path(url)
    parsed = urlparse(url)
    normalized_path = normalize_path(parsed.path)
    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            normalized_path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        )
    )


def is_double_slash(path: str) -> bool:
    """
    Checks whether a URL path contains any consecutive forward slash characters.

    Scans the given path string for the presence of double slash sequences
    which may indicate a need for path normalization. This is a simple
    containment check and does not perform any modification of the path.

    Args:
        path (str): The URL path string to check for double slash sequences.

    Returns:
        bool: True if the path contains at least one occurrence of two
        consecutive forward slashes, False otherwise.
    """
    return "//" in path
