import typing
from typing import Any, Dict, TypeVar

from .types import HandlerType

F = TypeVar("F", bound=HandlerType)


class RouteDecorator:
    """Base class for all route decorators"""

    def __init__(self, **kwargs: Dict[str, Any]):
        pass

    def __call__(self, handler: HandlerType) -> Any:
        raise NotImplementedError("Handler not set")

    def __get__(self, obj: typing.Any, objtype: typing.Any = None):
        if obj is None:
            return self
        return self.__class__(obj)  # type: ignore
