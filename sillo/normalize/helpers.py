from __future__ import annotations

from enum import Enum
from typing import List
from urllib.parse import urlparse, urlunparse


def normalize_path(path: str, remove_double_slashes: bool = True) -> str:
    if remove_double_slashes:
        while "//" in path:
            path = path.replace("//", "/")
    path = path.strip()
    return path


def has_trailing_slash(path: str) -> bool:
    return len(path) > 1 and path.endswith("/")


def add_trailing_slash(path: str) -> str:
    if not has_trailing_slash(path):
        path += "/"
    return path


def remove_trailing_slash(path: str) -> str:
    if has_trailing_slash(path):
        path = path[:-1]
    return path


def should_skip_path_processing(path: str) -> bool:
    skip_patterns = [".", "?", "#"]
    return any(pattern in path for pattern in skip_patterns)


def build_normalized_url(
    base_url: str,
    path: str,
    preserve_query: bool = True,
    preserve_fragment: bool = True,
) -> str:
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


def get_path_segments(path: str) -> List[str]:
    path = path.strip("/")
    if not path:
        return []
    return path.split("/")


def join_path_segments(segments: List[str], trailing_slash: bool = False) -> str:
    path = "/" + "/".join(segments)
    if trailing_slash and not path.endswith("/"):
        path += "/"
    return path


def is_absolute_url(url: str) -> bool:
    parsed = urlparse(url)
    return bool(parsed.scheme and parsed.netloc)


def normalize_url(url: str, preserve_case: bool = True) -> str:
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
    return "//" in path
