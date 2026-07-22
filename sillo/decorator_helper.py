"""Decorator helper utilities for route handler decoration.

This module provides the base class for all route decorators in the sillo
framework. Route decorators are used to annotate handler functions with routing
metadata such as HTTP methods, path patterns, and middleware configuration.
"""

import typing
from typing import Any, Dict, TypeVar

from .types import HandlerType

F = TypeVar("F", bound=HandlerType)


class RouteDecorator:
    """Base class for all route decorators in the sillo framework.

    This class provides the foundational interface that all concrete route
    decorators must implement. Route decorators are callable objects that wrap
    handler functions to associate them with routing configuration. They also
    implement the descriptor protocol to support use as method decorators on
    class-based views.

    The decorator pattern allows route configuration to be expressed declaratively
    using Python's decorator syntax, e.g., ``@app.get("/path")``. Subclasses
    should override ``__call__`` to apply their specific routing logic.

    Attributes:
        No public attributes are defined on the base class. Subclasses may add
        attributes for path patterns, HTTP methods, middleware lists, etc.

    Note:
        This class implements ``__get__`` to support the descriptor protocol,
        enabling decorators to work correctly when applied to methods on
        class-based views. When accessed from an instance, a new decorator
        instance is created bound to that instance's handler method.
    """

    def __init__(self, **kwargs: Dict[str, Any]):
        """Initialize the route decorator with optional configuration.

        Accepts arbitrary keyword arguments that subclasses can use to configure
        routing behavior such as path patterns, HTTP methods, response models,
        and middleware. The base implementation accepts but ignores all kwargs.

        Args:
            **kwargs: Arbitrary keyword arguments for subclass-specific route
                configuration. Common parameters include ``path``, ``methods``,
                ``response_model``, ``tags``, and ``summary``.

        Returns:
            None. This is a constructor method.

        Note:
            Subclasses should override this method to process and store their
            specific configuration parameters. The base implementation is a
            no-op to allow flexible subclass design.
        """
        pass

    def __call__(self, handler: HandlerType) -> Any:
        """Apply the decorator to a route handler function.

        This method is invoked when the decorator is used with the ``@`` syntax.
        It receives the handler function and should return a wrapped or annotated
        version that includes the routing configuration.

        Args:
            handler: The route handler function or callable to decorate. This
                is typically an async function that accepts a Request and
                returns a Response.

        Returns:
            The decorated handler. The return type depends on the subclass
            implementation but is typically the handler with attached metadata.

        Raises:
            NotImplementedError: The base class always raises this exception.
                All concrete subclasses must provide their own implementation.

        Note:
            This method must be overridden by subclasses. The base implementation
            serves as an abstract interface definition.
        """
        raise NotImplementedError("Handler not set")

    def __get__(self, obj: typing.Any, objtype: typing.Any = None):
        """Descriptor protocol support for class-based view method decoration.

        Enables route decorators to work correctly when applied to methods on
        class-based views. When accessed through an instance, creates a new
        decorator bound to the instance's method. When accessed through the
        class, returns the decorator itself.

        Args:
            obj: The instance through which the attribute is accessed, or
                ``None`` when accessed through the owner class.
            objtype: The owner class of the descriptor. Ignored when ``obj``
                is ``None``.

        Returns:
            If ``obj`` is ``None``, returns ``self`` (the decorator itself).
            Otherwise, returns a new instance of the decorator's class,
            effectively binding the decorator to the instance's handler method.

        Note:
            This descriptor behavior is essential for supporting decorators on
            methods in class-based views, where the same decorator class needs
            to work with different handler methods on different instances.
        """
        if obj is None:
            return self
        return self.__class__(obj)  # type: ignore
