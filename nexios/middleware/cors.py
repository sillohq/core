import re
import typing
from typing import Any, Callable, Dict, List, Optional

from nexios.config import get_config
from nexios.http import Request, Response
from nexios.logging import getLogger

# from typing_extensions import Annotated, Doc
from nexios.middleware.base import BaseMiddleware

logger = getLogger()

ALL_METHODS = ("delete", "get", "head", "options", "patch", "post", "put")
BASIC_HEADERS = {"Accept", "Accept-Language", "Content-Language", "Content-Type"}
SAFELISTED_HEADERS = {"accept", "accept-language", "content-language", "content-type"}


class CORSMiddleware(BaseMiddleware):
    def __init__(self):
        config = get_config().cors

        if not config:
            return None
        self.config = config
        self.allow_origins: List[str] = config.allow_origins or []
        self.blacklist_origins: List[str] = config.blacklist_origins or []
        self.allow_methods = config.allow_methods or ALL_METHODS
        self.blacklist_headers: List[str] = config.blacklist_headers or []
        self.allow_credentials = (
            config.allow_credentials if config.allow_credentials is not None else True
        )

        self.allow_origin_regex = (
            re.compile(config.allow_origin_regex) if config.allow_origin_regex else None
        )
        self.expose_headers: List[str] = config.expose_headers or []
        self.max_age = config.max_age or 600
        self.strict_origin_checking = config.strict_origin_checking or False
        self.dynamic_origin_validator: Optional[Callable[[Optional[str]], bool]] = (
            getattr(config, "dynamic_origin_validator", None)
        )
        self.debug = config.debug or False
        self.custom_error_status = config.custom_error_status or 400
        self.custom_error_messages: Dict[str, Any] = config.custom_error_messages or {}

        self.simple_headers: Dict[str, Any] = {}
        if self.allow_credentials:
            self.simple_headers["Access-Control-Allow-Credentials"] = "true"
        if self.expose_headers:
            self.simple_headers["Access-Control-Expose-Headers"] = ", ".join(
                self.expose_headers
            )

        self.preflight_headers = {
            "Access-Control-Allow-Methods": ", ".join(
                [x.upper() for x in self.allow_methods]
            ),
            "Access-Control-Max-Age": str(self.max_age),
        }
        if self.allow_credentials:
            self.preflight_headers["Access-Control-Allow-Credentials"] = "true"
        if config.allow_headers:
            self.allow_headers: List[str] = [
                *list(SAFELISTED_HEADERS),
                *(config.allow_headers or []),
            ]
        else:
            self.allow_headers = list(SAFELISTED_HEADERS)

    async def process_request(
        self,
        request: Request,
        response: Response,
        call_next: typing.Callable[..., typing.Awaitable[Any]],
    ):
        config = get_config().cors

        if not config:
            await call_next()
            return
        origin = request.origin

        method = request.scope["method"]

        if not origin and self.strict_origin_checking:
            if self.debug:
                logger.error("Request denied: Missing 'Origin' header.")
            return response.json(
                self.get_error_message("missing_origin"),
                status_code=self.custom_error_status,
            )
        if (
            method.lower() == "options"
            and "access-control-request-method" in request.headers
        ):
            return await self.preflight_response(request, response)
        await self.simple_response(request, response, call_next)

    async def simple_response(
        self,
        request: Request,
        response: Response,
        call_next: typing.Callable[..., typing.Awaitable[Any]],
    ):
        config = get_config().cors
        origin = request.origin
        if not config:
            return None
        server_error_headers = request.scope.get("server_error_headers", {})
        server_error_headers["Access-Control-Allow-Origin"] = origin
        request.scope["server_error_headers"] = server_error_headers
        await call_next()

        if origin and self.is_allowed_origin(origin):
            response.set_header("Access-Control-Allow-Origin", origin, overide=True)

            if self.allow_credentials:
                response.set_header(
                    "Access-Control-Allow-Credentials", "true", overide=True
                )

        if self.expose_headers:
            response.set_header(
                "Access-Control-Expose-Headers",
                ", ".join(self.expose_headers),
                overide=True,
            )

    def is_allowed_origin(self, origin: Optional[str]) -> bool:

        if origin in self.blacklist_origins:
            if self.debug:
                logger.error(f"Request denied: Origin '{origin}' is blacklisted.")

            return False

        if "*" in self.allow_origins:
            return True
        try:
            if self.allow_origin_regex and self.allow_origin_regex.fullmatch(origin):
                return True
        except re.error:
            return False

        if self.dynamic_origin_validator and callable(self.dynamic_origin_validator):
            return self.dynamic_origin_validator(origin)

        return origin in self.allow_origins

    def is_allowed_method(self, method: Optional[str]) -> bool:
        if not method or method.strip() == "":
            return False
        if "*" in self.allow_methods:
            return True
        if method.lower() not in [x.lower() for x in self.allow_methods]:
            return False
        return True

    async def preflight_response(self, request: Request, response: Response) -> Any:
        origin = request.headers.get("origin")
        requested_method = request.headers.get("access-control-request-method")
        requested_headers = request.headers.get("access-control-request-headers")

        headers = {}

        if not self.is_allowed_origin(origin):
            if self.debug:
                logger.error(
                    f"Preflight request denied: Origin '{origin}' is not allowed."
                )
            return response.json(
                self.get_error_message("disallowed_origin"),
                status_code=self.custom_error_status,
            )

        headers["Access-Control-Allow-Origin"] = origin  # type:ignore

        if not self.is_allowed_method(requested_method):
            if self.debug:
                logger.error(
                    f"Preflight request denied: Method '{requested_method}' is not allowed."
                )
            return response.json(
                self.get_error_message("disallowed_method"),
                status_code=self.custom_error_status,
            )

        if requested_method:
            headers["Access-Control-Allow-Methods"] = requested_method.upper()

        if requested_headers:
            requested_header_list = [
                h.strip().lower() for h in requested_headers.split(",")
            ]

            allowed_requested_headers = []
            for header in requested_header_list:
                # If allow_headers is "*", allow any header (except blacklisted)
                if "*" in self.allow_headers:
                    if header in self.blacklist_headers:
                        if self.debug:
                            logger.error(
                                f"Preflight request denied: Header '{header}' is blacklisted."
                            )
                        return response.json(
                            self.get_error_message("disallowed_header"),
                            status_code=self.custom_error_status,
                        )
                else:
                    if (
                        header not in [x.lower() for x in self.allow_headers]
                        or header in self.blacklist_headers
                    ):
                        if self.debug:
                            logger.error(
                                f"Preflight request denied: Header '{header}' is not allowed."
                            )
                        return response.json(
                            self.get_error_message("disallowed_header"),
                            status_code=self.custom_error_status,
                        )
                allowed_requested_headers.append(header)

            if allowed_requested_headers:
                headers["Access-Control-Allow-Headers"] = ", ".join(
                    allowed_requested_headers
                )

        headers["Access-Control-Max-Age"] = str(self.max_age)
        if self.allow_credentials:
            headers["Access-Control-Allow-Credentials"] = "true"

        return response.json("OK", status_code=201, headers=headers)

    def get_error_message(self, error_type: str) -> str:
        if not self.custom_error_messages:
            return "CORS request denied."
        return self.custom_error_messages.get(error_type, "CORS request denied.")
