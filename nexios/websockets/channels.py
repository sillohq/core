import os
import sys
import time
import typing
import uuid

from nexios import logging as nexios_logger
from nexios.websockets import WebSocket

from .utils import (
    ChannelAddStatusEnum,
    ChannelMessageDC,
    ChannelRemoveStatusEnum,
    GroupSendStatusEnum,
    PayloadTypeEnum,
)

logging = nexios_logger.getLogger("nexios")


class Channel:
    def __init__(
        self,
        websocket: WebSocket,
        payload_type: str,
        expires: typing.Optional[int] = None,
    ) -> None:
        """Main websocket channel class.

        Args:
            websocket (WebSocket): Starlette websocket
            expires (int): Channel ttl in seconds
            encoding (str): encoding of payload (str, bytes, json)
            uuid (str): channel uuid
            created (tim): channel creation time
        """
        assert isinstance(websocket, WebSocket)
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
        if not self.expires:
            return False
        return (self.expires + int(self.created)) < time.time()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__} {self.uuid=} {self.payload_type=} {self.expires=}"


class ChannelBox:
    CHANNEL_GROUPS: typing.Dict[
        str, typing.Any
    ] = {}  # groups of channels ~ key: group_name, val: dict of channels
    CHANNEL_GROUPS_HISTORY: typing.Dict[str, typing.Any] = {}  # history messages
    HISTORY_SIZE: int = int(os.getenv("CHANNEL_BOX_HISTORY_SIZE", 1_048_576))

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

        Args:
            channel (Channel): Instance of Channel class
            group_name (str): Group name
        """
        channel_remove_status: typing.Any = None
        if channel in cls.CHANNEL_GROUPS.get(group_name, {}):
            try:
                del cls.CHANNEL_GROUPS[group_name][channel]
                channel_remove_status = ChannelRemoveStatusEnum.CHANNEL_REMOVED
            except KeyError:
                channel_remove_status = ChannelRemoveStatusEnum.CHANNEL_DOES_NOT_EXIST

        if not any(cls.CHANNEL_GROUPS.get(group_name, {})):
            try:
                del cls.CHANNEL_GROUPS[group_name]
                channel_remove_status = ChannelRemoveStatusEnum.GROUP_REMOVED
            except KeyError:
                channel_remove_status = ChannelRemoveStatusEnum.GROUP_DOES_NOT_EXIST

        await cls._clean_expired()
        return channel_remove_status

    @classmethod
    async def group_send(
        cls,
        group_name: str = "default",
        payload: typing.Union[typing.Dict[str, typing.Any], str, bytes] = {},
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
            cls.CHANNEL_GROUPS_HISTORY.setdefault(group_name, [])
            cls.CHANNEL_GROUPS_HISTORY[group_name].append(
                ChannelMessageDC(
                    payload=payload,  # type:ignore
                )
            )
            if sys.getsizeof(cls.CHANNEL_GROUPS_HISTORY[group_name]) > cls.HISTORY_SIZE:
                cls.CHANNEL_GROUPS_HISTORY[group_name] = []

        group_send_status = GroupSendStatusEnum.NO_SUCH_GROUP
        for channel in cls.CHANNEL_GROUPS.get(group_name, {}):
            await channel._send(payload)
            group_send_status = GroupSendStatusEnum.GROUP_SEND

        return group_send_status

    @classmethod
    async def show_groups(cls) -> typing.Dict[str, typing.Any]:
        return cls.CHANNEL_GROUPS

    @classmethod
    async def flush_groups(cls) -> None:
        cls.CHANNEL_GROUPS = {}

    @classmethod
    async def show_history(
        cls,
        group_name: str = "",
    ) -> typing.Dict[str, typing.Any]:
        return (
            cls.CHANNEL_GROUPS_HISTORY.get(group_name, {})
            if group_name
            else cls.CHANNEL_GROUPS_HISTORY
        )

    @classmethod
    async def flush_history(cls) -> None:
        cls.CHANNEL_GROUPS_HISTORY = {}

    @classmethod
    async def _clean_expired(cls) -> None:
        for group_name in list(cls.CHANNEL_GROUPS):
            for channel in cls.CHANNEL_GROUPS.get(group_name, {}):
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
