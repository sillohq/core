from __future__ import annotations

import re
import typing
from html.parser import HTMLParser as _HTMLParser

_HTML_TAG_RE = re.compile(r"<[^>]*>")
_MULTI_SPACE_RE = re.compile(r"\s+")
_WORD_RE = re.compile(r"\w+")
_PLURAL_IRREGULARS = {
    "child": "children",
    "man": "men",
    "woman": "women",
    "person": "people",
    "mouse": "mice",
    "goose": "geese",
    "tooth": "teeth",
    "foot": "feet",
    "ox": "oxen",
    "crisis": "crises",
    "analysis": "analyses",
    "phenomenon": "phenomena",
    "criterion": "criteria",
    "datum": "data",
}


def truncate(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate a string to a maximum length, appending a suffix if truncated.

    If the input text exceeds max_length, it is cut to fit within the limit
    including the suffix. Trailing whitespace is stripped before the suffix
    is appended.

    Args:
        text: The input string to truncate.
        max_length: The maximum total length of the returned string,
            including the suffix.
        suffix: The string to append when truncation occurs.
            Defaults to '...'.

    Returns:
        The original text if it fits within max_length, otherwise the
        truncated text with the suffix appended.

    Raises:
        TypeError: If text is not a string or max_length is not an integer.
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)].rstrip() + suffix


def excerpt(text: str, query: str, radius: int = 50) -> str:
    """Extract a contextual excerpt from text around a search query match.

    Strips HTML tags from the input, locates the first case-insensitive
    occurrence of the query, and returns a window of text centered on the
    match. If no match is found, returns a truncated view of the beginning
    of the text.

    Args:
        text: The source text, potentially containing HTML markup.
        query: The search term to locate within the stripped text.
        radius: The number of characters to include on each side of the
            matched query. Defaults to 50.

    Returns:
        A text excerpt centered on the query match with '...' ellipsis
        markers where text was truncated, or a truncated preview if the
        query is not found.

    Raises:
        TypeError: If text or query is not a string.
    """
    stripped = strip_html(text)
    idx = stripped.lower().find(query.lower())
    if idx == -1:
        return truncate(stripped, radius * 2)
    start = max(0, idx - radius)
    end = min(len(stripped), idx + len(query) + radius)
    result = stripped[start:end]
    if start > 0:
        result = "..." + result
    if end < len(stripped):
        result = result + "..."
    return result


def strip_html(text: str) -> str:
    """Remove all HTML tags from a string and normalize whitespace.

    Strips HTML tags using a compiled regex and collapses consecutive
    whitespace characters into single spaces, producing plain text
    suitable for display or indexing.

    Args:
        text: The input string potentially containing HTML markup.

    Returns:
        The plain text content with all HTML tags removed and
        whitespace normalized to single spaces.

    Raises:
        TypeError: If text is not a string.
    """
    return _MULTI_SPACE_RE.sub(" ", _HTML_TAG_RE.sub(" ", text)).strip()


def pluralize(word: str, count: int) -> str:
    """Return the plural form of an English word based on a count.

    If count is 1, returns the word unchanged. Otherwise applies English
    pluralization rules including irregular forms (e.g. 'child' -> 'children'),
    sibilant endings (-es), consonant + y (-ies), and -f/-fe endings (-ves).

    Args:
        word: The singular English word to pluralize.
        count: The quantity determining whether to pluralize.
            A count of 1 returns the singular form.

    Returns:
        The singular word if count is 1, otherwise the plural form
        according to English pluralization rules.

    Raises:
        TypeError: If word is not a string or count is not an integer.
    """
    if count == 1:
        return word
    word_lower = word.lower()
    if word_lower in _PLURAL_IRREGULARS:
        return _PLURAL_IRREGULARS[word_lower]

    if word_lower.endswith(("s", "x", "z", "ch", "sh")):
        return word + "es"
    if word_lower.endswith("y") and len(word) > 1 and word[-2] not in "aeiou":
        return word[:-1] + "ies"
    if word_lower.endswith("f") and word_lower not in ("roof", "chief", "belief"):
        return word[:-1] + "ves"
    if word_lower.endswith("fe"):
        return word[:-2] + "ves"
    return word + "s"


def word_count(text: str) -> int:
    """Count the number of words in a text string.

    Uses a regex pattern to find all sequences of word characters,
    providing a simple word count suitable for text analysis.

    Args:
        text: The input string to count words in.

    Returns:
        The number of words found in the text as an integer.

    Raises:
        TypeError: If text is not a string.
    """
    return len(_WORD_RE.findall(text))


def ellipsis(text: str, max_lines: int) -> str:
    """Truncate multi-line text to a maximum number of lines with an ellipsis.

    If the text has more lines than max_lines, keeps only the first max_lines
    lines and appends a line containing '...' to indicate truncation.

    Args:
        text: The input multi-line string to truncate.
        max_lines: The maximum number of content lines to retain
            before adding the ellipsis indicator.

    Returns:
        The original text if it has max_lines or fewer lines, otherwise
        the first max_lines lines followed by a '...' line.

    Raises:
        TypeError: If text is not a string or max_lines is not an integer.
    """
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    return "\n".join(lines[:max_lines]) + "\n..."


def wrap_text(text: str, width: int = 80) -> str:
    """Wrap text to fit within a specified character width per line.

    Splits the input into words and reassembles them into lines that do
    not exceed the given width. Words are never split across lines.

    Args:
        text: The input string to wrap.
        width: The maximum number of characters per line.
            Defaults to 80.

    Returns:
        The wrapped text as a single string with lines separated
        by newline characters.

    Raises:
        TypeError: If text is not a string or width is not an integer.
    """
    words = text.split()
    lines: typing.List[str] = []
    current: typing.List[str] = []
    current_len = 0
    for word in words:
        if current_len + len(word) + len(current) > width:
            lines.append(" ".join(current))
            current = [word]
            current_len = len(word)
        else:
            current.append(word)
            current_len += len(word)
    if current:
        lines.append(" ".join(current))
    return "\n".join(lines)


def extract_urls(text: str) -> typing.List[str]:
    """Extract all HTTP and HTTPS URLs from a text string.

    Uses a regex pattern to find all substrings that match the structure
    of HTTP or HTTPS URLs, stopping at whitespace or common delimiter
    characters.

    Args:
        text: The input string to search for URLs.

    Returns:
        A list of URL strings found in the text. Returns an empty list
        if no URLs are found.

    Raises:
        TypeError: If text is not a string.
    """
    pattern = re.compile(r'https?://[^\s<>"\'\)\[\]{}|\\^`]+')
    return pattern.findall(text)


def extract_emails(text: str) -> typing.List[str]:
    """Extract all email addresses from a text string.

    Uses a regex pattern to find all substrings matching common email
    address formats, including those with dots, hyphens, underscores,
    and plus signs in the local part.

    Args:
        text: The input string to search for email addresses.

    Returns:
        A list of email address strings found in the text. Returns an
        empty list if no email addresses are found.

    Raises:
        TypeError: If text is not a string.
    """
    pattern = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
    return pattern.findall(text)
