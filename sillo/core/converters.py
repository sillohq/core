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
    """Base class for URL path parameter type converters.

    This abstract base class defines the interface that all URL path converters
    must implement. Converters are responsible for transforming string values
    extracted from URL paths into typed Python objects, and vice versa for URL
    generation. The framework uses these converters to support typed route
    parameters such as integers, floats, UUIDs, and custom types.

    Subclasses must set the ``regex`` class variable to a regular expression
    pattern that matches valid URL path segments for the target type, and must
    implement both ``convert`` and ``to_string`` methods.

    Attributes:
        regex: A class-level regular expression string that defines which URL
            path segments are valid for this converter type. The routing system
            uses this pattern to match incoming request paths.

    Note:
        This class is generic over type ``T``, where ``T`` represents the Python
        type that the converter produces. Custom converters should subclass
        ``Convertor[YourType]`` to maintain type safety.
    """

    regex: typing.ClassVar[str] = ""

    def convert(self, value: str) -> T:
        """Convert a string URL path segment to the target typed value.

        Takes a raw string extracted from a URL path segment and converts it
        into an instance of the target type ``T``. This method is called by the
        routing system when a request matches a route that uses this converter
        type for one of its path parameters.

        Args:
            value: The raw string value extracted from the URL path segment.
                This value is guaranteed to match the converter's ``regex``
                pattern, but may still fail conversion if the regex is not
                sufficiently strict.

        Returns:
            The converted value as an instance of type ``T``.

        Raises:
            NotImplementedError: If the subclass does not override this method.
                All concrete converter subclasses must provide an implementation.

        Note:
            Subclasses should handle any conversion errors gracefully. The
            routing system assumes that if a value matches the regex, it can
            be successfully converted.
        """
        raise NotImplementedError()  # pragma: no cover

    def to_string(self, value: T) -> str:
        """Convert a typed value back to a string for URL generation.

        Takes a value of the target type ``T`` and produces its string
        representation suitable for inclusion in a URL path. This method is
        used by the URL reverse-generation system (e.g., ``url_for``) to build
        URLs from route names and parameter values.

        Args:
            value: The typed value to convert to a URL-safe string. The type
                of this value should match the converter's target type ``T``.

        Returns:
            A string representation of the value that is safe for inclusion
            in a URL path segment and matches the converter's ``regex`` pattern.

        Raises:
            NotImplementedError: If the subclass does not override this method.
                All concrete converter subclasses must provide an implementation.

        Note:
            The returned string must not contain forward slashes, as these are
            used as path segment delimiters by the routing system.
        """
        raise NotImplementedError()  # pragma: no cover


class StringConvertor(Convertor[str]):
    """Converter for standard string path parameters in URL routes.

    This converter handles string-type path segments that do not contain forward
    slashes. It is the default converter used for ``{param:str}`` style route
    parameters. The regex pattern matches any non-empty sequence of characters
    except the path separator ``/``.

    Attributes:
        regex: Matches one or more characters that are not forward slashes,
            ensuring the captured segment represents a single path component.

    Note:
        The ``to_string`` method enforces that the value does not contain path
        separators and is not empty. These assertions guard against malformed
        URLs being generated during reverse URL resolution.
    """

    regex = "[^/]+"

    def convert(self, value: str) -> str:
        """Convert a URL path string segment by returning it as-is.

        Since the target type is already ``str``, this method performs a
        passthrough conversion. The routing system guarantees that the input
        value matches the ``regex`` pattern before this method is called.

        Args:
            value: The raw string value from the URL path segment. This value
                has already been validated against the regex pattern ``[^/]+``.

        Returns:
            The same string value unchanged, since no type transformation is
            needed for string path parameters.

        Note:
            This is an identity function. It exists to maintain a consistent
            converter interface across all path parameter types.
        """
        return value

    def to_string(self, value: str) -> str:
        """Convert a string value to a URL-safe path segment string.

        Validates that the string does not contain forward slashes and is not
        empty, then returns it for inclusion in a generated URL path.

        Args:
            value: The string value to include in a URL path segment. Must not
                contain ``/`` characters and must be non-empty.

        Returns:
            The validated string value suitable for URL path inclusion.

        Raises:
            AssertionError: If the value contains a forward slash character or
                if the value is an empty string.

        Note:
            The assertions here are safety guards. In normal operation, values
            should already be valid, but these checks prevent silently generating
            malformed URLs.
        """
        value = str(value)
        assert "/" not in value, "May not contain path separators"
        assert value, "Must not be empty"
        return value


class PathConvertor(Convertor[str]):
    """Converter for wildcard path parameters that match across multiple segments.

    Unlike ``StringConvertor``, this converter matches the remainder of the URL
    path including any forward slashes. It is used for catch-all or wildcard
    route parameters such as ``{path:path}`` that need to capture an entire
    sub-path rather than a single segment.

    Attributes:
        regex: The pattern ``.*`` matches zero or more of any character,
            including forward slashes, allowing multi-segment path capture.

    Note:
        Because this converter matches everything, routes using it should be
        placed after more specific routes to avoid shadowing them. The greedy
        nature of the ``.*`` pattern means it will consume all remaining path
        segments.
    """

    regex = ".*"

    def convert(self, value: str) -> str:
        """Convert a multi-segment URL path by returning it as-is.

        This is a passthrough conversion since the target type is ``str``. The
        value may contain forward slashes, distinguishing it from the
        ``StringConvertor`` which only handles single path segments.

        Args:
            value: The raw string value from the URL path, potentially
                containing multiple path segments separated by ``/`` characters.

        Returns:
            The same string value unchanged, preserving all path separators
            and segment structure.

        Note:
            This is an identity function that exists to maintain a consistent
            converter interface across all path parameter types.
        """
        return value

    def to_string(self, value: str) -> str:
        """Convert a path value back to its string representation for URL generation.

        Returns the value as-is since it is already a string. Unlike
        ``StringConvertor.to_string``, this method does not assert the absence
        of forward slashes, because path converters are expected to handle
        multi-segment paths.

        Args:
            value: The path string to include in a generated URL. May contain
                forward slashes for multi-segment paths.

        Returns:
            The string value unchanged, suitable for direct inclusion in a
            generated URL path.

        Note:
            No validation is performed on the value. Callers are responsible
            for ensuring the value is a well-formed path string.
        """
        return value


class IntegerConvertor(Convertor[int]):
    """Converter for integer path parameters in URL routes.

    This converter handles numeric path segments that represent non-negative
    integers. It is used for route parameters typed as ``int``, such as
    ``{item_id:int}``. The regex pattern matches one or more ASCII digits
    without any sign prefix, meaning only non-negative integers are supported.

    Attributes:
        regex: The pattern ``[0-9]+`` matches one or more ASCII digit characters,
            ensuring only non-negative integer strings are captured from the URL.

    Note:
        Negative integers are not supported in URL path parameters by this
        converter. If negative values are needed, consider using a query
        parameter or a different routing approach.
    """

    regex = "[0-9]+"

    def convert(self, value: str) -> int:
        """Convert a numeric string from a URL path to an integer value.

        Parses the string representation of a non-negative integer into a
        Python ``int`` object. The input is guaranteed to consist only of
        ASCII digit characters due to the regex constraint.

        Args:
            value: A string of one or more ASCII digits extracted from the
                URL path segment. Guaranteed to match ``[0-9]+``.

        Returns:
            The parsed integer value corresponding to the input string.

        Raises:
            ValueError: If the string cannot be parsed as an integer. This
                should not occur in practice due to regex validation, but is
                listed for completeness.

        Note:
            Leading zeros are accepted (e.g., ``"007"`` becomes ``7``). The
            resulting integer is always non-negative.
        """
        return int(value)

    def to_string(self, value: int) -> str:
        """Convert an integer value to its string representation for URL generation.

        Validates that the integer is non-negative and returns its decimal
        string representation for inclusion in a generated URL path.

        Args:
            value: The integer value to convert. Must be non-negative.

        Returns:
            The decimal string representation of the integer, suitable for
            inclusion in a URL path segment.

        Raises:
            AssertionError: If the value is negative, since negative integers
                are not supported in URL path parameters.

        Note:
            The assertion prevents silently generating invalid URLs with
            negative numbers, which would not match the converter's regex
            pattern and could cause routing inconsistencies.
        """
        value = int(value)
        assert value >= 0, "Negative integers are not supported"
        return str(value)


class FloatConvertor(Convertor[float]):
    """Converter for floating-point path parameters in URL routes.

    This converter handles numeric path segments that represent non-negative
    floating-point numbers. It is used for route parameters typed as ``float``,
    such as ``{price:float}``. The regex pattern matches both integer-like and
    decimal number strings without a sign prefix.

    Attributes:
        regex: The pattern ``[0-9]+(\\.[0-9]+)?`` matches one or more digits
            optionally followed by a decimal point and one or more digits.
            This ensures only valid non-negative decimal number strings are
            captured from the URL path.

    Note:
        Negative floats, NaN, and infinity are not supported in URL path
        parameters. The ``to_string`` method explicitly validates against
        these cases. Output formatting uses up to 20 decimal places with
        trailing zeros stripped.
    """

    regex = r"[0-9]+(\.[0-9]+)?"

    def convert(self, value: str) -> float:
        """Convert a numeric string from a URL path to a float value.

        Parses the string representation of a non-negative decimal number into
        a Python ``float`` object. The input is guaranteed to match the float
        regex pattern due to routing-level validation.

        Args:
            value: A string representing a non-negative decimal number extracted
                from the URL path segment. Matches ``[0-9]+(\\.[0-9]+)?``.

        Returns:
            The parsed floating-point value corresponding to the input string.

        Raises:
            ValueError: If the string cannot be parsed as a float. This should
                not occur in practice due to regex validation, but is listed
                for completeness.

        Note:
            Both integer-like strings (``"42"``) and decimal strings (``"3.14"``)
            are accepted. The result is always a non-negative float.
        """
        return float(value)

    def to_string(self, value: float) -> str:
        """Convert a float value to its string representation for URL generation.

        Validates that the float is non-negative, not NaN, and not infinite,
        then produces a high-precision decimal string with trailing zeros
        stripped for clean URL output.

        Args:
            value: The floating-point value to convert. Must be non-negative,
                finite, and not NaN.

        Returns:
            A decimal string representation of the float with up to 20 decimal
            places and trailing zeros removed. For example, ``3.14`` becomes
            ``"3.14"`` and ``42.0`` becomes ``"42"``.

        Raises:
            AssertionError: If the value is negative, NaN, or infinite.

        Note:
            The 20-decimal-place precision ensures round-trip fidelity for
            IEEE 754 double-precision floats. Trailing zeros and unnecessary
            decimal points are stripped for cleaner URLs.
        """
        value = float(value)
        assert value >= 0.0, "Negative floats are not supported"
        assert not math.isnan(value), "NaN values are not supported"
        assert not math.isinf(value), "Infinite values are not supported"
        return (f"{value:0.20f}").rstrip("0").rstrip(".")


class UUIDConvertor(Convertor[uuid.UUID]):
    """Converter for UUID path parameters in URL routes.

    This converter handles universally unique identifier (UUID) path segments
    in standard hyphenated or unhyphenated hexadecimal format. It is used for
    route parameters typed as ``uuid.UUID``, such as ``{resource_id:uuid}``.
    UUIDs are commonly used as primary keys in database-backed applications.

    Attributes:
        regex: Matches the standard 8-4-4-4-12 hexadecimal UUID format with
            optional hyphens, supporting both ``550e8400-e29b-41d4-a716-446655440000``
            and ``550e8400e29b41d4a716446655440000`` styles.
    """

    regex = "[0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{12}"

    def convert(self, value: str) -> uuid.UUID:
        """Convert a UUID string from a URL path to a uuid.UUID object.

        Parses the string representation of a UUID into a Python ``uuid.UUID``
        instance. Accepts both hyphenated and unhyphenated formats since the
        regex allows optional hyphens between groups.

        Args:
            value: A hexadecimal string representing a UUID, optionally with
                hyphens separating the standard 8-4-4-4-12 groups.

        Returns:
            A ``uuid.UUID`` object representing the parsed UUID value.

        Raises:
            ValueError: If the string does not represent a valid UUID. This
                should be rare given the regex constraint, but could occur if
                the hex digits form an invalid UUID variant or version.

        Note:
            The resulting UUID object preserves the original version and variant
            information encoded in the hex digits.
        """
        return uuid.UUID(value)

    def to_string(self, value: uuid.UUID) -> str:
        """Convert a UUID object to its standard string representation for URL generation.

        Produces the canonical hyphenated lowercase string form of the UUID
        for inclusion in a generated URL path.

        Args:
            value: The ``uuid.UUID`` object to convert to a string.

        Returns:
            The standard hyphenated UUID string (e.g.,
            ``"550e8400-e29b-41d4-a716-446655440000"``).

        Note:
            The output always uses lowercase hexadecimal digits with hyphens,
            which is the canonical form produced by ``str(uuid.UUID(...))``.
        """
        return str(value)


class SlugConvertor(Convertor[str]):
    """Converter for slug-style path parameters in URL routes.

    This converter handles URL-friendly slug strings that consist of lowercase
    alphanumeric words separated by single hyphens. Slugs are commonly used in
    blog posts, article URLs, and SEO-friendly paths. The converter validates
    that the input strictly conforms to the slug format.

    Attributes:
        regex: The pattern ``[a-z0-9]+(?:-[a-z0-9]+)*`` matches one or more
            lowercase alphanumeric words joined by single hyphens. Leading,
            trailing, and consecutive hyphens are not permitted.

    Note:
        Unlike ``StringConvertor``, this converter performs strict validation
        in both ``convert`` and ``to_string`` methods. Values that do not
        conform to the slug format will raise ``ValueError`` rather than
        being silently accepted.
    """

    regex = r"[a-z0-9]+(?:-[a-z0-9]+)*"

    def convert(self, value: str) -> str:
        """Convert a slug string from a URL path with format validation.

        Validates that the input string strictly matches the slug format
        (lowercase alphanumeric words separated by single hyphens) and
        returns it if valid.

        Args:
            value: The string value from the URL path segment to validate
                as a slug. Must match ``[a-z0-9]+(?:-[a-z0-9]+)*``.

        Returns:
            The validated slug string, unchanged from the input.

        Raises:
            ValueError: If the value does not conform to the slug format.
                This includes strings with uppercase letters, special
                characters, leading/trailing hyphens, or consecutive hyphens.

        Note:
            Although the routing regex provides initial filtering, this method
            performs a redundant full-match validation to ensure data integrity.
        """
        if not re.fullmatch(self.regex, value):
            raise ValueError(f"Invalid slug format: {value}")
        return value

    def to_string(self, value: str) -> str:
        """Convert a value to slug format for URL generation with validation.

        Validates that the provided value is a properly formatted slug before
        returning it for inclusion in a generated URL path.

        Args:
            value: The string value to validate and include in a URL path.
                Must conform to the slug format.

        Returns:
            The validated slug string suitable for URL path inclusion.

        Raises:
            ValueError: If the value does not conform to the slug format.
                Prevents generating URLs with invalid slug segments.

        Note:
            This validation ensures that reverse URL generation never produces
            malformed slug segments, maintaining consistency between incoming
            route matching and outgoing URL construction.
        """
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
"""Default registry of built-in URL path converter instances.

This module-level dictionary maps converter type names to their singleton
converter instances. The routing system consults this registry when resolving
typed path parameters in route definitions. New converters can be added via
the :func:`register_url_convertor` function.

The following converter types are registered by default:
    - ``"str"``: :class:`StringConvertor` for single-segment string parameters.
    - ``"path"``: :class:`PathConvertor` for multi-segment wildcard paths.
    - ``"int"``: :class:`IntegerConvertor` for non-negative integer parameters.
    - ``"float"``: :class:`FloatConvertor` for non-negative float parameters.
    - ``"uuid"``: :class:`UUIDConvertor` for UUID parameters.
    - ``"slug"``: :class:`SlugConvertor` for URL-friendly slug parameters.
"""


def register_url_convertor(key: str, convertor: Convertor[typing.Any]) -> None:
    """Register a custom URL path converter in the global converter registry.

    Adds a new converter type to the ``CONVERTOR_TYPES`` registry, making it
    available for use in route path definitions. Once registered, the converter
    can be referenced by its key in route parameter type annotations, e.g.,
    ``{param:key}``.

    Args:
        key: The string name used to reference this converter in route path
            definitions. Must be a valid identifier that does not conflict
            with existing converter type names unless intentional overriding
            is desired.
        convertor: An instance of a ``Convertor`` subclass that implements
            the ``convert`` and ``to_string`` methods and defines a ``regex``
            pattern for URL path matching.

    Raises:
        No explicit exceptions are raised, but registering a key that already
        exists will silently overwrite the previous converter for that key.

    Note:
        This function modifies the module-level ``CONVERTOR_TYPES`` dictionary
        in place. It should typically be called during application setup before
        any routes are defined that reference the custom converter type.
        Registering a converter after routes are compiled may not take effect
        for those routes.
    """
    CONVERTOR_TYPES[key] = convertor
