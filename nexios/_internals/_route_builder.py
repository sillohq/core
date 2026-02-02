import re
import typing
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Pattern

from nexios.converters import CONVERTOR_TYPES, Convertor

PARAM_REGEX = re.compile("{([a-zA-Z_][a-zA-Z0-9_]*)(:[a-zA-Z_][a-zA-Z0-9_]*)?}")


class RouteType(Enum):
    REGEX = "regex"
    PATH = "path"
    WILDCARD = "wildcard"


def replace_params(
    path: str,
    param_convertors: dict[str, Convertor[typing.Any]],
    path_params: dict[str, str],
) -> tuple[str, dict[str, str]]:
    for key, value in list(path_params.items()):
        if "{" + key + "}" in path:
            convertor = param_convertors[key]
            value = convertor.to_string(value)
            path = path.replace("{" + key + "}", value)
            path_params.pop(key)
    return path, path_params


def compile_path(
    path: str,
) -> tuple[typing.Pattern[str], RouteType, dict[str, Convertor[typing.Any]], List[str]]:
    """
    Given a path string, like: "/{username:str}",
    or a host string, like: "{subdomain}.mydomain.org", return a three-tuple
    of (regex, format, {param_name:convertor}).

    regex:      "/(?P<username>[^/]+)"
    format:     "/{username}"
    convertors: {"username": StringConvertor()}
    """
    is_host = not path.startswith("/")

    path_regex = "^"
    path_format = ""
    duplicated_params: typing.Set[typing.Any] = set()

    idx = 0
    param_convertors = {}
    param_names: List[str] = []
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
        path_format += "{%s}" % param_name

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
    """Represents a processed route pattern with metadata"""

    pattern: Pattern[str]
    raw_path: str
    param_names: List[str]
    route_type: RouteType
    convertor: Dict[str, Convertor[typing.Any]]


class RouteBuilder:
    @staticmethod
    def create_pattern(path: str) -> RoutePattern:
        path_regex, path_format, param_convertors, param_names = (  # type: ignore
            compile_path(path)
        )
        return RoutePattern(
            pattern=path_regex,
            raw_path=path,
            param_names=param_names,
            route_type=path_format,
            convertor=param_convertors,
        )
