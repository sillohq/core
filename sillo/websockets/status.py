"""
WebSocket close status codes.

See the IANA WebSocket close-code registry:
https://www.iana.org/assignments/websocket/websocket.xml#close-code-number
"""

from __future__ import annotations

import warnings

__all__ = (
    "WS_1000_NORMAL_CLOSURE",
    "WS_1001_GOING_AWAY",
    "WS_1002_PROTOCOL_ERROR",
    "WS_1003_UNSUPPORTED_DATA",
    "WS_1005_NO_STATUS_RCVD",
    "WS_1006_ABNORMAL_CLOSURE",
    "WS_1007_INVALID_FRAME_PAYLOAD_DATA",
    "WS_1008_POLICY_VIOLATION",
    "WS_1009_MESSAGE_TOO_BIG",
    "WS_1010_MANDATORY_EXT",
    "WS_1011_INTERNAL_ERROR",
    "WS_1012_SERVICE_RESTART",
    "WS_1013_TRY_AGAIN_LATER",
    "WS_1014_BAD_GATEWAY",
    "WS_1015_TLS_HANDSHAKE",
)

WS_1000_NORMAL_CLOSURE = 1000
WS_1001_GOING_AWAY = 1001
WS_1002_PROTOCOL_ERROR = 1002
WS_1003_UNSUPPORTED_DATA = 1003
WS_1005_NO_STATUS_RCVD = 1005
WS_1006_ABNORMAL_CLOSURE = 1006
WS_1007_INVALID_FRAME_PAYLOAD_DATA = 1007
WS_1008_POLICY_VIOLATION = 1008
WS_1009_MESSAGE_TOO_BIG = 1009
WS_1010_MANDATORY_EXT = 1010
WS_1011_INTERNAL_ERROR = 1011
WS_1012_SERVICE_RESTART = 1012
WS_1013_TRY_AGAIN_LATER = 1013
WS_1014_BAD_GATEWAY = 1014
WS_1015_TLS_HANDSHAKE = 1015

__deprecated__ = {"WS_1004_NO_STATUS_RCVD": 1004, "WS_1005_ABNORMAL_CLOSURE": 1005}


def __getattr__(name: str) -> int:
    deprecation_changes = {
        "WS_1004_NO_STATUS_RCVD": "WS_1005_NO_STATUS_RCVD",
        "WS_1005_ABNORMAL_CLOSURE": "WS_1006_ABNORMAL_CLOSURE",
    }
    deprecated = __deprecated__.get(name)
    if deprecated:
        warnings.warn(
            f"'{name}' is deprecated. Use '{deprecation_changes[name]}' instead.",
            category=DeprecationWarning,
            stacklevel=3,
        )
        return deprecated
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


def __dir__() -> list[str]:
    return sorted(list(__all__) + list(__deprecated__.keys()))
