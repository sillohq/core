import os
import time
import typing
import uuid
from typing import ClassVar

from sillo import logging as sillo_logger
from sillo.websockets import WebSocketContext

from .history import BaseHistoryManager, InMemoryHistoryManager
from .utils import (
    ChannelAddStatusEnum,
    ChannelMessageDC,
    ChannelRemoveStatusEnum,
    GroupSendStatusEnum,
    PayloadTypeEnum,
)

logging = sillo_logger.getLogger("sillo")

#: Sentinel for dict.pop, so a stored ``None`` is not mistaken for "absent".
_MISSING = object()


class Channel:
    """Channel"""

    def __init__(
        self,
        websocket: WebSocketContext,
        payload_type: str,
        expires: int | None = None,
    ) -> None:
        """Main websocket channel class.

        Args:
            websocket (WebSocketContext): Starlette websocket
            expires (int): Channel ttl in seconds
            encoding (str): encoding of payload (str, bytes, json)
            uuid (str): channel uuid
            created (tim): channel creation time
        """
        assert isinstance(websocket, WebSocketContext)
        if expires:
            assert isinstance(expires, int)
        assert isinstance(payload_type, str) and payload_type in [
            PayloadTypeEnum.JSON.value,
            PayloadTypeEnum.TEXT.value,
            PayloadTypeEnum.BYTES.value,
        ]

        self.websocket = websocket
        self.expires = expires
        self.payload_type = payload_type
        self.uuid = uuid.uuid4()
        self.created = time.time()

    async def _send(self, payload: typing.Any) -> None:
        """Send"""
        try:
            if self.payload_type == "json":
                await self.websocket.send_json(payload)
            elif self.payload_type == "text":
                await self.websocket.send_text(payload)
            elif self.payload_type == "bytes":
                await self.websocket.send_bytes(payload)
            else:
                await self.websocket.send(payload)
        except RuntimeError as error:
            logging.debug(error)

        self.created = time.time()

    async def _is_expired(self) -> bool:
        """Is Expired"""
        if not self.expires:
            return False
        return (self.expires + int(self.created)) < time.time()

    def __repr__(self) -> str:
        """Repr"""
        return f"{self.__class__.__name__} {self.uuid=} {self.payload_type=} {self.expires=}"


class ChannelBox:
    """Channelbox"""

    # Groups of channels ~ key: group_name, val: dict of channels.
    CHANNEL_GROUPS: ClassVar[dict[str, typing.Any]] = {}
    HISTORY_SIZE: int = int(os.getenv("CHANNEL_BOX_HISTORY_SIZE", "1048576"))
    HISTORY_MANAGER: BaseHistoryManager = InMemoryHistoryManager(
        history_size=int(os.getenv("CHANNEL_BOX_HISTORY_SIZE", "1048576"))
    )

    @classmethod
    async def add_channel_to_group(
        cls,
        channel: Channel,
        group_name: str = "default",
    ) -> ChannelAddStatusEnum:
        """Add channel to group.

        Args:
            channel (Channel): Instance of Channel class
            group_name (str): Group name

        """
        assert group_name, "Group name must to be set."

        if group_name not in cls.CHANNEL_GROUPS:
            cls.CHANNEL_GROUPS[group_name] = {}
            channel_add_status = ChannelAddStatusEnum.CHANNEL_ADDED
        else:
            channel_add_status = ChannelAddStatusEnum.CHANNEL_EXIST

        cls.CHANNEL_GROUPS[group_name][channel] = ...
        return channel_add_status

    @classmethod
    async def remove_channel_from_group(
        cls,
        channel: Channel,
        group_name: str,
    ) -> ChannelRemoveStatusEnum:
        """Remove channel from group.

        Removing a channel that is not in the group, or removing from a group
        that does not exist, is not an error — both are ordinary outcomes of a
        disconnect racing a cleanup, and are reported through the return value.

        Args:
            channel (Channel): Instance of Channel class
            group_name (str): Group name

        Returns:
            ``GROUP_DOES_NOT_EXIST`` when there is no such group,
            ``CHANNEL_DOES_NOT_EXIST`` when the group has no such channel,
            ``GROUP_REMOVED`` when the channel was the last one and the empty
            group was discarded, and ``CHANNEL_REMOVED`` otherwise.
        """
        group = cls.CHANNEL_GROUPS.get(group_name)
        if group is None:
            await cls._clean_expired()
            return ChannelRemoveStatusEnum.GROUP_DOES_NOT_EXIST

        if group.pop(channel, _MISSING) is _MISSING:
            await cls._clean_expired()
            return ChannelRemoveStatusEnum.CHANNEL_DOES_NOT_EXIST

        if not group:
            cls.CHANNEL_GROUPS.pop(group_name, None)
            await cls._clean_expired()
            return ChannelRemoveStatusEnum.GROUP_REMOVED

        await cls._clean_expired()
        return ChannelRemoveStatusEnum.CHANNEL_REMOVED

    @classmethod
    def set_history_manager(cls, manager: BaseHistoryManager) -> None:
        """Set a custom history manager.

        Args:
            manager: Instance of a class that implements BaseHistoryManager

        Example:
            >>> from sillo.websockets import ChannelBox, NoOpHistoryManager
            >>> ChannelBox.set_history_manager(NoOpHistoryManager())
        """
        cls.HISTORY_MANAGER = manager

    @classmethod
    async def group_send(
        cls,
        group_name: str = "default",
        payload: dict[str, typing.Any] | str | bytes = {},
        save_history: bool = False,
    ) -> GroupSendStatusEnum:
        """Send payload to all channels connected to group.

        Args:
            group_name (str, optional): Group name
            payload (dict, optional): Payload to channel
            save_history (bool, optional): Save message history. Defaults to False.

        """
        assert group_name, "Group name must to be set."

        if save_history:
            message = ChannelMessageDC(
                payload=payload,  # type: ignore
            )
            await cls.HISTORY_MANAGER.save_message(group_name, message)

        group_send_status = GroupSendStatusEnum.NO_SUCH_GROUP
        for channel in cls.CHANNEL_GROUPS.get(group_name, {}):
            await channel._send(payload)
            group_send_status = GroupSendStatusEnum.GROUP_SEND

        return group_send_status

    @classmethod
    async def show_groups(cls) -> dict[str, typing.Any]:
        """Show Groups"""
        return cls.CHANNEL_GROUPS

    @classmethod
    async def flush_groups(cls) -> None:
        """Flush Groups"""
        cls.CHANNEL_GROUPS = {}

    @classmethod
    async def show_history(
        cls,
        group_name: str = "",
    ) -> list[ChannelMessageDC] | dict[str, list[ChannelMessageDC]]:
        """Get message history for a group or all groups.

        Args:
            group_name: Optional group name. If empty, returns all history.

        Returns:
            List of messages if group_name is provided, otherwise dict of all histories
        """
        return await cls.HISTORY_MANAGER.get_history(group_name if group_name else None)

    @classmethod
    async def flush_history(cls, group_name: str | None = None) -> None:
        """Flush message history.

        Args:
            group_name: Optional group name. If provided, only flushes that group's history.
                       If None, flushes all history.
        """
        await cls.HISTORY_MANAGER.flush_history(group_name)

    @classmethod
    async def _clean_expired(cls) -> None:
        """Clean Expired"""
        for group_name in list(cls.CHANNEL_GROUPS):
            # Snapshot the channels too — the loop deletes from the same dict,
            # which otherwise raises "dictionary changed size during iteration"
            # the moment any channel in the group has actually expired.
            for channel in list(cls.CHANNEL_GROUPS.get(group_name, {})):
                _is_expired = await channel._is_expired()
                if _is_expired:
                    try:
                        del cls.CHANNEL_GROUPS[group_name][channel]
                    except KeyError:
                        logging.debug("No such channel")

            if not any(cls.CHANNEL_GROUPS.get(group_name, {})):
                try:
                    del cls.CHANNEL_GROUPS[group_name]
                except KeyError:
                    logging.debug("No such group")

    @classmethod
    async def close_all_connections(cls) -> None:
        """
        Close all WebSocket connections in all groups.
        """
        for group_name, channels in cls.CHANNEL_GROUPS.items():
            for channel in list(
                channels.keys()
            ):  # Use list() to avoid RuntimeError due to dict size change
                try:
                    await channel.websocket.close()
                    logging.debug(
                        f"Closed connection for channel {channel.uuid} in group {group_name}"
                    )
                except Exception as e:
                    logging.error(
                        f"Failed to close connection for channel {channel.uuid}: {e}"
                    )

        cls.CHANNEL_GROUPS = {}
        logging.debug("All connections closed and groups cleared.")
