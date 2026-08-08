import re
import typing
from dataclasses import dataclass
from enum import Enum
from re import Pattern

from sillo.core.converters import CONVERTOR_TYPES, Convertor

PARAM_REGEX = re.compile("{([a-zA-Z_][a-zA-Z0-9_]*)(:[a-zA-Z_][a-zA-Z0-9_]*)?}")


class RouteType(Enum):
    """
    Enumeration of supported route matching strategies.

    Defines the different types of route patterns that the routing system
    can compile and match against incoming request paths. Each route type
    corresponds to a specific regex compilation strategy and parameter
    extraction mechanism.

    Attributes:
        REGEX: A route pattern that uses regular expression matching for
            complex path matching scenarios with custom regex constraints.
        PATH: A standard path-based route pattern using curly-brace parameter
            syntax (e.g., ``/users/{id:int}``) with automatic regex compilation.
        WILDCARD: A catch-all route pattern that matches any remaining path
            segments, typically used for SPA fallback or static file serving.
    """

    REGEX = "regex"
    PATH = "path"
    WILDCARD = "wildcard"


def replace_params(
    path: str,
    param_convertors: dict[str, Convertor[typing.Any]],
    path_params: dict[str, str],
) -> tuple[str, dict[str, str]]:
    """
    Substitute path parameter placeholders with their concrete values.

    Iterates over the provided path parameters and replaces any matching
    ``{key}`` placeholders found in the path template string. Each value is
    first converted to its string representation using the corresponding
    convertor from the ``param_convertors`` mapping. Consumed parameters
    are removed from the ``path_params`` dictionary so that callers can
    detect which parameters remain unresolved.

    Args:
        path: The URL path template containing ``{key}`` placeholders that
            should be replaced with actual parameter values.
        param_convertors: A dictionary mapping parameter names to their
            associated ``Convertor`` instances, which handle type-to-string
            serialization for each path parameter.
        path_params: A mutable dictionary of parameter names to their raw
            string values. Parameters that are successfully substituted
            into the path are removed from this dictionary in-place.

    Returns:
        A two-element tuple where the first element is the path string with
        all matched placeholders replaced by their string values, and the
        second element is the remaining ``path_params`` dictionary with
        consumed parameters removed.

    Example::

        convertors = {"user_id": StringConvertor()}
        params = {"user_id": "42", "extra": "value"}
        new_path, remaining = replace_params(
            "/users/{user_id}", convertors, params
        )
        # new_path == "/users/42", remaining == {"extra": "value"}
    """
    for key, value in list(path_params.items()):
        if "{" + key + "}" in path:
            convertor = param_convertors[key]
            value = convertor.to_string(value)
            path = path.replace("{" + key + "}", value)
            path_params.pop(key)
    return path, path_params


def compile_path(
    path: str,
) -> tuple[typing.Pattern[str], RouteType, dict[str, Convertor[typing.Any]], list[str]]:
    """
    Compile a URL path template into a regex pattern with parameter convertors.

    Parses a path string containing ``{param_name:type}`` placeholders and
    produces a compiled regular expression for matching incoming request
    paths, along with metadata about the discovered parameters and their
    type convertors. Supports both URL paths (starting with ``/``) and host
    patterns (e.g., ``{subdomain}.example.com``).

    The function iterates through all parameter placeholders found in the
    path, looks up the appropriate convertor for each declared type, and
    builds a named-group regex pattern. Duplicate parameter names are
    detected and raise a ``ValueError``.

    Args:
        path: The URL path template string to compile. May contain parameter
            placeholders in the form ``{name}`` or ``{name:type}`` where
            ``type`` corresponds to a registered convertor name (e.g.,
            ``str``, ``int``, ``path``). Paths starting with ``/`` are
            treated as URL paths; all others are treated as host patterns.

    Returns:
        A four-element tuple consisting of:
            - ``pattern``: A compiled ``re.Pattern`` for matching request paths.
            - ``route_type``: The string format of the path with normalized
              parameter placeholders (e.g., ``/users/{user_id}``).
            - ``param_convertors``: A dictionary mapping parameter names to
              their ``Convertor`` instances for type coercion.
            - ``param_names``: An ordered list of parameter names as they
              appear in the path template.

    Raises:
        AssertionError: If a parameter type convertor name is not found in
            the ``CONVERTOR_TYPES`` registry.
        ValueError: If duplicate parameter names are detected in the path.

    Example::

        pattern, fmt, convertors, names = compile_path("/users/{user_id:int}")
        # pattern matches "/users/42", names == ["user_id"]
    """
    is_host = not path.startswith("/")

    path_regex = "^"
    path_format = ""
    duplicated_params: set[typing.Any] = set()

    idx = 0
    param_convertors = {}
    param_names: list[str] = []
    for match in PARAM_REGEX.finditer(path):
        param_name, convertor_type = match.groups("str")
        convertor_type = convertor_type.lstrip(":")
        assert convertor_type in CONVERTOR_TYPES, (
            f"Unknown path convertor '{convertor_type}'"
        )
        convertor = CONVERTOR_TYPES[convertor_type]

        path_regex += re.escape(path[idx : match.start()])
        path_regex += f"(?P<{param_name}>{convertor.regex})"
        path_format += path[idx : match.start()]
        path_format += f"{{{param_name}}}"

        if param_name in param_convertors:
            duplicated_params.add(param_name)

        param_convertors[param_name] = convertor

        idx = match.end()
        param_names.append(param_name)

    if duplicated_params:
        names = ", ".join(sorted(duplicated_params))
        ending = "s" if len(duplicated_params) > 1 else ""
        raise ValueError(f"Duplicated param name{ending} {names} at path {path}")

    if is_host:
        hostname = path[idx:].split(":")[0]
        path_regex += re.escape(hostname) + "$"
    else:
        path_regex += re.escape(path[idx:]) + "$"
    path_format += path[idx:]

    return re.compile(path_regex), path_format, param_convertors, param_names  # type: ignore


@dataclass
class RoutePattern:
    """
    Represents a fully processed and compiled route pattern with metadata.

    This dataclass holds all the information needed to match incoming request
    paths against a route template and extract typed path parameters. It is
    produced by ``RouteBuilder.create_pattern`` and consumed by the routing
    layer during request dispatch.

    Attributes:
        pattern: A compiled regular expression pattern used to match incoming
            request URL paths against this route's template.
        raw_path: The original unmodified path template string as provided
            during route registration (e.g., ``"/users/{user_id:int}"``).
        param_names: An ordered list of parameter names extracted from the
            path template, preserving their declaration order.
        route_type: The normalized path format string with parameter placeholders
            (e.g., ``"/users/{user_id}"``), also serving as the route type
            identifier for display and debugging purposes.
        convertor: A dictionary mapping parameter names to their corresponding
            ``Convertor`` instances, which handle type coercion between URL
            path segments and Python objects.
    """

    pattern: Pattern[str]
    raw_path: str
    param_names: list[str]
    route_type: RouteType
    convertor: dict[str, Convertor[typing.Any]]


class RouteBuilder:
    """
    Factory for creating compiled route patterns from path template strings.

    Provides static methods to transform human-readable URL path templates
    (e.g., ``"/users/{user_id:int}"``) into ``RoutePattern`` instances that
    contain compiled regex patterns, parameter convertors, and metadata
    needed for efficient request matching and parameter extraction at runtime.

    This class serves as the primary entry point for the routing subsystem
    to convert declarative route definitions into optimized matching objects.
    """

    @staticmethod
    def create_pattern(path: str) -> RoutePattern:
        """
        Create a compiled RoutePattern from a URL path template string.

        Delegates to ``compile_path`` to parse the path template, extract
        parameter definitions, and build a compiled regex pattern. The
        resulting ``RoutePattern`` is ready for use by the routing layer
        to match incoming requests and extract typed path parameters.

        Args:
            path: The URL path template string to compile. Supports parameter
                placeholders in ``{name}`` or ``{name:type}`` syntax, where
                ``type`` refers to a registered convertor (e.g., ``str``,
                ``int``, ``path``).

        Returns:
            A fully populated ``RoutePattern`` instance containing the compiled
            regex pattern, raw path, parameter names, route type, and parameter
            convertors needed for request matching and extraction.

        Example::

            pattern = RouteBuilder.create_pattern("/users/{user_id:int}/posts/{post_id}")
            # pattern.pattern matches "/users/42/posts/7"
            # pattern.param_names == ["user_id", "post_id"]
        """
        path_regex, path_format, param_convertors, param_names = compile_path(path)
        return RoutePattern(
            pattern=path_regex,
            raw_path=path,
            param_names=param_names,
            route_type=path_format,
            convertor=param_convertors,
        )
