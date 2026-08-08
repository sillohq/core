from __future__ import annotations

import re
import secrets
import string as _string
import unicodedata

_CAMEL_TO_SNAKE_RE = re.compile(r"([A-Z]+)([A-Z][a-z])")
_CAMEL_TO_SNAKE_RE2 = re.compile(r"([a-z\d])([A-Z])")
_SNAKE_TO_CAMEL_RE = re.compile(r"_([a-zA-Z\d])")
_SLUG_RE = re.compile(r"[^\w\s-]")
_SLUG_SPACE_RE = re.compile(r"[-\s]+")


def slugify(text: str, separator: str = "-") -> str:
    """Convert a Unicode string into a URL-safe slug.

    Normalizes the input to ASCII, strips non-alphanumeric characters,
    lowercases the result, and joins words with the specified separator.

    Args:
        text: The input string to convert into a slug.
        separator: The character used to join words in the slug.
            Defaults to a hyphen.

    Returns:
        A URL-safe slug derived from the input text, with words
        separated by the specified separator character.

    Raises:
        TypeError: If text is not a string or separator is not a string.
    """
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = _SLUG_RE.sub("", text).strip().lower()
    text = _SLUG_SPACE_RE.sub(separator, text)
    return text.strip(separator)


def camel_to_snake(name: str) -> str:
    """Convert a camelCase or PascalCase string to snake_case.

    Handles consecutive uppercase letters (e.g. 'HTTPServer' -> 'http_server')
    and standard camelCase transitions (e.g. 'myVariable' -> 'my_variable').

    Args:
        name: The camelCase or PascalCase string to convert.

    Returns:
        The converted snake_case string with lowercase letters and
        underscores separating word boundaries.

    Raises:
        TypeError: If name is not a string.
    """
    name = _CAMEL_TO_SNAKE_RE.sub(r"\1_\2", name)
    name = _CAMEL_TO_SNAKE_RE2.sub(r"\1_\2", name)
    return name.lower()


def snake_to_camel(name: str, capitalize_first: bool = False) -> str:
    """Convert a snake_case string to camelCase or PascalCase.

    Removes underscores and capitalizes the letter following each underscore.
    Optionally capitalizes the first letter to produce PascalCase output.

    Args:
        name: The snake_case string to convert.
        capitalize_first: If True, capitalize the first character to produce
            PascalCase. If False, produce lowerCamelCase. Defaults to False.

    Returns:
        The converted camelCase or PascalCase string with underscores removed
        and appropriate letters capitalized.

    Raises:
        TypeError: If name is not a string or capitalize_first is not a bool.
    """
    result = _SNAKE_TO_CAMEL_RE.sub(lambda m: m.group(1).upper(), name)
    if capitalize_first:
        result = result[0].upper() + result[1:] if result else result
    return result


def pascal_case(name: str) -> str:
    """Convert a snake_case string to PascalCase.

    Delegates to snake_to_camel with capitalize_first=True to produce
    a string where every word boundary is capitalized, including the first.

    Args:
        name: The snake_case string to convert.

    Returns:
        The converted PascalCase string with the first letter and all
        letters following underscores capitalized.

    Raises:
        TypeError: If name is not a string.
    """
    return snake_to_camel(name, capitalize_first=True)


def kebab_case(name: str) -> str:
    """Convert a camelCase or PascalCase string to kebab-case.

    Inserts hyphens at camelCase word boundaries and lowercases the entire
    result, producing a hyphen-separated identifier suitable for URLs and
    CSS class names.

    Args:
        name: The camelCase or PascalCase string to convert.

    Returns:
        The converted kebab-case string with lowercase letters and
        hyphens separating word boundaries.

    Raises:
        TypeError: If name is not a string.
    """
    name = _CAMEL_TO_SNAKE_RE.sub(r"\1-\2", name)
    name = _CAMEL_TO_SNAKE_RE2.sub(r"\1-\2", name)
    return name.lower()


def mask_string(
    value: str,
    visible_start: int = 4,
    visible_end: int = 4,
    mask_char: str = "*",
) -> str:
    """Mask the middle portion of a string, preserving visible prefix and suffix.

    Replaces the interior characters of the string with a repeated mask character,
    useful for displaying partial secrets such as API keys or credit card numbers.
    If the string is too short to show both prefix and suffix, the entire string
    is replaced with mask characters.

    Args:
        value: The string to mask.
        visible_start: Number of characters to keep visible at the start.
            Defaults to 4.
        visible_end: Number of characters to keep visible at the end.
            Defaults to 4.
        mask_char: The character used to replace masked portions.
            Defaults to '*'.

    Returns:
        The masked string with visible prefix, mask characters in the middle,
        and visible suffix.

    Raises:
        TypeError: If value is not a string.
    """
    if len(value) <= visible_start + visible_end:
        return mask_char * len(value)
    # ``value[-0:]`` is the whole string, so an explicit empty suffix is needed
    # when nothing should be visible at the end.
    suffix = value[-visible_end:] if visible_end else ""
    return (
        value[:visible_start]
        + mask_char * (len(value) - visible_start - visible_end)
        + suffix
    )


def mask_email(email: str) -> str:
    """Mask the local part of an email address for privacy display.

    Preserves the first and last characters of the local part (before the @),
    replacing the middle characters with asterisks. The domain part is left
    unchanged. For very short local parts (2 chars or fewer), only the first
    character is kept visible.

    Args:
        email: The full email address to mask, in user@domain format.

    Returns:
        The masked email address with the local part partially obscured
        and the domain part intact.

    Raises:
        ValueError: If the email does not contain an '@' separator.
    """
    local, _, domain = email.partition("@")
    if len(local) <= 2:
        masked_local = local[0] + "*"
    else:
        masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
    return f"{masked_local}@{domain}"


def random_string(
    length: int = 32,
    chars: str | None = None,
) -> str:
    """Generate a cryptographically secure random string.

    Uses the secrets module to produce a random string of the specified length,
    drawing from the provided character set or the default alphanumeric set.

    Args:
        length: The number of characters in the generated string.
            Defaults to 32.
        chars: A string of characters to sample from. If None, uses
            ASCII letters and digits. Defaults to None.

    Returns:
        A random string of the specified length composed of characters
        from the given character set.

    Raises:
        ValueError: If length is negative or chars is an empty string.
    """
    if chars is None:
        chars = _string.ascii_letters + _string.digits
    return "".join(secrets.choice(chars) for _ in range(length))


def random_digits(length: int = 6) -> str:
    """Generate a cryptographically secure random string of digits.

    Uses the secrets module to produce a random numeric string of the
    specified length, suitable for PINs, OTPs, and verification codes.

    Args:
        length: The number of digits in the generated string.
            Defaults to 6.

    Returns:
        A random string of the specified length containing only digit
        characters (0-9).

    Raises:
        ValueError: If length is negative.
    """
    return "".join(secrets.choice(_string.digits) for _ in range(length))


def random_token(length: int = 64) -> str:
    """Generate a cryptographically secure URL-safe random token.

    Uses secrets.token_urlsafe to produce a random token encoded with
    URL-safe base64, suitable for API keys, session identifiers, and
    authentication tokens.

    Args:
        length: The number of random bytes used to generate the token.
            The resulting string will be approximately 4/3 times this
            length. Defaults to 64.

    Returns:
        A URL-safe base64-encoded random token string.

    Raises:
        ValueError: If length is negative.
    """
    return secrets.token_urlsafe(length)


def strip_accents(text: str) -> str:
    """Remove all combining accent characters from a Unicode string.

    Normalizes the input to NFKD form and filters out any characters that
    are classified as combining marks, effectively stripping diacritical
    marks from accented characters.

    Args:
        text: The Unicode string from which to remove accents.

    Returns:
        The input string with all combining accent characters removed,
        leaving base characters intact.

    Raises:
        TypeError: If text is not a string.
    """
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )


def is_camel_case(text: str) -> bool:
    """Determine whether a string is in camelCase format.

    Checks that the string contains both uppercase and lowercase letters
    and does not contain underscores, which would indicate snake_case.

    Args:
        text: The string to test for camelCase formatting.

    Returns:
        True if the string contains mixed case letters and no underscores,
        False otherwise.

    Raises:
        TypeError: If text is not a string.
    """
    return text != text.lower() and text != text.upper() and "_" not in text


def is_snake_case(text: str) -> bool:
    """Determine whether a string is in snake_case format.

    Checks that the string is entirely lowercase, contains at least one
    underscore, and does not start with an underscore (which would indicate
    a private/protected naming convention).

    Args:
        text: The string to test for snake_case formatting.

    Returns:
        True if the string is lowercase, contains underscores, and does
        not start with an underscore. False otherwise.

    Raises:
        TypeError: If text is not a string.
    """
    return text == text.lower() and "_" in text and not text.startswith("_")
