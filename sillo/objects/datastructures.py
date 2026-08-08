from __future__ import annotations

import typing

_KeyType = typing.TypeVar("_KeyType")
_CovariantValueType = typing.TypeVar("_CovariantValueType", covariant=True)


class ImmutableMultiDict(typing.Mapping[_KeyType, _CovariantValueType]):
    """
    An immutable mapping that supports multiple values for the same key.

    This data structure extends the standard Mapping interface to support
    storing multiple values per key while maintaining insertion order. It
    provides both single-value access (returning the last value for a key)
    and multi-value access (returning all values for a key). The internal
    storage uses both a dictionary for fast single-value lookups and a list
    of tuples for preserving all key-value pairs including duplicates.

    This class is immutable after construction; use ``MultiDict`` for a
    mutable variant that supports item assignment and deletion.
    """

    _dict: dict[_KeyType, _CovariantValueType]

    def __init__(
        self,
        *args: ImmutableMultiDict[_KeyType, _CovariantValueType]
        | typing.Mapping[_KeyType, _CovariantValueType]
        | typing.Iterable[tuple[_KeyType, _CovariantValueType]],
        **kwargs: typing.Any,
    ) -> None:
        """
        Initializes the ImmutableMultiDict from various input formats.

        Accepts initialization from another ImmutableMultiDict, a standard
        Mapping, an iterable of key-value tuples, or keyword arguments. When
        multiple sources are provided, they are merged together. Duplicate
        keys result in multiple entries being stored, with the last value
        being the one accessible via single-value dictionary access.

        Args:
            *args: Positional arguments that can be an ImmutableMultiDict,
                a Mapping, or an iterable of key-value tuples.
            **kwargs: Additional keyword arguments to merge into the multidict.

        Raises:
            AssertionError: If more than one positional argument is provided.
        """
        assert len(args) < 2, "Too many arguments."

        value: typing.Any = args[0] if args else []
        if kwargs:
            value = (
                ImmutableMultiDict(value).multi_items()
                + ImmutableMultiDict(kwargs).multi_items()  # type: ignore[operator]
            )

        if not value:
            _items: list[tuple[typing.Any, typing.Any]] = []
        elif hasattr(value, "multi_items"):
            value = typing.cast(
                ImmutableMultiDict[_KeyType, _CovariantValueType], value
            )
            _items = list(value.multi_items())
        elif hasattr(value, "items"):
            value = typing.cast(typing.Mapping[_KeyType, _CovariantValueType], value)
            _items = list(value.items())
        else:
            value = typing.cast(list[tuple[typing.Any, typing.Any]], value)
            _items = list(value)

        self._dict = {k: v for k, v in _items}
        self._list = _items

    def getlist(self, key: typing.Any) -> list[_CovariantValueType]:
        """
        Returns all values associated with the given key across all entries.

        Scans the internal list of key-value tuples and collects every value
        whose key matches the provided key argument. This is the primary method
        for accessing all values when a key has been stored multiple times.

        Args:
            key (Any): The key whose associated values should be retrieved
                from the multidict.

        Returns:
            List: A list of all values associated with the given key. Returns
            an empty list if the key does not exist in the multidict.
        """
        return [item_value for item_key, item_value in self._list if item_key == key]

    def keys(self) -> typing.KeysView[_KeyType]:
        """
        Returns a view of all unique keys in the multidict.

        Provides access to the unique keys stored in the internal dictionary.
        Duplicate keys from the multi-value list are collapsed into single
        entries in this view.

        Returns:
            KeysView: A view object containing all unique keys in the multidict.
        """
        return self._dict.keys()

    def values(self) -> typing.ValuesView[_CovariantValueType]:
        """
        Returns a view of the last stored value for each unique key.

        Provides access to values from the internal dictionary, which holds
        only the last value stored for each key. For access to all values
        including duplicates, use ``multi_items`` or ``getlist`` instead.

        Returns:
            ValuesView: A view object containing the last value for each
            unique key in the multidict.
        """
        return self._dict.values()

    def items(self) -> typing.ItemsView[_KeyType, _CovariantValueType]:
        """
        Returns a view of unique key-value pairs from the internal dictionary.

        Provides access to the last stored value for each unique key. For
        access to all key-value pairs including duplicates, use ``multi_items``
        instead.

        Returns:
            ItemsView: A view object containing unique key-value pairs where
            each key maps to its last stored value.
        """
        return self._dict.items()

    def multi_items(self) -> list[tuple[_KeyType, _CovariantValueType]]:
        """
        Returns all key-value pairs including duplicates as a list of tuples.

        Provides access to the complete internal list of key-value tuples,
        preserving all duplicate entries and their insertion order. This is
        the canonical way to iterate over all stored values when keys may
        have multiple associated values.

        Returns:
            List[Tuple]: A list of all key-value tuples including duplicates,
            maintaining their original insertion order.
        """
        return list(self._list)

    def __getitem__(self, key: _KeyType) -> _CovariantValueType:
        """
        Retrieves the last stored value for the given key.

        Looks up the key in the internal dictionary and returns its associated
        value. If the key has multiple stored values, only the last one is
        returned. Raises ``KeyError`` if the key does not exist.

        Args:
            key: The key whose last stored value should be retrieved.

        Returns:
            The last value associated with the given key.

        Raises:
            KeyError: If the key does not exist in the multidict.
        """
        return self._dict[key]

    def __contains__(self, key: typing.Any) -> bool:
        """
        Checks whether the given key exists in the multidict.

        Tests for key membership by checking the internal dictionary. This
        is an O(1) operation due to the underlying hash table implementation.

        Args:
            key (Any): The key to check for existence in the multidict.

        Returns:
            bool: True if the key exists in the multidict, False otherwise.
        """
        return key in self._dict

    def __iter__(self) -> typing.Iterator[_KeyType]:
        """
        Returns an iterator over the unique keys in the multidict.

        Enables iteration over the multidict by delegating to the keys view
        of the internal dictionary. Each unique key is yielded exactly once.

        Returns:
            Iterator: An iterator yielding each unique key in the multidict.
        """
        return iter(self.keys())

    def __len__(self) -> int:
        """
        Returns the number of unique keys in the multidict.

        Returns the length of the internal dictionary, which represents
        the count of unique keys. This does not reflect the total number
        of key-value pairs when duplicates exist.

        Returns:
            int: The number of unique keys stored in the multidict.
        """
        return len(self._dict)

    def __eq__(self, other: object) -> bool:
        """
        Compares this multidict with another for equality.

        Two ImmutableMultiDict instances are considered equal if they contain
        the same set of key-value tuples regardless of order. Comparison with
        objects of other types always returns False.

        Args:
            other (Any): The object to compare against this multidict instance.

        Returns:
            bool: True if both multidicts contain the same sorted key-value
            pairs, False if types differ or contents are not equal.
        """
        if not isinstance(other, self.__class__):
            return False
        return sorted(self._list) == sorted(other._list)

    def __repr__(self) -> str:
        """
        Returns a string representation of the ImmutableMultiDict.

        Produces a developer-friendly representation showing the class name
        and the complete list of key-value tuples including all duplicates.

        Returns:
            str: A string of the form ``ImmutableMultiDict([(key, value), ...])``
            showing all stored key-value pairs.
        """
        class_name = self.__class__.__name__
        items = self.multi_items()
        return f"{class_name}({items!r})"


class MultiDict(ImmutableMultiDict[typing.Any, typing.Any]):
    """
    A mutable multidict that extends ImmutableMultiDict with modification operations.

    This class adds support for item assignment, deletion, and various mutation
    methods on top of the immutable multidict interface. It is used for form data
    and other scenarios where key-value pairs need to be modified after creation.

    All mutation operations maintain consistency between the internal dictionary
    and the list of key-value tuples to ensure correct behavior for both
    single-value and multi-value access patterns.
    """

    def __setitem__(self, key: typing.Any, value: typing.Any) -> None:
        """
        Sets the value for the given key, replacing all existing entries for that key.

        Removes any existing entries for the key and stores a single new entry
        with the provided value. This is equivalent to calling ``setlist`` with
        a single-element list.

        Args:
            key (Any): The key to set in the multidict.
            value (Any): The value to associate with the given key.
        """
        self.setlist(key, [value])

    def __delitem__(self, key: typing.Any) -> None:
        """
        Removes all entries for the given key from the multidict.

        Deletes the key from both the internal dictionary and the list of
        key-value tuples, effectively removing all values associated with
        the key. Raises ``KeyError`` if the key does not exist.

        Args:
            key (Any): The key whose entries should be removed from the multidict.
        """
        self._list = [(k, v) for k, v in self._list if k != key]
        del self._dict[key]

    def pop(self, key: typing.Any, default: typing.Any = None) -> typing.Any:
        """
        Removes and returns the last value for the given key.

        Removes all entries for the key from the multidict and returns the
        last stored value. If the key does not exist, returns the provided
        default value instead of raising an exception.

        Args:
            key (Any): The key to remove from the multidict.
            default (Any): The value to return if the key does not exist.
                Defaults to None.

        Returns:
            Any: The last value associated with the key, or the default value
            if the key was not present in the multidict.
        """
        self._list = [(k, v) for k, v in self._list if k != key]
        return self._dict.pop(key, default)

    def popitem(self) -> tuple[typing.Any, typing.Any]:
        """
        Removes and returns an arbitrary key-value pair from the multidict.

        Pops the last item from the internal dictionary and removes all
        corresponding entries from the key-value tuple list. Raises
        ``KeyError`` if the multidict is empty.

        Returns:
            Tuple[Any, Any]: A tuple containing the removed key and its
            last associated value.

        Raises:
            KeyError: If the multidict is empty and no items can be removed.
        """
        key, value = self._dict.popitem()
        self._list = [(k, v) for k, v in self._list if k != key]
        return key, value

    def poplist(self, key: typing.Any) -> list[typing.Any]:
        """
        Removes all entries for the key and returns all its values as a list.

        Collects all values associated with the key from the internal tuple
        list, then removes the key entirely from the multidict. Returns the
        collected values even if the key did not exist (as an empty list).

        Args:
            key (Any): The key whose values should be collected and removed.

        Returns:
            List[Any]: A list of all values that were associated with the key
            before removal. Returns an empty list if the key was not present.
        """
        values = [v for k, v in self._list if k == key]
        self.pop(key)
        return values

    def clear(self) -> None:
        """
        Removes all key-value pairs from the multidict.

        Clears both the internal dictionary and the key-value tuple list,
        leaving the multidict completely empty. After this operation, the
        multidict has a length of zero and contains no entries.
        """
        self._dict.clear()
        self._list.clear()

    def setdefault(self, key: typing.Any, default: typing.Any = None) -> typing.Any:
        """
        Returns the value for the key, setting it to a default if not present.

        If the key already exists in the multidict, returns its current value
        without modification. If the key does not exist, inserts the default
        value and returns it. The default value is appended to both the
        internal dictionary and the tuple list.

        Args:
            key (Any): The key to look up or set in the multidict.
            default (Any): The value to set if the key does not exist.
                Defaults to None.

        Returns:
            Any: The existing value for the key if present, or the newly
            inserted default value.
        """
        if key not in self:
            self._dict[key] = default
            self._list.append((key, default))

        return self[key]

    def setlist(self, key: typing.Any, values: list[typing.Any]) -> None:
        """
        Replaces all values for the given key with a new list of values.

        Removes any existing entries for the key and inserts new entries for
        each value in the provided list. If the values list is empty, the key
        is removed entirely from the multidict. The last value in the list
        becomes the value accessible via single-value dictionary access.

        Args:
            key (Any): The key whose values should be replaced.
            values (List[Any]): A list of new values to associate with the key.
                If empty, the key is removed from the multidict.
        """
        if not values:
            self.pop(key, None)
        else:
            existing_items = [(k, v) for (k, v) in self._list if k != key]
            self._list = existing_items + [(key, value) for value in values]
            self._dict[key] = values[-1]

    def append(self, key: typing.Any, value: typing.Any) -> None:
        """
        Appends a new value for the given key without removing existing entries.

        Adds a new key-value tuple to the internal list and updates the
        dictionary to reflect the new value. Unlike ``__setitem__``, this
        method preserves any existing entries for the same key, supporting
        the multidict's multi-value semantics.

        Args:
            key (Any): The key to append a value for.
            value (Any): The value to append to the existing entries for the key.
        """
        self._list.append((key, value))
        self._dict[key] = value

    def update(
        self,
        *args: MultiDict
        | typing.Mapping[str, typing.Any]
        | list[tuple[typing.Any, typing.Any]],
        **kwargs: typing.Any,
    ) -> None:
        """
        Updates the multidict with key-value pairs from another source.

        Merges entries from the provided arguments into the current multidict.
        Existing entries for keys that appear in the update source are removed
        and replaced with the new values. Keys that do not appear in the update
        source retain their existing entries.

        Args:
            *args: Can be a MultiDict, a Mapping, or a list of key-value tuples
                to merge into the current multidict.
            **kwargs: Additional keyword arguments to merge as key-value pairs.
        """
        value = MultiDict(*args, **kwargs)
        existing_items = [(k, v) for (k, v) in self._list if k not in value]
        self._list = existing_items + value.multi_items()
        self._dict.update(value)
