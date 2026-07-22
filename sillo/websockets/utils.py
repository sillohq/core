import typing
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID


class ChannelAddStatusEnum(Enum):
    """Channeladdstatusenum

    Returns:
        [description]

    Raises:
        [description]
    """

    CHANNEL_ADDED = "CHANNEL_ADDED"
    CHANNEL_EXIST = "CHANNEL_EXIST"


class ChannelRemoveStatusEnum(Enum):
    """Channelremovestatusenum

    Returns:
        [description]

    Raises:
        [description]
    """

    CHANNEL_REMOVED = "CHANNEL_REMOVED"
    CHANNEL_DOES_NOT_EXIST = "CHANNEL_DOES_NOT_EXIST"
    GROUP_REMOVED = "GROUP_REMOVED"
    GROUP_DOES_NOT_EXIST = "GROUP_DOES_NOT_EXIST"


class GroupSendStatusEnum(Enum):
    """Groupsendstatusenum

    Returns:
        [description]

    Raises:
        [description]
    """

    GROUP_SEND = "GROUP_SEND"
    NO_SUCH_GROUP = "NO_SUCH_GROUP"


class PayloadTypeEnum(Enum):
    """Payloadtypeenum

    Returns:
        [description]

    Raises:
        [description]
    """

    JSON = "json"
    TEXT = "text"
    BYTES = "bytes"


@dataclass
class ChannelMessageDC:
    """Channelmessagedc

    Returns:
        [description]

    Raises:
        [description]
    """

    payload: typing.Union[str, bytes]
    uuid: UUID = uuid.uuid4()
    created: datetime = datetime.now(tz=timezone.utc)
