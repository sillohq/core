from __future__ import annotations

from enum import Enum
from typing import Any
from urllib.parse import urlunparse

from sillo.core.http import Request, Response
from sillo.middleware.base import BaseMiddleware


class SlashAction(Enum):
    """
    Enumeration of available trailing slash normalization strategies.

    Defines the different behaviors that the normalize middleware can apply
    when processing trailing slashes in URL paths. Actions range from simple
    in-place modification to HTTP redirect responses that inform the client
    of the canonical URL form.

    Attributes:
        ADD: Silently adds a trailing slash to the path without redirecting.
        REMOVE: Silently removes a trailing slash from the path without redirecting.
        REDIRECT_ADD: Issues an HTTP redirect to a URL with a trailing slash added.
        REDIRECT_REMOVE: Issues an HTTP redirect to a URL with the trailing slash removed.
        IGNORE: Takes no action on trailing slashes, leaving the path unchanged.
    """

    ADD = "add"
    REMOVE = "remove"
    REDIRECT_ADD = "redirect_add"
    REDIRECT_REMOVE = "redirect_remove"
    IGNORE = "ignore"


class NormalizeMiddleware(BaseMiddleware):
    """
    Middleware that normalizes URL paths by handling trailing slashes and double slashes.

    This middleware intercepts incoming HTTP requests and applies URL normalization
    rules to the request path before it reaches the route handler. It supports
    multiple strategies for handling trailing slashes including silent modification,
    HTTP redirects, and ignoring. Additionally, it can collapse consecutive slashes
    and optionally normalize path case for case-insensitive routing.

    The middleware integrates with the sillo middleware system by extending
    ``BaseMiddleware`` and overriding the ``process_request`` hook to modify
    the request scope before downstream processing.
    """

    def __init__(
        self,
        *,
        slash_action: SlashAction = SlashAction.REDIRECT_REMOVE,
        redirect_status_code: int = 301,
        auto_remove_double_slashes: bool = True,
        normalize_case: bool = False,
        **_: Any,
    ) -> None:
        """
        Initializes the normalize middleware with URL normalization configuration.

        Configures the middleware with the desired trailing slash handling strategy,
        the HTTP status code to use for redirect responses, and options for
        automatic double-slash removal and case normalization.

        Args:
            slash_action (SlashAction): The strategy to apply for trailing slash
                handling. Defaults to ``SlashAction.REDIRECT_REMOVE`` which issues
                a redirect to the URL without a trailing slash.
            redirect_status_code (int): The HTTP status code to use when issuing
                redirect responses. Defaults to 301 (permanent redirect).
            auto_remove_double_slashes (bool): Whether to automatically collapse
                consecutive slashes in the path into a single slash. Defaults to True.
            normalize_case (bool): Whether to convert the path to lowercase for
                case-insensitive routing. Defaults to False.
            **_ (Any): Additional keyword arguments that are accepted but ignored,
                allowing compatibility with generic middleware configuration patterns.
        """
        self.slash_action = slash_action
        self.redirect_status_code = redirect_status_code
        self.auto_remove_double_slashes = auto_remove_double_slashes
        self.normalize_case = normalize_case

    def _normalize_path(self, path: str) -> str:
        """
        Applies configured normalization rules to a URL path string.

        Processes the path by collapsing consecutive double slashes into single
        slashes if auto-removal is enabled, and optionally converts the path
        to lowercase if case normalization is configured. These transformations
        are applied in sequence to produce a clean, normalized path.

        Args:
            path (str): The raw URL path string to normalize according to the
                middleware configuration settings.

        Returns:
            str: The normalized path string with double slashes collapsed and
            case adjusted according to the middleware configuration.
        """
        if self.auto_remove_double_slashes:
            while "//" in path:
                path = path.replace("//", "/")
        if self.normalize_case:
            path = path.lower()
        return path

    def _has_trailing_slash(self, path: str) -> bool:
        """
        Checks whether the given URL path ends with a trailing forward slash.

        Evaluates the path to determine if it contains a trailing slash, with
        the special case that a root path of exactly ``/`` is not considered
        to have a trailing slash since removing it would produce an empty string.

        Args:
            path (str): The URL path string to inspect for a trailing slash.

        Returns:
            bool: True if the path is longer than one character and ends with
            a forward slash, False otherwise.
        """
        return len(path) > 1 and path.endswith("/")

    def _add_trailing_slash(self, path: str) -> str:
        """
        Appends a trailing forward slash to the path if one is not already present.

        Ensures the URL path ends with a trailing slash by appending one if
        the path does not already have one. Paths that already end with a
        slash are returned unchanged.

        Args:
            path (str): The URL path string to which a trailing slash should
                be conditionally appended.

        Returns:
            str: The path string guaranteed to end with a forward slash.
        """
        if not self._has_trailing_slash(path):
            path += "/"
        return path

    def _remove_trailing_slash(self, path: str) -> str:
        """
        Removes a trailing forward slash from the path if one is present.

        Strips the trailing slash character from the end of the URL path
        if one exists. Paths without a trailing slash are returned unchanged.

        Args:
            path (str): The URL path string from which a trailing slash
                should be conditionally removed.

        Returns:
            str: The path string with any trailing forward slash removed.
        """
        if self._has_trailing_slash(path):
            path = path[:-1]
        return path

    def _should_skip_processing(self, path: str) -> bool:
        """
        Determines whether URL normalization should be skipped for the given path.

        Checks the path against a set of patterns that indicate special URL
        components such as file extensions, query strings, or fragment identifiers.
        Paths matching these patterns are excluded from normalization to prevent
        corruption of these URL components.

        Args:
            path (str): The URL path string to evaluate for skip eligibility.

        Returns:
            bool: True if the path contains characters indicating it should
            bypass normalization processing, False otherwise.
        """
        skip_patterns = [".", "?", "#"]
        return any(pattern in path for pattern in skip_patterns)

    async def process_request(
        self,
        request: Request,
        response: Response,
        call_next: Any,
    ) -> Any:
        """
        Processes an incoming HTTP request by applying URL normalization rules.

        This method implements the core normalization logic by inspecting the
        request path and applying the configured slash handling strategy. It
        first checks whether the path should be skipped, then applies double-slash
        removal and case normalization. Based on the configured ``slash_action``,
        it either silently modifies the path in the request scope or issues an
        HTTP redirect response to the canonical URL form.

        Args:
            request (Request): The incoming HTTP request object whose URL path
                will be inspected and potentially modified during normalization.
            response (Response): The HTTP response object used to construct
                redirect responses when the slash action requires redirection.
            call_next (Any): An async callable representing the next middleware
                or route handler in the processing chain.

        Returns:
            Any: Either a redirect response if the path requires canonicalization
            via redirect, or the result of calling the next handler in the chain.
        """
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
                        # The `params` slot is a URL path's `;key=value`
                        # segment, not the route's captured parameters.
                        # `request.path_params` is a dict, and passing a
                        # populated one raises "Cannot mix str and non-str
                        # arguments". It is empty here only because this
                        # middleware runs before routing fills it in.
                        "",
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
    """
    Factory function that creates a configured NormalizeMiddleware instance.

    Provides a convenient shorthand for instantiating the normalize middleware
    with the specified URL normalization settings. This function simplifies
    middleware registration by allowing configuration through a simple function
    call rather than requiring explicit class instantiation.

    Args:
        slash_action (SlashAction): The trailing slash handling strategy to apply.
            Defaults to ``SlashAction.REDIRECT_REMOVE``.
        auto_remove_double_slashes (bool): Whether to collapse consecutive slashes
            in the URL path. Defaults to True.
        redirect_status_code (int): The HTTP status code for redirect responses.
            Defaults to 301 (permanent redirect).
        normalize_case (bool): Whether to convert paths to lowercase for
            case-insensitive routing. Defaults to False.

    Returns:
        NormalizeMiddleware: A fully configured middleware instance ready to be
        registered in the application middleware stack.
    """
    return NormalizeMiddleware(
        slash_action=slash_action,
        auto_remove_double_slashes=auto_remove_double_slashes,
        redirect_status_code=redirect_status_code,
        normalize_case=normalize_case,
    )
