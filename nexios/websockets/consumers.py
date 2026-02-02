import json
import typing
import uuid

from nexios import logging, status

from .base import WebSocket
from .channels import Channel, ChannelBox, PayloadTypeEnum

Message = typing.MutableMapping[str, typing.Any]


class WebSocketConsumer:
    channel: typing.Optional[Channel] = None
    middleware: typing.List[typing.Any] = []

    encoding: typing.Optional[str] = None

    def __init__(
        self,
        logging_enabled: bool = True,
        logger: typing.Optional[logging.Logger] = None,
    ):
        """
        Args:
            logging_enabled: Whether logging is enabled for this endpoint.
            logger: A custom logger instance. If not provided, the default logger will be used.
        """
        self.logging_enabled = logging_enabled
        self.logger = logger if logger else logging.getLogger("nexios")

    @classmethod
    def as_route(cls, path: str):
        from nexios.routing import WebsocketRoute

        """
        Convert the WebSocketConsumer class into a Route that can be registered with the app or router.
        """

        async def handler(
            websocket: WebSocket, **kwargs: typing.Dict[str, typing.Any]
        ) -> None:
            instance = cls()
            await instance(websocket, **kwargs)

        return WebsocketRoute(path, handler, middleware=cls.middleware)

    async def __call__(self, ws: WebSocket) -> None:
        self.websocket = ws

        self.channel = Channel(
            websocket=self.websocket,
            expires=3600,  # Set your desired TTL for the channel
            payload_type=(
                PayloadTypeEnum.JSON.value
                if self.encoding == "json"
                else PayloadTypeEnum.TEXT.value
            ),
        )
        await self.on_connect(self.websocket)

        close_code = status.WS_1000_NORMAL_CLOSURE

        try:
            while True:
                message = await self.websocket.receive()
                if message["type"] == "websocket.receive":
                    data = await self.decode(self.websocket, message)
                    await self.on_receive(self.websocket, data)
                elif message["type"] == "websocket.disconnect":
                    close_code = int(
                        message.get("code") or status.WS_1000_NORMAL_CLOSURE
                    )
                    break
        except Exception as exc:
            close_code = status.WS_1011_INTERNAL_ERROR
            raise exc
        finally:
            await self.on_disconnect(self.websocket, close_code)

    async def decode(self, websocket: WebSocket, message: Message) -> typing.Any:
        if self.encoding == "text":
            if "text" not in message:
                await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
                raise RuntimeError("Expected text websocket messages, but got bytes")
            return message["text"]

        elif self.encoding == "bytes":
            if "bytes" not in message:
                await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
                raise RuntimeError("Expected bytes websocket messages, but got text")
            return message["bytes"]

        elif self.encoding == "json":
            if message.get("text") is not None:
                text = message["text"]
            else:
                text = message["bytes"].decode("utf-8")

            try:
                return json.loads(text)
            except json.decoder.JSONDecodeError:
                await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
                raise RuntimeError("Malformed JSON data received.")

        assert self.encoding is None, (
            f"Unsupported 'encoding' attribute {self.encoding}"
        )
        return message["text"] if message.get("text") else message["bytes"]

    async def on_connect(self, websocket: WebSocket) -> None:
        """Override to handle an incoming websocket connection"""
        await websocket.accept()
        if self.logging_enabled:
            self.logger.info("New WebSocket connection established")

    async def on_receive(self, websocket: WebSocket, data: typing.Any) -> None:
        """Override to handle an incoming websocket message"""
        if self.logging_enabled:
            self.logger.info(f"Received message: {data}")

    async def on_disconnect(self, websocket: WebSocket, close_code: int) -> None:
        """Override to handle a disconnecting websocket"""
        if self.logging_enabled:
            self.logger.info(f"WebSocket disconnected with code: {close_code}")

    # New Methods for Channel and Group Management
    async def broadcast(
        self,
        payload: typing.Any,
        group_name: str = "default",
        save_history: bool = False,
    ) -> None:
        """
        Broadcast a message to all channels in a group.
        Args:
            payload: The message payload to broadcast.
            group_name: The name of the group to broadcast to.
            save_history: Whether to save the message in the group's history.
        """
        await ChannelBox.group_send(
            group_name=group_name, payload=payload, save_history=save_history
        )
        if self.logging_enabled:
            self.logger.info(f"Broadcasted message to group '{group_name}': {payload}")

    async def send_to(self, channel_id: uuid.UUID, payload: typing.Any) -> None:
        """
        Send a message to a specific channel by its ID.
        Args:
            channel_id: The UUID of the target channel.
            payload: The message payload to send.
        """
        for _, channels in ChannelBox.CHANNEL_GROUPS.items():
            for channel in channels:
                if channel.uuid == channel_id:
                    await channel._send(payload)
                    if self.logging_enabled:
                        self.logger.info(
                            f"Sent message to channel {channel_id}: {payload}"
                        )
                    return
        if self.logging_enabled:
            self.logger.warning(f"Channel with ID {channel_id} not found.")

    async def group(self, group_name: str) -> typing.List[Channel]:
        """
        Get all channels in a specific group.
        Args:
            group_name: The name of the group.
        Returns:
            A list of channels in the group.
        """
        channels = list(ChannelBox.CHANNEL_GROUPS.get(group_name, {}).keys())
        if self.logging_enabled:
            self.logger.info(
                f"Retrieved channels in group '{group_name}': {len(channels)} channels"
            )
        return channels

    async def join_group(self, group_name: str) -> None:
        """
        Add the current channel to a group.
        Args:
            group_name: The name of the group to join.
        """
        if self.channel:
            await ChannelBox.add_channel_to_group(self.channel, group_name=group_name)
            if self.logging_enabled:
                self.logger.info(f"Channel joined group '{group_name}'")

    async def leave_group(self, group_name: str) -> None:
        """
        Remove the current channel from a group.
        Args:
            group_name: The name of the group to leave.
        """
        if self.channel:
            await ChannelBox.remove_channel_from_group(
                self.channel, group_name=group_name
            )
            if self.logging_enabled:
                self.logger.info(f"Channel left group '{group_name}'")
