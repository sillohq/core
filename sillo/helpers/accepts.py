from __future__ import annotations

from typing import Any, Dict, List, Optional

from sillo.http import Request, Response
from sillo.middleware.base import BaseMiddleware


class AcceptItem:
    def __init__(
        self, value: str, quality: float = 1.0, params: Optional[Dict[str, str]] = None
    ):
        self.value = value
        self.quality = quality
        self.params = params or {}

    def __repr__(self) -> str:
        return f"AcceptItem(value={self.value}, quality={self.quality})"


class AcceptsInfo:
    def __init__(self, request: Request):
        self.request = request
        self._parsed_accept = None
        self._parsed_accept_language = None
        self._parsed_accept_charset = None
        self._parsed_accept_encoding = None

    @property
    def accept(self) -> List[AcceptItem]:
        if self._parsed_accept is None:
            cached = getattr(self.request.state, "accepts_parsed", {})
            if cached:
                self._parsed_accept = cached.get("accept", [])
            else:
                self._parsed_accept = parse_accept_header(
                    self.request.headers.get("Accept", "")
                )
        return self._parsed_accept

    @property
    def accept_language(self) -> List[AcceptItem]:
        if self._parsed_accept_language is None:
            cached = getattr(self.request.state, "accepts_parsed", {})
            if cached:
                self._parsed_accept_language = cached.get("accept_language", [])
            else:
                self._parsed_accept_language = parse_accept_language(
                    self.request.headers.get("Accept-Language", "")
                )
        return self._parsed_accept_language

    @property
    def accept_charset(self) -> List[AcceptItem]:
        if self._parsed_accept_charset is None:
            cached = getattr(self.request.state, "accepts_parsed", {})
            if cached:
                self._parsed_accept_charset = cached.get("accept_charset", [])
            else:
                self._parsed_accept_charset = parse_accept_charset(
                    self.request.headers.get("Accept-Charset", "")
                )
        return self._parsed_accept_charset

    @property
    def accept_encoding(self) -> List[AcceptItem]:
        if self._parsed_accept_encoding is None:
            cached = getattr(self.request.state, "accepts_parsed", {})
            if cached:
                self._parsed_accept_encoding = cached.get("accept_encoding", [])
            else:
                self._parsed_accept_encoding = parse_accept_encoding(
                    self.request.headers.get("Accept-Encoding", "")
                )
        return self._parsed_accept_encoding

    def get_accepted_types(self) -> List[str]:
        return [item.value for item in self.accept if item.quality > 0]

    def get_accepted_languages(self) -> List[str]:
        return [item.value for item in self.accept_language if item.quality > 0]

    def get_accepted_charsets(self) -> List[str]:
        return [item.value for item in self.accept_charset if item.quality > 0]

    def get_accepted_encodings(self) -> List[str]:
        return [item.value for item in self.accept_encoding if item.quality > 0]


def parse_accept_header(accept_header: str) -> List[AcceptItem]:
    if not accept_header:
        return []
    items = []
    for part in accept_header.split(","):
        part = part.strip()
        if not part:
            continue
        quality = 1.0
        params: Dict[str, str] = {}
        if ";" in part:
            media_range, param_str = part.split(";", 1)
            media_range = media_range.strip()
            for param in param_str.split(";"):
                param = param.strip()
                if "=" in param:
                    key, value = param.split("=", 1)
                    key = key.strip().lower()
                    value = value.strip()
                    if key == "q":
                        try:
                            quality = max(0.0, min(1.0, float(value)))
                        except ValueError:
                            quality = 0.0
                    else:
                        params[key] = value
                else:
                    media_range = f"{media_range};{param}"
        else:
            media_range = part
        items.append(AcceptItem(media_range, quality, params))
    items.sort(key=lambda x: (-x.quality, x.value.count("/"), -len(x.value)))
    return items


def parse_accept_language(accept_language: str) -> List[AcceptItem]:
    return parse_accept_header(accept_language)


def parse_accept_charset(accept_charset: str) -> List[AcceptItem]:
    return parse_accept_header(accept_charset)


def parse_accept_encoding(accept_encoding: str) -> List[AcceptItem]:
    return parse_accept_header(accept_encoding)


def matches_media_type(pattern: str, media_type: str) -> bool:
    if pattern == media_type:
        return True
    if pattern == "*/*":
        return True
    if pattern.endswith("/*"):
        pattern_type = pattern[:-2]
        return media_type.startswith(pattern_type + "/")
    return False


def negotiate_content_type(
    accept_header: str, available_types: List[str]
) -> Optional[str]:
    if not accept_header or not available_types:
        return available_types[0] if available_types else None
    accept_items = parse_accept_header(accept_header)
    for accept_item in accept_items:
        if accept_item.quality == 0:
            continue
        for available_type in available_types:
            if matches_media_type(accept_item.value, available_type):
                return available_type
    for accept_item in accept_items:
        if accept_item.quality == 0:
            continue
        if accept_item.value == "*/*":
            return available_types[0]
        if "/*" in accept_item.value:
            accept_type = accept_item.value.split("/")[0]
            for available_type in available_types:
                if available_type.startswith(accept_type + "/"):
                    return available_type
    return None


def negotiate_language(
    accept_language: str, available_languages: List[str]
) -> Optional[str]:
    if not accept_language or not available_languages:
        return available_languages[0] if available_languages else None
    accept_items = parse_accept_language(accept_language)
    for accept_item in accept_items:
        if accept_item.quality == 0:
            continue
        if accept_item.value in available_languages:
            return accept_item.value
        if "-" in accept_item.value:
            lang_prefix = accept_item.value.split("-")[0]
            for available_lang in available_languages:
                if available_lang.startswith(lang_prefix + "-"):
                    return available_lang
                if available_lang == lang_prefix:
                    return available_lang
    return available_languages[0] if available_languages else None


def negotiate_charset(
    accept_charset: str, available_charsets: List[str]
) -> Optional[str]:
    if not accept_charset or not available_charsets:
        return available_charsets[0] if available_charsets else None
    accept_items = parse_accept_charset(accept_charset)
    for accept_item in accept_items:
        if accept_item.quality == 0:
            continue
        if accept_item.value in available_charsets:
            return accept_item.value
        if accept_item.value == "*":
            return available_charsets[0]
    return available_charsets[0] if available_charsets else None


def negotiate_encoding(
    accept_encoding: str, available_encodings: List[str]
) -> List[str]:
    if not accept_encoding or not available_encodings:
        return []
    accept_items = parse_accept_encoding(accept_encoding)
    accepted_encodings: List[str] = []
    for accept_item in accept_items:
        if accept_item.quality == 0:
            continue
        if accept_item.value in ("identity", "*"):
            accepted_encodings.extend(
                [enc for enc in available_encodings if enc != "identity"]
            )
            continue
        if accept_item.value in available_encodings:
            accepted_encodings.append(accept_item.value)
    return accepted_encodings


def get_best_match(accept_header: str, options: List[str]) -> Optional[str]:
    if not accept_header or not options:
        return options[0] if options else None
    accept_items = parse_accept_header(accept_header)
    for accept_item in accept_items:
        if accept_item.quality == 0:
            continue
        for option in options:
            if matches_media_type(accept_item.value, option):
                return option
    return options[0] if options else None


def get_accepts_info(request: Request) -> Dict[str, Any]:
    return {
        "accept": parse_accept_header(request.headers.get("Accept", "")),
        "accept_language": parse_accept_language(
            request.headers.get("Accept-Language", "")
        ),
        "accept_charset": parse_accept_charset(
            request.headers.get("Accept-Charset", "")
        ),
        "accept_encoding": parse_accept_encoding(
            request.headers.get("Accept-Encoding", "")
        ),
        "raw_accept": request.headers.get("Accept", ""),
        "raw_accept_language": request.headers.get("Accept-Language", ""),
        "raw_accept_charset": request.headers.get("Accept-Charset", ""),
        "raw_accept_encoding": request.headers.get("Accept-Encoding", ""),
    }


def create_vary_header(existing_vary: Optional[str], new_fields: List[str]) -> str:
    if not existing_vary:
        return ", ".join(new_fields)
    existing_fields = [field.strip() for field in existing_vary.split(",")]
    for field in new_fields:
        if field not in existing_fields:
            existing_fields.append(field)
    return ", ".join(existing_fields)


def get_accepts_from_request(
    request: Request, attribute_name: str = "accepts"
) -> AcceptsInfo:
    return AcceptsInfo(request)


def get_accepted_content_types(
    request: Request, attribute_name: str = "accepts_parsed"
) -> List[str]:
    accepts_parsed = getattr(request.state, attribute_name, {})
    accept_items = accepts_parsed.get("accept", [])
    return [item.value for item in accept_items if item.quality > 0]


def get_accepted_languages(
    request: Request, attribute_name: str = "accepts_parsed"
) -> List[str]:
    accepts_parsed = getattr(request.state, attribute_name, {})
    accept_items = accepts_parsed.get("accept_language", [])
    return [item.value for item in accept_items if item.quality > 0]


def get_accepted_charsets(
    request: Request, attribute_name: str = "accepts_parsed"
) -> List[str]:
    accepts_parsed = getattr(request.state, attribute_name, {})
    accept_items = accepts_parsed.get("accept_charset", [])
    return [item.value for item in accept_items if item.quality > 0]


def get_accepted_encodings(
    request: Request, attribute_name: str = "accepts_parsed"
) -> List[str]:
    accepts_parsed = getattr(request.state, attribute_name, {})
    accept_items = accepts_parsed.get("accept_encoding", [])
    return [item.value for item in accept_items if item.quality > 0]


def get_best_accepted_content_type(
    request: Request, available_types: List[str], attribute_name: str = "accepts_parsed"
) -> Optional[str]:
    accepted_types = get_accepted_content_types(request, attribute_name)
    for accepted_type in accepted_types:
        for available_type in available_types:
            if matches_media_type(accepted_type, available_type):
                return available_type
    return available_types[0] if available_types else None


def get_best_accepted_language(
    request: Request,
    available_languages: List[str],
    attribute_name: str = "accepts_parsed",
) -> Optional[str]:
    accepted_languages = get_accepted_languages(request, attribute_name)
    for accepted_lang in accepted_languages:
        if accepted_lang in available_languages:
            return accepted_lang
        if "-" in accepted_lang:
            lang_prefix = accepted_lang.split("-")[0]
            for available_lang in available_languages:
                if available_lang.startswith(lang_prefix + "-"):
                    return available_lang
                if available_lang == lang_prefix:
                    return available_lang
    return available_languages[0] if available_languages else None


class AcceptsMiddleware(BaseMiddleware):
    def __init__(
        self,
        *,
        default_content_type: str = "application/json",
        default_language: str = "en",
        default_charset: str = "utf-8",
        set_vary_header: bool = True,
        store_accepts_info: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.default_content_type = default_content_type
        self.default_language = default_language
        self.default_charset = default_charset
        self.set_vary_header = set_vary_header
        self.store_accepts_info = store_accepts_info
        self.vary: List[str] = []

    async def process_request(
        self, request: Request, response: Response, call_next: Any
    ) -> Any:
        if self.store_accepts_info:
            accepts_info = get_accepts_info(request)
            request.state.accepts = accepts_info
            request.state.accepts_parsed = {
                "accept": parse_accept_header(request.headers.get("Accept", "")),
                "accept_language": parse_accept_language(
                    request.headers.get("Accept-Language", "")
                ),
                "accept_charset": parse_accept_charset(
                    request.headers.get("Accept-Charset", "")
                ),
                "accept_encoding": parse_accept_encoding(
                    request.headers.get("Accept-Encoding", "")
                ),
            }
        if self.set_vary_header:
            if request.headers.get("Accept"):
                self.vary.append("Accept")
            if request.headers.get("Accept-Language"):
                self.vary.append("Accept-Language")
            if request.headers.get("Accept-Charset"):
                self.vary.append("Accept-Charset")
            if request.headers.get("Accept-Encoding"):
                self.vary.append("Accept-Encoding")
        return await call_next()

    async def process_response(
        self, request: Request, response: Response
    ) -> Any:
        if self.vary:
            existing_vary = response.headers.get("Vary")
            response.set_header(
                "Vary", create_vary_header(existing_vary, self.vary), overide=True
            )
        if not response.headers.get("Content-Type") and self.default_content_type:
            accept_header = request.headers.get("Accept")
            if accept_header:
                negotiated_type = negotiate_content_type(
                    accept_header, [self.default_content_type]
                )
                if negotiated_type:
                    response.set_header("Content-Type", negotiated_type, overide=True)
            else:
                response.set_header(
                    "Content-Type", self.default_content_type, overide=True
                )
        return response


def Accepts(
    default_content_type: str = "application/json",
    default_language: str = "en",
    default_charset: str = "utf-8",
    set_vary_header: bool = True,
    store_accepts_info: bool = True,
) -> AcceptsMiddleware:
    return AcceptsMiddleware(
        default_content_type=default_content_type,
        default_language=default_language,
        default_charset=default_charset,
        set_vary_header=set_vary_header,
        store_accepts_info=store_accepts_info,
    )


class ContentNegotiationMiddleware(AcceptsMiddleware):
    def negotiate_content_type(
        self,
        request: Request,
        available_types: List[str],
        default_type: Optional[str] = None,
    ) -> str:
        accept_header = request.headers.get("Accept")
        if accept_header:
            negotiated = negotiate_content_type(accept_header, available_types)
            if negotiated:
                return negotiated
        return default_type or self.default_content_type

    def negotiate_language(
        self,
        request: Request,
        available_languages: List[str],
        default_language: Optional[str] = None,
    ) -> str:
        accept_language = request.headers.get("Accept-Language")
        if accept_language:
            negotiated = negotiate_language(accept_language, available_languages)
            if negotiated:
                return negotiated
        return default_language or self.default_language


class StrictContentNegotiationMiddleware(ContentNegotiationMiddleware):
    def __init__(
        self,
        *,
        available_types: List[str],
        available_languages: Optional[List[str]] = None,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.available_types = available_types
        self.available_languages = available_languages or ["en"]

    async def process_request(
        self, request: Request, response: Response, call_next: Any
    ) -> Any:
        best_type = self.negotiate_content_type(
            request, self.available_types, self.default_content_type
        )
        accept_header = request.headers.get("Accept")
        if accept_header and best_type not in self.available_types:
            response.status(406)
            response.set_header("Content-Type", "application/json")
            return response.json(
                {
                    "error": "Not Acceptable",
                    "message": "Client does not accept any available content types",
                    "available_types": self.available_types,
                }
            )
        setattr(request, "negotiated_content_type", best_type)
        best_language = self.negotiate_language(
            request, self.available_languages, self.default_language
        )
        setattr(request, "negotiated_language", best_language)
        return await call_next()
