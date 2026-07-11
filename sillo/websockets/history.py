import sys
import typing
from abc import ABC, abstractmethod

from .utils import ChannelMessageDC


class BaseHistoryManager(ABC):
    """Abstract base class for channel history managers.

    This allows users to implement custom history storage backends
    (e.g., Redis, database, file-based) for WebSocket channel messages.
    """

    @abstractmethod
    async def save_message(
        self,
        group_name: str,
        message: ChannelMessageDC,
    ) -> None:
        """Save a message to history for a specific group.

        Args:
            group_name: The name of the channel group
            message: The message to save
        """
        pass

    @abstractmethod
    async def get_history(
        self,
        group_name: typing.Optional[str] = None,
    ) -> typing.Union[
        typing.List[ChannelMessageDC], typing.Dict[str, typing.List[ChannelMessageDC]]
    ]:
        """Retrieve message history.

        Args:
            group_name: Optional group name. If provided, returns history for that group.
                       If None, returns history for all groups.

        Returns:
            List of messages if group_name is provided, otherwise dict of group_name -> messages
        """
        pass

    @abstractmethod
    async def flush_history(self, group_name: typing.Optional[str] = None) -> None:
        """Clear message history.

        Args:
            group_name: Optional group name. If provided, clears history for that group.
                       If None, clears all history.
        """
        pass


class InMemoryHistoryManager(BaseHistoryManager):
    """Default in-memory history manager.

    Stores message history in memory with a configurable size limit per group.
    When the size limit is exceeded, the history for that group is cleared.

    Args:
        history_size: Maximum size in bytes for each group's history (default: 1MB)
    """

    def __init__(self, history_size: int = 1_048_576):
        self.history_size = history_size
        self._history: typing.Dict[str, typing.List[ChannelMessageDC]] = {}

    async def save_message(
        self,
        group_name: str,
        message: ChannelMessageDC,
    ) -> None:
        """Save a message to in-memory history."""
        if group_name not in self._history:
            self._history[group_name] = []

        self._history[group_name].append(message)

        # Check size and clear if exceeded
        if sys.getsizeof(self._history[group_name]) > self.history_size:
            self._history[group_name] = []

    async def get_history(
        self,
        group_name: typing.Optional[str] = None,
    ) -> typing.Union[
        typing.List[ChannelMessageDC], typing.Dict[str, typing.List[ChannelMessageDC]]
    ]:
        """Retrieve message history from memory."""
        if group_name:
            return self._history.get(group_name, [])
        return self._history

    async def flush_history(self, group_name: typing.Optional[str] = None) -> None:
        """Clear message history from memory."""
        if group_name:
            if group_name in self._history:
                del self._history[group_name]
        else:
            self._history = {}


class NoOpHistoryManager(BaseHistoryManager):
    """No-operation history manager that doesn't store anything.

    Useful when you don't need message history and want to avoid
    the memory overhead of storing messages.
    """

    async def save_message(
        self,
        group_name: str,
        message: ChannelMessageDC,
    ) -> None:
        """Does nothing - messages are not saved."""
        pass

    async def get_history(
        self,
        group_name: typing.Optional[str] = None,
    ) -> typing.Union[
        typing.List[ChannelMessageDC], typing.Dict[str, typing.List[ChannelMessageDC]]
    ]:
        """Returns empty history."""
        if group_name:
            return []
        return {}

    async def flush_history(self, group_name: typing.Optional[str] = None) -> None:
        """Does nothing - no history to flush."""
        pass
