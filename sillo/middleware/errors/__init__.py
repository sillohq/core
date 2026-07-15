# Backward-compatibility: moved to sillo.error
from sillo.error import ServerErrorMiddleware, ServerErrHandlerType

__all__ = ["ServerErrorMiddleware", "ServerErrHandlerType"]
