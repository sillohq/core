from __future__ import annotations

from collections.abc import ItemsView, Iterator, KeysView, Sequence, ValuesView
from typing import Any
from urllib.parse import SplitResult, parse_qsl, urlencode, urlsplit

from typing_extensions import Self

from sillo.objects.common import Scope
from sillo.objects.datastructures import MultiDict


class URL:
    """
    Represents an immutable URL with convenient access to its components.

    Provides parsing and manipulation of URLs including scheme, host, path,
    query parameters, and fragment. Can be constructed from a raw URL string,
    an ASGI scope dictionary, or individual URL components. Supports query
    parameter manipulation and URL component replacement while preserving
    immutability by returning new instances on modification.
    """

    def __init__(
        self,
        url: str = "",
        scope: Scope | None = None,
        **components: Any,
    ) -> None:
        """
        Initialize a URL instance from a string, ASGI scope, or components.

        Constructs a URL object from exactly one of three sources: a raw URL
        string, an ASGI connection scope dictionary, or individual URL component
        keyword arguments. When built from a scope, the URL is reconstructed
        using the scheme, server, path, query string, and host header from the
        scope. When built from components, they are applied as replacements on
        an empty URL to produce the final result.

        Args:
            url: A raw URL string to parse. Must be empty if scope or
                components are provided.
            scope: An ASGI connection scope dictionary from which to
                reconstruct the URL. Mutually exclusive with url and components.
            **components: Individual URL component overrides such as scheme,
                netloc, path, query, or fragment. Mutually exclusive with url
                and scope.

        Raises:
            AssertionError: If more than one initialization source is provided,
                e.g. both url and scope, or both scope and components.
        """
        if scope is not None:
            assert not url, 'Cannot set both "url" and "scope".'
            assert not components, 'Cannot set both "scope" and "**components".'
            scheme = scope.get("scheme", "http")
            server = scope.get("server", None)
            path = scope["path"]
            query_string = scope.get("query_string", b"")

            host_header = None
            for key, value in scope["headers"]:
                if key == b"host":
                    host_header = value.decode("latin-1")
                    break

            if host_header is not None:
                url = f"{scheme}://{host_header}{path}"
            elif server is None:
                url = path
            else:
                host, port = server
                default_port = {"http": 80, "https": 443, "ws": 80, "wss": 443}[scheme]
                if port == default_port:
                    url = f"{scheme}://{host}{path}"
                else:
                    url = f"{scheme}://{host}:{port}{path}"

            if query_string:
                url += "?" + query_string.decode()
        elif components:
            assert not url, 'Cannot set both "url" and "**components".'
            url = URL("").replace(**components).components.geturl()

        self._url = url

    @property
    def components(self) -> SplitResult:
        """
        Return the parsed URL components as a SplitResult namedtuple.

        Lazily parses the internal URL string using ``urllib.parse.urlsplit``
        and caches the resulting SplitResult for subsequent accesses. The
        SplitResult provides named attributes for scheme, netloc, path,
        query, and fragment portions of the URL.

        Returns:
            SplitResult: A five-tuple of (scheme, netloc, path, query,
            fragment) representing the parsed URL components.
        """
        if not hasattr(self, "_components"):
            self._components = urlsplit(self._url)
        return self._components

    @property
    def scheme(self) -> str:
        """
        Return the URL scheme component (e.g. 'http', 'https', 'ws', 'wss').

        Extracts the scheme portion from the parsed URL components, which
        identifies the protocol used to access the resource. The scheme
        is always returned in lowercase without the trailing colon.

        Returns:
            str: The URL scheme string, such as 'http' or 'https'.
            Returns an empty string if no scheme is present in the URL.
        """
        return self.components.scheme

    @property
    def netloc(self) -> str:
        """
        Return the URL network location component (host and optional port).

        Extracts the netloc portion from the parsed URL components, which
        includes the hostname and optionally the port number, username,
        and password if present in the URL authority section.

        Returns:
            str: The network location string such as 'example.com:8080'
            or 'user:pass@host:port'. Empty string if not present.
        """
        return self.components.netloc

    @property
    def path(self) -> str:
        """
        Return the URL path component.

        Extracts the hierarchical path portion from the parsed URL components.
        The path typically represents the resource location on the server
        and begins with a forward slash for absolute URLs.

        Returns:
            str: The URL path string such as '/api/v1/users'. Returns an
            empty string if no path is present in the URL.
        """
        return self.components.path

    @property
    def query(self) -> str:
        """
        Return the URL query string component.

        Extracts the query portion from the parsed URL components, which
        contains the parameters passed after the '?' delimiter. The query
        string is returned without the leading '?' character.

        Returns:
            str: The URL query string such as 'key=value&foo=bar'. Returns
            an empty string if no query parameters are present.
        """
        return self.components.query

    @property
    def fragment(self) -> str:
        """
        Return the URL fragment component.

        Extracts the fragment identifier from the parsed URL components,
        which appears after the '#' character. Fragments are commonly used
        to reference a specific section within a resource.

        Returns:
            str: The URL fragment string without the leading '#'. Returns
            an empty string if no fragment is present in the URL.
        """
        return self.components.fragment

    @property
    def username(self) -> None | str:
        """
        Return the username component from the URL authority section.

        Extracts the username portion from the URL's netloc if present.
        The username appears before the colon or '@' symbol in URLs that
        include authentication credentials.

        Returns:
            None | str: The username string if credentials are present in
            the URL, or None if no username is specified.
        """
        return self.components.username

    @property
    def password(self) -> None | str:
        """
        Return the password component from the URL authority section.

        Extracts the password portion from the URL's netloc if present.
        The password appears after the colon and before the '@' symbol
        in URLs that include authentication credentials.

        Returns:
            None | str: The password string if credentials are present in
            the URL, or None if no password is specified.
        """
        return self.components.password

    @property
    def hostname(self) -> None | str:
        """
        Return the hostname component from the URL authority section.

        Extracts the host portion from the URL's netloc, excluding any
        port number, username, or password. For IPv6 addresses, the
        hostname is returned without the surrounding square brackets.

        Returns:
            None | str: The hostname string such as 'example.com' or
            None if no host is specified in the URL.
        """
        return self.components.hostname

    @property
    def port(self) -> int | None:
        """
        Return the port number from the URL authority section.

        Extracts the numeric port from the URL's netloc if explicitly
        specified. Returns None when no port is present, in which case
        the default port for the scheme should be assumed.

        Returns:
            int | None: The integer port number if specified in the URL,
            or None if no explicit port is present.
        """
        return self.components.port

    @property
    def is_secure(self) -> bool:
        """
        Determine whether the URL uses a secure transport scheme.

        Checks if the URL scheme is one of the recognized secure protocols,
        specifically 'https' for HTTP over TLS or 'wss' for WebSocket
        over TLS. This is useful for conditional logic based on transport
        security such as setting secure cookies.

        Returns:
            bool: True if the scheme is 'https' or 'wss', False for
            all other schemes including 'http' and 'ws'.
        """
        return self.scheme in ("https", "wss")

    def replace(self, **kwargs: Any) -> URL:
        """
        Return a new URL with the specified components replaced.

        Creates a new URL instance by replacing one or more of the parsed
        URL components (scheme, netloc, path, query, fragment). When
        hostname, port, username, or password are provided, they are
        combined into a properly formatted netloc value before replacement.

        Args:
            **kwargs: URL component overrides. Accepted keys include
                'scheme', 'netloc', 'path', 'query', 'fragment',
                'hostname', 'port', 'username', and 'password'.

        Returns:
            URL: A new URL instance with the specified components replaced
            while preserving all other components from the original URL.
        """
        if (
            "username" in kwargs
            or "password" in kwargs
            or "hostname" in kwargs
            or "port" in kwargs
        ):
            hostname = kwargs.pop("hostname", None)
            port = kwargs.pop("port", self.port)
            username = kwargs.pop("username", self.username)
            password = kwargs.pop("password", self.password)

            if hostname is None:
                netloc = self.netloc
                _, _, hostname = netloc.rpartition("@")

                if hostname[-1] != "]":
                    hostname = hostname.rsplit(":", 1)[0]

            netloc = hostname
            if port is not None:
                netloc += f":{port}"
            if username is not None:
                userpass = username
                if password is not None:
                    userpass += f":{password}"
                netloc = f"{userpass}@{netloc}"

            kwargs["netloc"] = netloc

        components = self.components._replace(**kwargs)
        return self.__class__(components.geturl())

    def include_query_params(self, **kwargs: Any) -> URL:
        """
        Return a new URL with additional query parameters merged in.

        Parses the existing query string into a MultiDict, merges the
        provided keyword arguments into it (overwriting any existing keys),
        and returns a new URL with the combined query string. Existing
        query parameters that are not specified in kwargs are preserved.

        Args:
            **kwargs: Query parameter key-value pairs to add or update
                in the URL's query string. Values are converted to strings.

        Returns:
            URL: A new URL instance with the merged query parameters.
            The original URL instance is not modified.
        """
        params = MultiDict(parse_qsl(self.query, keep_blank_values=True))
        params.update({str(key): str(value) for key, value in kwargs.items()})
        query = urlencode(params.multi_items())
        return self.replace(query=query)

    def replace_query_params(self, **kwargs: Any) -> URL:
        """
        Return a new URL with query parameters completely replaced.

        Discards all existing query parameters and constructs a new query
        string from the provided keyword arguments. All values are converted
        to strings before encoding into the URL query format.

        Args:
            **kwargs: Query parameter key-value pairs that will form the
                entire new query string. Values are converted to strings.

        Returns:
            URL: A new URL instance with the replacement query parameters.
            The original URL instance and its query string are not modified.
        """
        query = urlencode([(str(key), str(value)) for key, value in kwargs.items()])
        return self.replace(query=query)

    def remove_query_params(self, keys: str | Sequence[str]) -> URL:
        """
        Return a new URL with specified query parameters removed.

        Parses the existing query string and removes all entries matching
        the provided key or keys. All other query parameters are preserved
        in their original order. If a specified key does not exist in the
        query string, it is silently ignored.

        Args:
            keys: A single key string or a sequence of key strings to
                remove from the URL's query parameters.

        Returns:
            URL: A new URL instance with the specified query parameters
                removed. The original URL instance is not modified.
        """
        if isinstance(keys, str):
            keys = [keys]
        params = MultiDict(parse_qsl(self.query, keep_blank_values=True))
        for key in keys:
            params.pop(key, None)
        query = urlencode(params.multi_items())
        return self.replace(query=query)

    def __eq__(self, other: object) -> bool:
        """
        Compare this URL with another object for string equality.

        Performs a direct string comparison between this URL's string
        representation and the other object's string representation.
        This allows URL objects to be compared with other URL objects
        or plain strings for equality.

        Args:
            other: The object to compare against. Can be another URL
                instance or any object that supports str() conversion.

        Returns:
            bool: True if the string representations are equal, False
            otherwise.
        """
        return str(self) == str(other)

    def __str__(self) -> str:
        """
        Return the raw URL string representation.

        Returns the internal URL string as-is, without any additional
        formatting or transformation. This is the canonical string
        representation used by str() and string comparisons.

        Returns:
            str: The complete URL string including scheme, netloc, path,
            query, and fragment components.
        """
        return self._url

    def __repr__(self) -> str:
        """
        Return a developer-friendly representation of the URL.

        Produces a repr string showing the class name and the URL value.
        If the URL contains a password component, it is masked with
        asterisks to prevent accidental exposure of credentials in logs
        and debug output.

        Returns:
            str: A string of the form 'URL('...')' with the password
            masked if present, suitable for debugging and logging.
        """
        url = str(self)
        if self.password:
            url = str(self.replace(password="********"))
        return f"{self.__class__.__name__}({url!r})"


class URLPath(str):
    """
    A URL path string that may also hold an associated protocol and/or host.

    Used by the routing system to return ``url_path_for`` matches. Extends
    the built-in str type so it can be used anywhere a path string is
    expected, while carrying additional metadata about the protocol and
    host that can be used to construct absolute URLs.
    """

    def __new__(cls, path: str, protocol: str = "", host: str = "") -> Self:
        """
        Create a new URLPath instance with the given path string.

        Constructs the str base class with the path value and validates
        that the protocol is one of the allowed values. The protocol and
        host are stored as instance attributes for later use when
        constructing absolute URLs.

        Args:
            path: The URL path string to store as the base value.
            protocol: The protocol associated with this path. Must be
                'http', 'websocket', or an empty string.
            host: The host associated with this path. Defaults to an
                empty string if not specified.

        Raises:
            AssertionError: If protocol is not 'http', 'websocket', or
                an empty string.
        """
        assert protocol in ("http", "websocket", "")
        return str.__new__(cls, path)

    def __init__(self, path: str, protocol: str = "", host: str = "") -> None:
        """
        Initialize the URLPath with protocol and host metadata.

        Stores the protocol and host as instance attributes. These values
        are used by ``make_absolute_url`` to construct full URLs with the
        appropriate scheme and network location.

        Args:
            path: The URL path string. Used by the str base class.
            protocol: The protocol ('http', 'websocket', or ''). This
                determines the scheme used in absolute URL construction.
            host: The hostname for absolute URL construction. If empty,
                the base URL's host will be used instead.
        """
        self.protocol = protocol
        self.host = host

    def make_absolute_url(self, base_url: str | URL) -> URL:
        """
        Construct an absolute URL from this path and a base URL.

        Combines this URLPath with a base URL to produce a complete absolute
        URL. The scheme is determined by the path's protocol (if set) and
        whether the base URL uses a secure connection. The netloc defaults
        to the path's host if set, otherwise uses the base URL's netloc.
        The path is formed by stripping trailing slashes from the base URL's
        path and appending this URLPath's path.

        Args:
            base_url: The base URL to combine with this path. Can be a URL
                string or a URL instance. Provides the scheme and netloc
                when not overridden by the path's protocol and host.

        Returns:
            URL: A new URL instance with the combined scheme, netloc, and
            path components forming a complete absolute URL.
        """
        if isinstance(base_url, str):
            base_url = URL(base_url)
        if self.protocol:
            scheme = {
                "http": {True: "https", False: "http"},
                "websocket": {True: "wss", False: "ws"},
            }[self.protocol][base_url.is_secure]
        else:
            scheme = base_url.scheme

        netloc = self.host or base_url.netloc
        path = base_url.path.rstrip("/") + str(self)
        return URL(scheme=scheme, netloc=netloc, path=path)


class RouteParam:
    """
    A wrapper around route parameter data with attribute-style access.

    Provides a convenient interface for accessing URL route parameters by
    key, attribute name, or iteration. Supports dictionary-like operations
    including get, keys, values, items, and len. Attribute access falls
    through to the underlying data dictionary, allowing route parameters
    to be accessed as object attributes.
    """

    def __init__(self, data: dict[str, Any]) -> None:
        """
        Initialize the RouteParam with a dictionary of route parameters.

        Stores the provided dictionary as the internal data source for
        all parameter lookups. The dictionary is stored by reference,
        not copied, so external modifications to the original dict will
        be reflected in this RouteParam instance.

        Args:
            data: A dictionary mapping route parameter names to their
                extracted values from the URL path pattern match.

        Raises:
            None: No exceptions are raised during initialization.
        """
        """Initialize the RouteParam with a dictionary."""
        self.data: dict[str, Any] = data

    def __iter__(self) -> Iterator[str]:
        """
        Return an iterator over the route parameter names.

        Enables iteration over the RouteParam by delegating to the
        underlying data dictionary's key iterator. Each parameter name
        is yielded exactly once in insertion order.

        Returns:
            Iterator[str]: An iterator yielding each route parameter
            name as a string key from the internal data dictionary.

        Raises:
            None: No exceptions are raised during iteration.
        """
        """Return an iterator over the dictionary keys."""
        return iter(self.data)

    def __getitem__(self, name: str) -> Any:
        """
        Retrieve a route parameter value by its key name.

        Looks up the specified parameter name in the internal data
        dictionary and returns its associated value. Returns None if
        the key does not exist rather than raising a KeyError, making
        this a safe lookup method for optional route parameters.

        Args:
            name: The route parameter name to look up in the internal
                data dictionary.

        Returns:
            Any: The value associated with the given parameter name,
            or None if the parameter does not exist in the route.

        Raises:
            None: No exceptions are raised; returns None for missing keys.
        """
        """Retrieve a value by key, returning None if the key does not exist."""
        return self.data.get(name, None)

    def __getattribute__(self, name: str) -> Any:
        """
        Custom attribute access with fallback to route parameter data.

        Overrides default attribute resolution to first check if the
        requested attribute name exists as a key in the route parameter
        data dictionary. If found, returns the parameter value. Otherwise,
        falls back to standard object attribute resolution via
        ``object.__getattribute__``.

        Args:
            name: The attribute name to resolve. Checked against route
                parameter keys first, then falls back to normal lookup.

        Returns:
            Any: The route parameter value if the name exists in data,
            otherwise the standard object attribute value.

        Raises:
            AttributeError: If the name is not found in data and is not
                a valid object attribute.
        """
        """
        Custom attribute access:
        - If the attribute exists in `data`, return its value.
        - Otherwise, fallback to the default attribute resolution.
        """
        data = object.__getattribute__(self, "data")
        if name in data:
            return data[name]
        return object.__getattribute__(self, name)

    def get_lists(self) -> ItemsView[str, Any]:
        """
        Return all route parameter key-value pairs as an items view.

        Provides access to the complete set of route parameters as an
        ItemsView, which supports iteration and membership testing.
        This is an alias for the ``items()`` method.

        Returns:
            ItemsView[str, Any]: A view of all (name, value) pairs in
            the route parameter data dictionary.

        Raises:
            None: No exceptions are raised during access.
        """
        """Return the dictionary's items (key-value pairs)."""
        return self.data.items()

    def keys(self) -> KeysView[str]:
        """
        Return a view of all route parameter names.

        Provides access to the parameter names as a KeysView, which
        supports iteration and membership testing. Useful for checking
        which parameters were extracted from the URL pattern.

        Returns:
            KeysView[str]: A view containing all parameter name keys
            from the internal data dictionary.

        Raises:
            None: No exceptions are raised during access.
        """
        """Return the dictionary's keys."""
        return self.data.keys()

    def values(self) -> ValuesView[Any]:
        """
        Return a view of all route parameter values.

        Provides access to the parameter values as a ValuesView, which
        supports iteration. The order corresponds to the keys returned
        by the ``keys()`` method.

        Returns:
            ValuesView[Any]: A view containing all parameter values
            from the internal data dictionary.

        Raises:
            None: No exceptions are raised during access.
        """
        """Return the dictionary's values."""
        return self.data.values()

    def items(self) -> ItemsView[str, Any]:
        """
        Return a view of all route parameter key-value pairs.

        Provides access to the complete set of route parameters as an
        ItemsView, which supports iteration and membership testing.
        Equivalent to calling ``get_lists()``.

        Returns:
            ItemsView[str, Any]: A view of all (name, value) pairs in
            the route parameter data dictionary.

        Raises:
            None: No exceptions are raised during access.
        """
        """Return the dictionary's items (key-value pairs)."""
        return self.data.items()

    def __repr__(self) -> str:
        """
        Return a developer-friendly string representation of the RouteParam.

        Produces a repr string showing the class name and the complete
        dictionary of route parameters, useful for debugging and logging
        of extracted URL pattern matches.

        Returns:
            str: A string of the form '<RouteParams {key: value, ...}>'
            showing all extracted route parameters.

        Raises:
            None: No exceptions are raised during representation.
        """
        """Return a string representation of the RouteParam object."""
        return f"<RouteParams {dict(self.data)}>"

    def __len__(self) -> int:
        """
        Return the number of route parameters in the data dictionary.

        Returns the count of unique parameter names extracted from the
        URL pattern match. This reflects the number of keys in the
        internal data dictionary.

        Returns:
            int: The number of route parameters stored in the data
            dictionary. Returns 0 if no parameters were extracted.

        Raises:
            None: No exceptions are raised during length computation.
        """
        """Return the number of items in the dictionary."""
        return len(self.data)

    def __call__(self, *args: Any, **kwds: Any) -> dict[str, Any]:
        """
        Return the underlying route parameter data dictionary.

        Allows the RouteParam instance to be called as a function to
        retrieve the raw dictionary of all route parameters. Arguments
        passed to the call are ignored.

        Args:
            *args: Positional arguments (ignored).
            **kwds: Keyword arguments (ignored).

        Returns:
            Dict[str, Any]: The raw dictionary mapping parameter names
            to their extracted values from the URL pattern match.

        Raises:
            None: No exceptions are raised during the call.
        """
        return self.data

    def get(self, key: str, default: Any = None) -> Any:
        """
        Return the value for a route parameter with an optional default.

        Looks up the specified key in the internal data dictionary and
        returns its associated value. If the key does not exist, returns
        the provided default value instead of raising a KeyError.

        Args:
            key: The route parameter name to look up in the data dict.
            default: The value to return if the key is not found. Defaults
                to None if not explicitly provided.

        Returns:
            Any: The value associated with the given key, or the default
            value if the key does not exist in the route parameters.

        Raises:
            None: No exceptions are raised; returns default for missing keys.
        """
        """Return the value for the given key, or a default value if the key does not exist."""
        return self.data.get(key, default)

    def __dict__(self) -> dict[str, Any]:
        """
        Return the underlying route parameter data dictionary.

        Provides direct access to the internal data dictionary containing
        all route parameters. This method enables dict() conversion of
        the RouteParam instance.

        Returns:
            Dict[str, Any]: The raw dictionary mapping parameter names
            to their extracted values from the URL pattern match.

        Raises:
            None: No exceptions are raised during access.
        """
        return self.data
