"""Type converters for URL path parameters.

Implemented from Starlette.
"""

from __future__ import annotations

import math
import re
import typing
import uuid

T = typing.TypeVar("T")


class Convertor(typing.Generic[T]):
    """Base class for URL path converters."""

    regex: typing.ClassVar[str] = ""

    def convert(self, value: str) -> T:
        """Convert a string URL value to the target type.

        Args:
            value: The string value from the URL path.

        Returns:
            The converted value.
        """
        raise NotImplementedError()  # pragma: no cover

    def to_string(self, value: T) -> str:
        """Convert a value back to a string for URL generation.

        Args:
            value: The value to convert.

        Returns:
            The string representation.
        """
        raise NotImplementedError()  # pragma: no cover


class StringConvertor(Convertor[str]):
    """Converter for string path parameters."""

    regex = "[^/]+"

    def convert(self, value: str) -> str:
        """Convert string (passthrough)."""
        return value

    def to_string(self, value: str) -> str:
        """Convert string to URL-safe string."""
        value = str(value)
        assert "/" not in value, "May not contain path separators"
        assert value, "Must not be empty"
        return value


class PathConvertor(Convertor[str]):
    """Converter for wildcard path parameters."""

    regex = ".*"

    def convert(self, value: str) -> str:
        """Convert path (passthrough)."""
        return value

    def to_string(self, value: str) -> str:
        """Convert path to string."""
        return value


class IntegerConvertor(Convertor[int]):
    """Converter for integer path parameters."""

    regex = "[0-9]+"

    def convert(self, value: str) -> int:
        """Convert string to integer."""
        return int(value)

    def to_string(self, value: int) -> str:
        """Convert integer to string."""
        value = int(value)
        assert value >= 0, "Negative integers are not supported"
        return str(value)


class FloatConvertor(Convertor[float]):
    """Converter for float path parameters."""

    regex = r"[0-9]+(\.[0-9]+)?"

    def convert(self, value: str) -> float:
        """Convert string to float."""
        return float(value)

    def to_string(self, value: float) -> str:
        """Convert float to string."""
        value = float(value)
        assert value >= 0.0, "Negative floats are not supported"
        assert not math.isnan(value), "NaN values are not supported"
        assert not math.isinf(value), "Infinite values are not supported"
        return ("%0.20f" % value).rstrip("0").rstrip(".")


class UUIDConvertor(Convertor[uuid.UUID]):
    """Converter for UUID path parameters."""

    regex = "[0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{12}"

    def convert(self, value: str) -> uuid.UUID:
        """Convert string to UUID."""
        return uuid.UUID(value)

    def to_string(self, value: uuid.UUID) -> str:
        """Convert UUID to string."""
        return str(value)


class SlugConvertor(Convertor[str]):
    """Converter for slugs (URL-friendly strings)."""

    regex = r"[a-z0-9]+(?:-[a-z0-9]+)*"

    def convert(self, value: str) -> str:
        """Convert string to slug, validating format."""
        if not re.fullmatch(self.regex, value):
            raise ValueError(f"Invalid slug format: {value}")
        return value

    def to_string(self, value: str) -> str:
        """Convert value to slug format."""
        if not re.fullmatch(self.regex, value):
            raise ValueError(f"Invalid slug format: {value}")
        return value


CONVERTOR_TYPES: dict[str, Convertor[typing.Any]] = {
    "str": StringConvertor(),
    "path": PathConvertor(),
    "int": IntegerConvertor(),
    "float": FloatConvertor(),
    "uuid": UUIDConvertor(),
    "slug": SlugConvertor(),
}


def register_url_convertor(key: str, convertor: Convertor[typing.Any]) -> None:
    """Register a custom URL path converter.

    Args:
        key: The converter type name (e.g., 'slug').
        convertor: The converter instance to register.
    """
    CONVERTOR_TYPES[key] = convertor
