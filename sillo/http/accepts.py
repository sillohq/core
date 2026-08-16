from __future__ import annotations

from typing import Any

from sillo.core.http import Request, Response
from sillo.middleware.base import BaseMiddleware


class AcceptItem:
    """Represents a single parsed item from an HTTP Accept-family header.

    Each item holds the media range (or language tag, charset, encoding),
    an optional quality factor indicating client preference, and any
    additional extension parameters that were present in the header value.

    Attributes:
        value: The media range, language tag, charset name, or encoding token.
        quality: The q-factor between 0.0 and 1.0 (default 1.0).
        params: A dictionary of extension parameters excluding ``q``.
    """

    def __init__(
        self, value: str, quality: float = 1.0, params: dict[str, str] | None = None
    ):
        """Initialize an AcceptItem with a value, quality factor, and optional params.

        Args:
            value: The media range, language tag, charset, or encoding token string.
            quality: The client preference weight between 0.0 (not acceptable)
                and 1.0 (fully acceptable). Defaults to 1.0.
            params: An optional dictionary of extension parameters from the
                Accept header entry. If ``None``, an empty dict is used.

        Returns:
            None. This is a constructor and does not return a value.

        Raises:
            No exceptions are raised during initialization.
        """
        self.value = value
        self.quality = quality
        self.params = params or {}

    def __repr__(self) -> str:
        """Return a developer-friendly string representation of this AcceptItem.

        The representation includes the value and quality factor so that
        debugging output is informative when inspecting parsed Accept headers
        in logs or interactive sessions.

        Args:
            No arguments are accepted beyond ``self``.

        Returns:
            A string of the form ``AcceptItem(value=..., quality=...)`` that
            can be used for debugging and logging purposes.

        Raises:
            No exceptions are raised.
        """
        return f"AcceptItem(value={self.value}, quality={self.quality})"


class AcceptsInfo:
    """Provides parsed access to all Accept-family headers on a request.

    Lazily parses the ``Accept``, ``Accept-Language``, ``Accept-Charset``,
    and ``Accept-Encoding`` headers from the given request object. Parsed
    results are cached per-instance and can also leverage pre-parsed data
    stored on ``request.state`` by upstream middleware.

    Attributes:
        request: The HTTP request object whose headers are being inspected.
    """

    def __init__(self, request: Request):
        """Initialize AcceptsInfo by binding it to a specific HTTP request.

        Sets up internal caches for the four Accept-family header categories
        and stores a reference to the request for lazy header parsing.

        Args:
            request: The HTTP :class:`~sillo.http.Request` instance whose
                Accept-family headers will be inspected and parsed on demand.

        Returns:
            None. This is a constructor and does not return a value.

        Raises:
            No exceptions are raised during initialization.
        """
        self.request = request
        self._parsed_accept = None
        self._parsed_accept_language = None
        self._parsed_accept_charset = None
        self._parsed_accept_encoding = None

    @property
    def accept(self) -> list[AcceptItem]:
        """Return the parsed list of Accept header items from the request.

        Checks ``request.state.accepts_parsed`` first for pre-parsed data
        set by middleware, then falls back to parsing the raw ``Accept``
        header directly. Results are cached on first access.

        Args:
            No arguments are accepted beyond ``self``.

        Returns:
            A list of :class:`AcceptItem` instances sorted by quality factor
            and specificity, representing all media ranges the client accepts.

        Raises:
            No exceptions are raised under normal operation.
        """
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
    def accept_language(self) -> list[AcceptItem]:
        """Return the parsed list of Accept-Language header items.

        Checks ``request.state.accepts_parsed`` first for pre-parsed data
        set by middleware, then falls back to parsing the raw
        ``Accept-Language`` header directly. Results are cached on first
        access to avoid redundant parsing.

        Args:
            No arguments are accepted beyond ``self``.

        Returns:
            A list of :class:`AcceptItem` instances representing the
            languages the client prefers, sorted by quality factor.

        Raises:
            No exceptions are raised under normal operation.
        """
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
    def accept_charset(self) -> list[AcceptItem]:
        """Return the parsed list of Accept-Charset header items.

        Checks ``request.state.accepts_parsed`` first for pre-parsed data
        set by middleware, then falls back to parsing the raw
        ``Accept-Charset`` header directly. Results are cached on first
        access for performance.

        Args:
            No arguments are accepted beyond ``self``.

        Returns:
            A list of :class:`AcceptItem` instances representing the
            character sets the client accepts, sorted by quality factor.

        Raises:
            No exceptions are raised under normal operation.
        """
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
    def accept_encoding(self) -> list[AcceptItem]:
        """Return the parsed list of Accept-Encoding header items.

        Checks ``request.state.accepts_parsed`` first for pre-parsed data
        set by middleware, then falls back to parsing the raw
        ``Accept-Encoding`` header directly. Results are cached on first
        access for performance.

        Args:
            No arguments are accepted beyond ``self``.

        Returns:
            A list of :class:`AcceptItem` instances representing the
            content encodings the client accepts, sorted by quality factor.

        Raises:
            No exceptions are raised under normal operation.
        """
        if self._parsed_accept_encoding is None:
            cached = getattr(self.request.state, "accepts_parsed", {})
            if cached:
                self._parsed_accept_encoding = cached.get("accept_encoding", [])
            else:
                self._parsed_accept_encoding = parse_accept_encoding(
                    self.request.headers.get("Accept-Encoding", "")
                )
        return self._parsed_accept_encoding

    def get_accepted_types(self) -> list[str]:
        """Return a flat list of accepted media type values with positive quality.

        Filters out any entries whose quality factor is zero (explicitly
        not acceptable) and returns only the value strings for convenient
        iteration in content negotiation logic.

        Args:
            No arguments are accepted beyond ``self``.

        Returns:
            A list of media type strings (e.g. ``"text/html"``) that the
            client accepts with a quality factor greater than zero.

        Raises:
            No exceptions are raised under normal operation.
        """
        return [item.value for item in self.accept if item.quality > 0]

    def get_accepted_languages(self) -> list[str]:
        """Return a flat list of accepted language tags with positive quality.

        Filters out any entries whose quality factor is zero (explicitly
        not acceptable) and returns only the language tag strings for
        convenient iteration in language negotiation logic.

        Args:
            No arguments are accepted beyond ``self``.

        Returns:
            A list of language tag strings (e.g. ``"en-US"``) that the
            client accepts with a quality factor greater than zero.

        Raises:
            No exceptions are raised under normal operation.
        """
        return [item.value for item in self.accept_language if item.quality > 0]

    def get_accepted_charsets(self) -> list[str]:
        """Return a flat list of accepted charset names with positive quality.

        Filters out any entries whose quality factor is zero (explicitly
        not acceptable) and returns only the charset name strings for
        convenient iteration in charset negotiation logic.

        Args:
            No arguments are accepted beyond ``self``.

        Returns:
            A list of charset name strings (e.g. ``"utf-8"``) that the
            client accepts with a quality factor greater than zero.

        Raises:
            No exceptions are raised under normal operation.
        """
        return [item.value for item in self.accept_charset if item.quality > 0]

    def get_accepted_encodings(self) -> list[str]:
        """Return a flat list of accepted encoding tokens with positive quality.

        Filters out any entries whose quality factor is zero (explicitly
        not acceptable) and returns only the encoding token strings for
        convenient iteration in encoding negotiation logic.

        Args:
            No arguments are accepted beyond ``self``.

        Returns:
            A list of encoding token strings (e.g. ``"gzip"``) that the
            client accepts with a quality factor greater than zero.

        Raises:
            No exceptions are raised under normal operation.
        """
        return [item.value for item in self.accept_encoding if item.quality > 0]


def parse_accept_header(accept_header: str) -> list[AcceptItem]:
    """Parse an HTTP Accept header string into a sorted list of AcceptItem objects.

    Splits the raw header value on commas, extracts the media range, quality
    factor (``q`` parameter), and any extension parameters from each entry.
    The resulting list is sorted by descending quality factor, then by
    specificity (number of ``/`` characters), and finally by descending
    length of the media range string.

    Args:
        accept_header: The raw ``Accept`` header value string from an HTTP
            request, e.g. ``"text/html, application/json;q=0.9"``.

    Returns:
        A list of :class:`AcceptItem` instances sorted by client preference,
        with the most preferred media ranges appearing first. Returns an
        empty list if the header string is empty or ``None``.

    Raises:
        No exceptions are raised; malformed ``q`` values default to 0.0
        rather than causing a parse failure.
    """
    if not accept_header:
        return []
    items = []
    for part in accept_header.split(","):
        part = part.strip()
        if not part:
            continue
        quality = 1.0
        params: dict[str, str] = {}
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


def parse_accept_language(accept_language: str) -> list[AcceptItem]:
    """Parse an HTTP Accept-Language header into a sorted list of AcceptItem objects.

    Delegates to :func:`parse_accept_header` since the grammar for
    Accept-Language is structurally identical to Accept, with language
    tags replacing media ranges.

    Args:
        accept_language: The raw ``Accept-Language`` header value string,
            e.g. ``"en-US, fr;q=0.8"``.

    Returns:
        A list of :class:`AcceptItem` instances sorted by client preference,
        with the most preferred language tags appearing first. Returns an
        empty list if the header string is empty.

    Raises:
        No exceptions are raised during parsing.
    """
    return parse_accept_header(accept_language)


def parse_accept_charset(accept_charset: str) -> list[AcceptItem]:
    """Parse an HTTP Accept-Charset header into a sorted list of AcceptItem objects.

    Delegates to :func:`parse_accept_header` since the grammar for
    Accept-Charset is structurally identical to Accept, with charset
    names replacing media ranges.

    Args:
        accept_charset: The raw ``Accept-Charset`` header value string,
            e.g. ``"utf-8, iso-8859-1;q=0.5"``.

    Returns:
        A list of :class:`AcceptItem` instances sorted by client preference,
        with the most preferred charsets appearing first. Returns an empty
        list if the header string is empty.

    Raises:
        No exceptions are raised during parsing.
    """
    return parse_accept_header(accept_charset)


def parse_accept_encoding(accept_encoding: str) -> list[AcceptItem]:
    """Parse an HTTP Accept-Encoding header into a sorted list of AcceptItem objects.

    Delegates to :func:`parse_accept_header` since the grammar for
    Accept-Encoding is structurally identical to Accept, with encoding
    tokens replacing media ranges.

    Args:
        accept_encoding: The raw ``Accept-Encoding`` header value string,
            e.g. ``"gzip, deflate;q=0.5"``.

    Returns:
        A list of :class:`AcceptItem` instances sorted by client preference,
        with the most preferred encodings appearing first. Returns an empty
        list if the header string is empty.

    Raises:
        No exceptions are raised during parsing.
    """
    return parse_accept_header(accept_encoding)


def matches_media_type(pattern: str, media_type: str) -> bool:
    """Check whether a media type matches a given Accept header pattern.

    Supports exact matches, the universal wildcard ``*/*``, and type-level
    wildcards such as ``text/*``. The comparison is case-sensitive and
    does not perform any parameter matching beyond the type/subtype pair.

    Args:
        pattern: The Accept header pattern to match against, which may be
            an exact media type, ``*/*``, or a type wildcard like ``text/*``.
        media_type: The concrete media type string to test, e.g.
            ``"text/html"`` or ``"application/json"``.

    Returns:
        ``True`` if the media type matches the pattern according to the
        wildcard rules described above, ``False`` otherwise.

    Raises:
        No exceptions are raised during matching.
    """
    if pattern == media_type:
        return True
    if pattern == "*/*":
        return True
    if pattern.endswith("/*"):
        pattern_type = pattern[:-2]
        return media_type.startswith(pattern_type + "/")
    return False


def negotiate_content_type(
    accept_header: str, available_types: list[str]
) -> str | None:
    """Negotiate the best content type from available options given an Accept header.

    Performs RFC 7231 content negotiation by iterating through the parsed
    Accept items in preference order and returning the first available type
    that matches. Falls back to wildcard matching if no exact match is
    found, and returns the first available type when the header is empty.

    Args:
        accept_header: The raw ``Accept`` header value string from the
            client request, e.g. ``"text/html, application/json;q=0.9"``.
        available_types: A list of media type strings that the server can
            produce, e.g. ``["application/json", "text/html"]``.

    Returns:
        The best matching media type string from ``available_types``, or
        the first available type if the header is empty, or ``None`` if
        no match can be found and no types are available.

    Raises:
        No exceptions are raised during negotiation.
    """
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
    accept_language: str, available_languages: list[str]
) -> str | None:
    """Negotiate the best language from available options given an Accept-Language header.

    Iterates through parsed Accept-Language items in preference order and
    returns the first available language that matches. Supports prefix
    matching so that ``"en"`` can satisfy ``"en-US"`` and vice versa.
    Falls back to the first available language when the header is empty.

    Args:
        accept_language: The raw ``Accept-Language`` header value string,
            e.g. ``"en-US, fr;q=0.8"``.
        available_languages: A list of language tag strings the server can
            serve, e.g. ``["en", "fr", "de"]``.

    Returns:
        The best matching language tag from ``available_languages``, or
        the first available language if the header is empty, or ``None``
        if no match can be found and no languages are available.

    Raises:
        No exceptions are raised during negotiation.
    """
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


def negotiate_charset(accept_charset: str, available_charsets: list[str]) -> str | None:
    """Negotiate the best charset from available options given an Accept-Charset header.

    Iterates through parsed Accept-Charset items in preference order and
    returns the first available charset that matches. The ``*`` wildcard
    matches any available charset. Falls back to the first available
    charset when the header is empty.

    Args:
        accept_charset: The raw ``Accept-Charset`` header value string,
            e.g. ``"utf-8, iso-8859-1;q=0.5"``.
        available_charsets: A list of charset name strings the server can
            produce, e.g. ``["utf-8", "iso-8859-1"]``.

    Returns:
        The best matching charset from ``available_charsets``, or the
        first available charset if the header is empty, or ``None`` if
        no match can be found and no charsets are available.

    Raises:
        No exceptions are raised during negotiation.
    """
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
    accept_encoding: str, available_encodings: list[str]
) -> list[str]:
    """Negotiate acceptable encodings from available options given an Accept-Encoding header.

    Iterates through parsed Accept-Encoding items and collects all
    available encodings that the client accepts. The ``identity`` and
    ``*`` entries cause all non-identity available encodings to be
    included. Encodings with quality zero are excluded.

    Args:
        accept_encoding: The raw ``Accept-Encoding`` header value string,
            e.g. ``"gzip, deflate;q=0.5"``.
        available_encodings: A list of encoding token strings the server
            can produce, e.g. ``["gzip", "br", "identity"]``.

    Returns:
        A list of encoding token strings from ``available_encodings``
        that the client accepts. Returns an empty list if the header
        is empty or no encodings are available.

    Raises:
        No exceptions are raised during negotiation.
    """
    if not accept_encoding or not available_encodings:
        return []
    accept_items = parse_accept_encoding(accept_encoding)
    accepted_encodings: list[str] = []
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


def get_best_match(accept_header: str, options: list[str]) -> str | None:
    """Find the best matching option from a list given an Accept header.

    Parses the Accept header and iterates through items in preference
    order, returning the first option that matches via
    :func:`matches_media_type`. Falls back to the first option when the
    header is empty or no match is found.

    Args:
        accept_header: The raw ``Accept`` header value string from the
            client request, e.g. ``"text/html, application/json;q=0.9"``.
        options: A list of media type strings to match against, e.g.
            ``["application/json", "text/xml"]``.

    Returns:
        The first matching media type string from ``options``, or the
        first option as a default, or ``None`` if no options are provided.

    Raises:
        No exceptions are raised during matching.
    """
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


def get_accepts_info(request: Request) -> dict[str, Any]:
    """Build a comprehensive dictionary of parsed Accept-family header data.

    Parses all four Accept-family headers (Accept, Accept-Language,
    Accept-Charset, Accept-Encoding) from the given request and returns
    both the parsed :class:`AcceptItem` lists and the raw header strings
    in a single dictionary for convenient access.

    Args:
        request: The HTTP :class:`~sillo.http.Request` instance whose
            Accept-family headers should be parsed and collected.

    Returns:
        A dictionary with keys ``"accept"``, ``"accept_language"``,
        ``"accept_charset"``, ``"accept_encoding"`` mapping to lists of
        :class:`AcceptItem` objects, plus ``"raw_accept"``,
        ``"raw_accept_language"``, ``"raw_accept_charset"``, and
        ``"raw_accept_encoding"`` mapping to the raw header strings.

    Raises:
        No exceptions are raised during parsing.
    """
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


def create_vary_header(existing_vary: str | None, new_fields: list[str]) -> str:
    """Merge new field names into an existing Vary header value without duplicates.

    Takes the current ``Vary`` header string (if any) and appends each
    new field that is not already present, producing a correctly
    comma-separated header value suitable for HTTP caching directives.

    Args:
        existing_vary: The current ``Vary`` header value string, or
            ``None`` if no ``Vary`` header has been set yet.
        new_fields: A list of field name strings to add to the Vary
            header, e.g. ``["Accept", "Accept-Language"]``.

    Returns:
        A comma-separated string of all Vary field names including both
        the existing and newly added fields with duplicates removed.

    Raises:
        No exceptions are raised during header construction.
    """
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
    """Create an AcceptsInfo instance bound to the given HTTP request.

    Factory function that wraps the :class:`AcceptsInfo` constructor to
    provide a consistent interface for obtaining Accept header information
    from a request object. The ``attribute_name`` parameter is accepted
    for interface compatibility but the returned object always wraps the
    request directly.

    Args:
        request: The HTTP :class:`~sillo.http.Request` instance from which
            Accept-family headers will be lazily parsed.
        attribute_name: The name of the attribute used to store the
            AcceptsInfo on the request state. Defaults to ``"accepts"``.

    Returns:
        A new :class:`AcceptsInfo` instance bound to the given request,
        ready for lazy header parsing on property access.

    Raises:
        No exceptions are raised during construction.
    """
    return AcceptsInfo(request)


def get_accepted_content_types(
    request: Request, attribute_name: str = "accepts_parsed"
) -> list[str]:
    """Extract accepted content type values from pre-parsed request state.

    Reads the ``accepts_parsed`` attribute (or the specified attribute
    name) from the request state and returns a flat list of media type
    strings that have a quality factor greater than zero.

    Args:
        request: The HTTP :class:`~sillo.http.Request` instance whose
            state contains pre-parsed Accept header data, typically set
            by :class:`AcceptsMiddleware`.
        attribute_name: The name of the state attribute containing the
            parsed Accept data dictionary. Defaults to ``"accepts_parsed"``.

    Returns:
        A list of media type strings (e.g. ``["text/html", "application/json"]``)
        that the client accepts with a quality factor greater than zero.

    Raises:
        No exceptions are raised; returns an empty list if the attribute
        is missing or contains no accept data.
    """
    accepts_parsed = getattr(request.state, attribute_name, {})
    accept_items = accepts_parsed.get("accept", [])
    return [item.value for item in accept_items if item.quality > 0]


def get_accepted_languages(
    request: Request, attribute_name: str = "accepts_parsed"
) -> list[str]:
    """Extract accepted language tags from pre-parsed request state.

    Reads the ``accepts_parsed`` attribute (or the specified attribute
    name) from the request state and returns a flat list of language tag
    strings that have a quality factor greater than zero.

    Args:
        request: The HTTP :class:`~sillo.http.Request` instance whose
            state contains pre-parsed Accept-Language header data,
            typically set by :class:`AcceptsMiddleware`.
        attribute_name: The name of the state attribute containing the
            parsed Accept data dictionary. Defaults to ``"accepts_parsed"``.

    Returns:
        A list of language tag strings (e.g. ``["en-US", "fr"]``) that
        the client accepts with a quality factor greater than zero.

    Raises:
        No exceptions are raised; returns an empty list if the attribute
        is missing or contains no accept-language data.
    """
    accepts_parsed = getattr(request.state, attribute_name, {})
    accept_items = accepts_parsed.get("accept_language", [])
    return [item.value for item in accept_items if item.quality > 0]


def get_accepted_charsets(
    request: Request, attribute_name: str = "accepts_parsed"
) -> list[str]:
    """Extract accepted charset names from pre-parsed request state.

    Reads the ``accepts_parsed`` attribute (or the specified attribute
    name) from the request state and returns a flat list of charset name
    strings that have a quality factor greater than zero.

    Args:
        request: The HTTP :class:`~sillo.http.Request` instance whose
            state contains pre-parsed Accept-Charset header data,
            typically set by :class:`AcceptsMiddleware`.
        attribute_name: The name of the state attribute containing the
            parsed Accept data dictionary. Defaults to ``"accepts_parsed"``.

    Returns:
        A list of charset name strings (e.g. ``["utf-8"]``) that the
        client accepts with a quality factor greater than zero.

    Raises:
        No exceptions are raised; returns an empty list if the attribute
        is missing or contains no accept-charset data.
    """
    accepts_parsed = getattr(request.state, attribute_name, {})
    accept_items = accepts_parsed.get("accept_charset", [])
    return [item.value for item in accept_items if item.quality > 0]


def get_accepted_encodings(
    request: Request, attribute_name: str = "accepts_parsed"
) -> list[str]:
    """Extract accepted encoding tokens from pre-parsed request state.

    Reads the ``accepts_parsed`` attribute (or the specified attribute
    name) from the request state and returns a flat list of encoding
    token strings that have a quality factor greater than zero.

    Args:
        request: The HTTP :class:`~sillo.http.Request` instance whose
            state contains pre-parsed Accept-Encoding header data,
            typically set by :class:`AcceptsMiddleware`.
        attribute_name: The name of the state attribute containing the
            parsed Accept data dictionary. Defaults to ``"accepts_parsed"``.

    Returns:
        A list of encoding token strings (e.g. ``["gzip", "br"]``) that
        the client accepts with a quality factor greater than zero.

    Raises:
        No exceptions are raised; returns an empty list if the attribute
        is missing or contains no accept-encoding data.
    """
    accepts_parsed = getattr(request.state, attribute_name, {})
    accept_items = accepts_parsed.get("accept_encoding", [])
    return [item.value for item in accept_items if item.quality > 0]


def get_best_accepted_content_type(
    request: Request, available_types: list[str], attribute_name: str = "accepts_parsed"
) -> str | None:
    """Determine the best content type match from available options using request state.

    Reads pre-parsed Accept header data from the request state and
    iterates through accepted types in preference order, returning the
    first available type that matches via :func:`matches_media_type`.

    Args:
        request: The HTTP :class:`~sillo.http.Request` instance whose
            state contains pre-parsed Accept header data.
        available_types: A list of media type strings the server can
            produce, e.g. ``["application/json", "text/html"]``.
        attribute_name: The name of the state attribute containing the
            parsed Accept data dictionary. Defaults to ``"accepts_parsed"``.

    Returns:
        The best matching media type string from ``available_types``, or
        the first available type as a fallback, or ``None`` if no types
        are available.

    Raises:
        No exceptions are raised during negotiation.
    """
    accepted_types = get_accepted_content_types(request, attribute_name)
    for accepted_type in accepted_types:
        for available_type in available_types:
            if matches_media_type(accepted_type, available_type):
                return available_type
    return available_types[0] if available_types else None


def get_best_accepted_language(
    request: Request,
    available_languages: list[str],
    attribute_name: str = "accepts_parsed",
) -> str | None:
    """Determine the best language match from available options using request state.

    Reads pre-parsed Accept-Language data from the request state and
    iterates through accepted languages in preference order, returning
    the first available language that matches. Supports prefix matching
    so that ``"en"`` can satisfy ``"en-US"`` and vice versa.

    Args:
        request: The HTTP :class:`~sillo.http.Request` instance whose
            state contains pre-parsed Accept-Language header data.
        available_languages: A list of language tag strings the server
            can serve, e.g. ``["en", "fr", "de"]``.
        attribute_name: The name of the state attribute containing the
            parsed Accept data dictionary. Defaults to ``"accepts_parsed"``.

    Returns:
        The best matching language tag from ``available_languages``, or
        the first available language as a fallback, or ``None`` if no
        languages are available.

    Raises:
        No exceptions are raised during negotiation.
    """
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
    """Middleware that parses and stores Accept-family header information.

    Intercepts incoming requests to parse all Accept-family headers and
    store the parsed results on the request state for downstream handlers.
    Optionally sets ``Vary`` response headers and negotiates a default
    ``Content-Type`` based on the client's Accept header.

    Attributes:
        default_content_type: Fallback content type when negotiation fails.
        default_language: Fallback language when negotiation fails.
        default_charset: Fallback charset when negotiation fails.
        set_vary_header: Whether to add Vary headers to responses.
        store_accepts_info: Whether to parse and store Accept data on request state.
    """

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
        """Initialize AcceptsMiddleware with configurable content negotiation defaults.

        Sets up the middleware with default fallback values for content type,
        language, and charset, along with flags controlling Vary header
        generation and Accept data storage on the request state.

        Args:
            default_content_type: The fallback Content-Type to use when the
                client's Accept header cannot be matched. Defaults to
                ``"application/json"``.
            default_language: The fallback language tag when the client's
                Accept-Language header cannot be matched. Defaults to ``"en"``.
            default_charset: The fallback charset when the client's
                Accept-Charset header cannot be matched. Defaults to ``"utf-8"``.
            set_vary_header: If ``True``, adds ``Vary`` headers to responses
                for each Accept-family header present in the request.
                Defaults to ``True``.
            store_accepts_info: If ``True``, parses and stores Accept data
                on ``request.state`` for downstream handler access.
                Defaults to ``True``.
            **kwargs: Additional keyword arguments passed to the parent
                :class:`~sillo.middleware.base.BaseMiddleware` constructor.

        Returns:
            None. This is a constructor and does not return a value.

        Raises:
            No exceptions are raised during initialization.
        """
        super().__init__(**kwargs)
        self.default_content_type = default_content_type
        self.default_language = default_language
        self.default_charset = default_charset
        self.set_vary_header = set_vary_header
        self.store_accepts_info = store_accepts_info
        self.vary: list[str] = []

    async def process_request(
        self, request: Request, response: Response, call_next: Any
    ) -> Any:
        """Process an incoming request by parsing and storing Accept-family headers.

        When ``store_accepts_info`` is enabled, parses all four Accept-family
        headers and stores both a comprehensive info dictionary and a
        pre-parsed dictionary on the request state. When ``set_vary_header``
        is enabled, records which Accept-family headers are present so that
        appropriate ``Vary`` headers can be set on the response.

        Args:
            request: The incoming HTTP :class:`~sillo.http.Request` object
                whose headers will be inspected and parsed.
            response: The HTTP :class:`~sillo.http.Response` object that
                will eventually be sent back to the client.
            call_next: An async callable that invokes the next middleware
                or request handler in the processing chain.

        Returns:
            The result of calling the next handler in the chain, which
            is typically a :class:`~sillo.http.Response` object.

        Raises:
            No exceptions are raised directly; any exceptions from the
            downstream handler are propagated unchanged.
        """
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

    async def process_response(self, request: Request, response: Response) -> Any:
        """Process the outgoing response by setting Vary and Content-Type headers.

        If any Accept-family headers were detected in the request, adds
        corresponding ``Vary`` header fields to the response. If no
        ``Content-Type`` is already set and a default is configured,
        attempts to negotiate the content type from the client's Accept
        header or falls back to the configured default.

        Args:
            request: The original HTTP :class:`~sillo.http.Request` object
                used to look up Accept headers for content negotiation.
            response: The outgoing HTTP :class:`~sillo.http.Response` object
                whose headers will be updated before sending to the client.

        Returns:
            The modified :class:`~sillo.http.Response` object with updated
            ``Vary`` and ``Content-Type`` headers as appropriate.

        Raises:
            No exceptions are raised during response processing.
        """
        if self.vary:
            existing_vary = response.headers.get("Vary")
            response.set_header(
                "Vary", create_vary_header(existing_vary, self.vary), override=True
            )
        if not response.headers.get("Content-Type") and self.default_content_type:
            accept_header = request.headers.get("Accept")
            if accept_header:
                negotiated_type = negotiate_content_type(
                    accept_header, [self.default_content_type]
                )
                if negotiated_type:
                    response.set_header("Content-Type", negotiated_type, override=True)
            else:
                response.set_header(
                    "Content-Type", self.default_content_type, override=True
                )
        return response


def Accepts(
    default_content_type: str = "application/json",
    default_language: str = "en",
    default_charset: str = "utf-8",
    set_vary_header: bool = True,
    store_accepts_info: bool = True,
) -> AcceptsMiddleware:
    """Factory function that creates a configured AcceptsMiddleware instance.

    Provides a convenient shorthand for constructing an
    :class:`AcceptsMiddleware` without calling the class constructor
    directly, making it suitable for use in middleware registration
    pipelines and configuration helpers.

    Args:
        default_content_type: The fallback Content-Type to use when the
            client's Accept header cannot be matched. Defaults to
            ``"application/json"``.
        default_language: The fallback language tag when the client's
            Accept-Language header cannot be matched. Defaults to ``"en"``.
        default_charset: The fallback charset when the client's
            Accept-Charset header cannot be matched. Defaults to ``"utf-8"``.
        set_vary_header: If ``True``, adds ``Vary`` headers to responses
            for each Accept-family header present in the request.
            Defaults to ``True``.
        store_accepts_info: If ``True``, parses and stores Accept data
            on ``request.state`` for downstream handler access.
            Defaults to ``True``.

    Returns:
        A fully configured :class:`AcceptsMiddleware` instance ready to
        be registered in the middleware pipeline.

    Raises:
        No exceptions are raised during construction.
    """
    return AcceptsMiddleware(
        default_content_type=default_content_type,
        default_language=default_language,
        default_charset=default_charset,
        set_vary_header=set_vary_header,
        store_accepts_info=store_accepts_info,
    )


class ContentNegotiationMiddleware(AcceptsMiddleware):
    """Extended middleware that provides active content negotiation methods.

    Extends :class:`AcceptsMiddleware` with convenience methods for
    negotiating content type and language against a set of server-supported
    options, using the client's Accept headers as input.

    Attributes:
        Inherits all attributes from :class:`AcceptsMiddleware`.
    """

    def negotiate_content_type(
        self,
        request: Request,
        available_types: list[str],
        default_type: str | None = None,
    ) -> str:
        """Negotiate the best content type for a request from available server types.

        Reads the client's ``Accept`` header and attempts to find the best
        match among the available types using :func:`negotiate_content_type`.
        Falls back to the provided default type or the middleware's
        configured default content type.

        Args:
            request: The HTTP :class:`~sillo.http.Request` instance whose
                Accept header will be used for negotiation.
            available_types: A list of media type strings the server can
                produce, e.g. ``["application/json", "text/html"]``.
            default_type: An optional explicit fallback media type to use
                when negotiation fails. If ``None``, the middleware's
                ``default_content_type`` is used instead.

        Returns:
            The negotiated media type string from ``available_types``,
            or the default type if negotiation fails to find a match.

        Raises:
            No exceptions are raised during negotiation.
        """
        accept_header = request.headers.get("Accept")
        if accept_header:
            negotiated = negotiate_content_type(accept_header, available_types)
            if negotiated:
                return negotiated
        return default_type or self.default_content_type

    def negotiate_language(
        self,
        request: Request,
        available_languages: list[str],
        default_language: str | None = None,
    ) -> str:
        """Negotiate the best language for a request from available server languages.

        Reads the client's ``Accept-Language`` header and attempts to find
        the best match among the available languages using
        :func:`negotiate_language`. Falls back to the provided default
        language or the middleware's configured default language.

        Args:
            request: The HTTP :class:`~sillo.http.Request` instance whose
                Accept-Language header will be used for negotiation.
            available_languages: A list of language tag strings the server
                can serve, e.g. ``["en", "fr", "de"]``.
            default_language: An optional explicit fallback language tag
                to use when negotiation fails. If ``None``, the middleware's
                ``default_language`` is used instead.

        Returns:
            The negotiated language tag from ``available_languages``, or
            the default language if negotiation fails to find a match.

        Raises:
            No exceptions are raised during negotiation.
        """
        accept_language = request.headers.get("Accept-Language")
        if accept_language:
            negotiated = negotiate_language(accept_language, available_languages)
            if negotiated:
                return negotiated
        return default_language or self.default_language


class StrictContentNegotiationMiddleware(ContentNegotiationMiddleware):
    """Strict content negotiation middleware that rejects unacceptable requests.

    Extends :class:`ContentNegotiationMiddleware` to enforce that the
    client must accept at least one of the server's available content
    types. Returns an HTTP 406 (Not Acceptable) response when the client
    cannot be served any of the available types.

    Attributes:
        available_types: The list of media types the server can produce.
        available_languages: The list of language tags the server can serve.
    """

    def __init__(
        self,
        *,
        available_types: list[str],
        available_languages: list[str] | None = None,
        **kwargs: Any,
    ):
        """Initialize StrictContentNegotiationMiddleware with required available types.

        Configures the middleware with the list of content types and
        languages the server supports. Unlike the parent class, the
        available types list is mandatory and used to enforce strict
        content negotiation on every request.

        Args:
            available_types: A required list of media type strings the
                server can produce, e.g. ``["application/json", "text/html"]``.
                At least one type must be provided.
            available_languages: An optional list of language tag strings
                the server can serve. Defaults to ``["en"]`` if not provided.
            **kwargs: Additional keyword arguments passed to the parent
                :class:`ContentNegotiationMiddleware` constructor.

        Returns:
            None. This is a constructor and does not return a value.

        Raises:
            No exceptions are raised during initialization.
        """
        super().__init__(**kwargs)
        self.available_types = available_types
        self.available_languages = available_languages or ["en"]

    async def process_request(
        self, request: Request, response: Response, call_next: Any
    ) -> Any:
        """Process a request with strict content negotiation enforcement.

        Negotiates the best content type and language for the request.
        If the client cannot accept any of the available content types
        and an Accept header was present, returns an HTTP 406 response.
        Otherwise stores the negotiated values on the request object
        and proceeds to the next handler.

        Args:
            request: The incoming HTTP :class:`~sillo.http.Request` object
                whose Accept headers will be used for strict negotiation.
            response: The HTTP :class:`~sillo.http.Response` object used
                to send a 406 response if negotiation fails.
            call_next: An async callable that invokes the next middleware
                or request handler in the processing chain.

        Returns:
            Either an HTTP 406 :class:`~sillo.http.Response` if the client
            cannot accept any available types, or the result of calling
            the next handler in the chain.

        Raises:
            No exceptions are raised directly; any exceptions from the
            downstream handler are propagated unchanged.
        """
        best_type = self.negotiate_content_type(
            request, self.available_types, self.default_content_type
        )
        accept_header = request.headers.get("Accept")
        if accept_header and best_type not in self.available_types:
            # The status must be passed to json() rather than set beforehand:
            # json() builds a fresh response, so an earlier status(406) was
            # discarded and this shipped a "Not Acceptable" body under a 200,
            # leaving clients to treat the error as a successful payload.
            # json() also sets the content type, so no header call is needed.
            return response.json(
                {
                    "error": "Not Acceptable",
                    "message": "Client does not accept any available content types",
                    "available_types": self.available_types,
                },
                status_code=406,
            )
        # Attached dynamically for downstream handlers to read. These were
        # written with setattr(), which only had the effect of hiding them from
        # the type checker — they are not declared on Request either way.
        request.negotiated_content_type = best_type  # ty: ignore[unresolved-attribute]
        best_language = self.negotiate_language(
            request, self.available_languages, self.default_language
        )
        request.negotiated_language = best_language  # ty: ignore[unresolved-attribute]
        return await call_next()
