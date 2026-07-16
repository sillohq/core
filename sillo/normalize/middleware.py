from __future__ import annotations

from enum import Enum
from typing import Any
from urllib.parse import urlunparse

from sillo.http import Request, Response
from sillo.middleware.base import BaseMiddleware


class SlashAction(Enum):
    ADD = "add"
    REMOVE = "remove"
    REDIRECT_ADD = "redirect_add"
    REDIRECT_REMOVE = "redirect_remove"
    IGNORE = "ignore"


class NormalizeMiddleware(BaseMiddleware):
    def __init__(
        self,
        *,
        slash_action: SlashAction = SlashAction.REDIRECT_REMOVE,
        redirect_status_code: int = 301,
        auto_remove_double_slashes: bool = True,
        normalize_case: bool = False,
        **_: Any,
    ) -> None:
        self.slash_action = slash_action
        self.redirect_status_code = redirect_status_code
        self.auto_remove_double_slashes = auto_remove_double_slashes
        self.normalize_case = normalize_case

    def _normalize_path(self, path: str) -> str:
        if self.auto_remove_double_slashes:
            while "//" in path:
                path = path.replace("//", "/")
        if self.normalize_case:
            path = path.lower()
        return path

    def _has_trailing_slash(self, path: str) -> bool:
        return len(path) > 1 and path.endswith("/")

    def _add_trailing_slash(self, path: str) -> str:
        if not self._has_trailing_slash(path):
            path += "/"
        return path

    def _remove_trailing_slash(self, path: str) -> str:
        if self._has_trailing_slash(path):
            path = path[:-1]
        return path

    def _should_skip_processing(self, path: str) -> bool:
        skip_patterns = [".", "?", "#"]
        return any(pattern in path for pattern in skip_patterns)

    async def process_request(
        self,
        request: Request,
        response: Response,
        call_next: Any,
    ) -> Any:
        original_path = request.url.path

        if self._should_skip_processing(original_path):
            return await call_next()

        normalized_path = self._normalize_path(original_path)

        if normalized_path != original_path and self.slash_action in (
            SlashAction.IGNORE,
            SlashAction.ADD,
            SlashAction.REMOVE,
        ):
            request.scope["path"] = normalized_path

        if self.slash_action == SlashAction.ADD:
            if not self._has_trailing_slash(normalized_path):
                request.scope["path"] = self._add_trailing_slash(normalized_path)

        elif self.slash_action == SlashAction.REMOVE:
            if self._has_trailing_slash(normalized_path):
                request.scope["path"] = self._remove_trailing_slash(normalized_path)

        elif self.slash_action in (
            SlashAction.REDIRECT_ADD,
            SlashAction.REDIRECT_REMOVE,
        ):
            should_redirect = False
            redirect_path = normalized_path

            if self.slash_action == SlashAction.REDIRECT_ADD:
                if not self._has_trailing_slash(normalized_path):
                    redirect_path = self._add_trailing_slash(normalized_path)
                    should_redirect = True
            elif self.slash_action == SlashAction.REDIRECT_REMOVE:
                if self._has_trailing_slash(normalized_path):
                    redirect_path = self._remove_trailing_slash(normalized_path)
                    should_redirect = True

            if should_redirect:
                redirect_url = urlunparse(
                    (
                        request.url.scheme,
                        request.url.netloc,
                        redirect_path,
                        request.path_params,
                        request.url.query,
                        request.url.fragment,
                    )
                )
                return response.redirect(
                    redirect_url, status_code=self.redirect_status_code
                )

        return await call_next()


def Normalize(
    slash_action: SlashAction = SlashAction.REDIRECT_REMOVE,
    auto_remove_double_slashes: bool = True,
    redirect_status_code: int = 301,
    normalize_case: bool = False,
) -> NormalizeMiddleware:
    return NormalizeMiddleware(
        slash_action=slash_action,
        auto_remove_double_slashes=auto_remove_double_slashes,
        redirect_status_code=redirect_status_code,
        normalize_case=normalize_case,
    )
