class ConfigBase:
    """Base configuration class that provides dictionary-backed attribute access.

    This class serves as a flexible configuration container, allowing configuration
    values to be set via an initial dictionary, keyword arguments, or a combination
    of both. Configuration values can be accessed using standard attribute syntax,
    making it convenient to work with structured configuration data throughout an
    application. The internal storage is a plain dictionary, which can be retrieved
    at any time for serialization or inspection purposes.

    Attributes:
        _config: A dictionary holding all configuration key-value pairs.
    """

    def __init__(self, config=None, **kwargs):
        """Initialize the ConfigBase instance with merged configuration data.

        Constructs the internal configuration dictionary by first incorporating any
        key-value pairs from the provided ``config`` mapping, then overlaying all
        keyword arguments on top. Keyword arguments take precedence over keys in
        the ``config`` mapping when there are collisions, ensuring that explicit
        keyword parameters always win.

        Args:
            config: An optional dictionary (or dict-like mapping) of initial
                configuration key-value pairs. If ``None``, an empty dictionary
                is used as the starting point.
            **kwargs: Arbitrary keyword arguments that are merged into the
                configuration dictionary after ``config``, overriding any
                duplicate keys.

        Returns:
            None

        Raises:
            TypeError: If ``config`` is provided but is not iterable as a
                dictionary (i.e., cannot be converted via ``dict()``).
        """
        data = dict(config or {})
        data.update(kwargs)
        self._config = data

    def __getattr__(self, name):
        """Retrieve a configuration value by attribute name.

        Provides attribute-style access to the underlying configuration dictionary.
        If the requested attribute name exists as a key in the internal ``_config``
        dictionary, its associated value is returned. If the key is not present,
        ``None`` is returned instead of raising an error, allowing safe access to
        optional configuration values without explicit existence checks.

        Args:
            name: The string name of the configuration key to look up as an
                attribute on this instance.

        Returns:
            The value associated with ``name`` in the configuration dictionary,
            or ``None`` if the key does not exist.

        Raises:
            AttributeError: If ``name`` is ``"_config"`` and the internal
                ``_config`` attribute has not yet been initialized, preventing
                infinite recursion during object construction.
        """
        if name == "_config":
            raise AttributeError(name)
        return self._config.get(name)

    def to_dict(self):
        """Return a shallow copy of the internal configuration dictionary.

        Creates and returns a new plain dictionary containing all key-value pairs
        currently stored in the internal ``_config`` attribute. The returned
        dictionary is a shallow copy, meaning that modifications to the returned
        dictionary will not affect the internal state of this ``ConfigBase``
        instance, and vice versa. However, mutable values within the dictionary
        are shared by reference between the copy and the original.

        Args:
            None

        Returns:
            dict: A new dictionary containing all configuration key-value pairs
            stored in this instance at the time of the call.

        Raises:
            None
        """
        return dict(self._config)
