"""
Deprecation warnings for functions and individual parameters.

Both decorators branch on whether the target is a coroutine function, so each
one is exercised in sync and async form.
"""

import asyncio
import warnings

import pytest

from sillo.core.helpers.deprecation import (
    DeprecatedError,
    deprecate_parameter,
    deprecated,
    warn_deprecated,
)


def _run(coro):
    return asyncio.run(coro)


# ── warn_deprecated ──────────────────────────────────────────────────────


def test_warn_deprecated_emits_the_warning_class():
    with pytest.warns(DeprecatedError):
        warn_deprecated("old thing", "0.5.0", "1.0.0")


def test_the_warning_names_both_versions():
    with pytest.warns(DeprecatedError) as caught:
        warn_deprecated("old thing", "0.5.0", "1.0.0")
    text = str(caught[0].message)
    assert "0.5.0" in text
    assert "1.0.0" in text


def test_the_warning_carries_the_message():
    with pytest.warns(DeprecatedError, match="use the new API"):
        warn_deprecated("use the new API", "0.5.0", "1.0.0")


def test_the_warning_is_a_future_warning():
    """FutureWarning is shown to end users by default; DeprecationWarning is
    not, and this is aimed at application authors."""
    assert issubclass(DeprecatedError, FutureWarning)


def test_a_custom_stacklevel_is_accepted():
    with pytest.warns(DeprecatedError):
        warn_deprecated("old", "0.5.0", "1.0.0", stacklevel=1)


# ── the @deprecated decorator ────────────────────────────────────────────


def test_a_deprecated_function_still_works():
    @deprecated(since="0.5.0", removed_in="1.0.0")
    def add(a, b):
        return a + b

    with pytest.warns(DeprecatedError):
        assert add(1, 2) == 3


def test_the_default_message_names_the_function():
    @deprecated(since="0.5.0", removed_in="1.0.0")
    def old_helper():
        return None

    with pytest.warns(DeprecatedError, match="old_helper"):
        old_helper()


def test_a_custom_message_is_used():
    @deprecated(since="0.5.0", removed_in="1.0.0", message="stop using this")
    def old_helper():
        return None

    with pytest.warns(DeprecatedError, match="stop using this"):
        old_helper()


def test_a_replacement_is_named_in_the_warning():
    @deprecated(since="0.5.0", removed_in="1.0.0", replacement="new_helper")
    def old_helper():
        return None

    with pytest.warns(DeprecatedError, match="new_helper"):
        old_helper()


def test_the_decorator_preserves_the_name_and_docstring():
    @deprecated(since="0.5.0", removed_in="1.0.0")
    def documented():
        """Original docstring."""

    assert documented.__name__ == "documented"
    assert documented.__doc__ == "Original docstring."


def test_arguments_are_forwarded_unchanged():
    @deprecated(since="0.5.0", removed_in="1.0.0")
    def takes_everything(a, b=2, *args, **kwargs):
        return (a, b, args, kwargs)

    with pytest.warns(DeprecatedError):
        assert takes_everything(1, 3, 4, key="v") == (1, 3, (4,), {"key": "v"})


def test_the_warning_fires_on_every_call():
    @deprecated(since="0.5.0", removed_in="1.0.0")
    def old_helper():
        return None

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        old_helper()
        old_helper()
    assert len(caught) == 2


def test_an_exception_from_the_wrapped_function_propagates():
    @deprecated(since="0.5.0", removed_in="1.0.0")
    def raises():
        raise ValueError("boom")

    with pytest.warns(DeprecatedError), pytest.raises(ValueError, match="boom"):
        raises()


def test_a_deprecated_async_function_still_works():
    @deprecated(since="0.5.0", removed_in="1.0.0")
    async def fetch():
        return "value"

    with pytest.warns(DeprecatedError):
        assert _run(fetch()) == "value"


def test_the_async_wrapper_stays_a_coroutine_function():
    """Wrapping must not turn an awaitable into a plain call."""
    import inspect

    @deprecated(since="0.5.0", removed_in="1.0.0")
    async def fetch():
        return "value"

    assert inspect.iscoroutinefunction(fetch)


def test_a_deprecated_method_works():
    class Service:
        @deprecated(since="0.5.0", removed_in="1.0.0")
        def legacy(self, value):
            return value * 2

    with pytest.warns(DeprecatedError):
        assert Service().legacy(3) == 6


# ── the @deprecate_parameter decorator ───────────────────────────────────


def test_no_warning_when_the_parameter_is_absent():
    @deprecate_parameter("old_flag", since="0.5.0", removed_in="1.0.0")
    def handler(value, old_flag=None):
        return value

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert handler("x") == "x"
    assert caught == []


def test_the_warning_fires_when_the_parameter_is_passed():
    @deprecate_parameter("old_flag", since="0.5.0", removed_in="1.0.0")
    def handler(value, old_flag=None):
        return old_flag

    with pytest.warns(DeprecatedError, match="old_flag"):
        assert handler("x", old_flag=True) is True


def test_the_warning_names_the_function_too():
    @deprecate_parameter("old_flag", since="0.5.0", removed_in="1.0.0")
    def handler(value, old_flag=None):
        return None

    with pytest.warns(DeprecatedError, match="handler"):
        handler("x", old_flag=True)


def test_a_replacement_parameter_is_named():
    @deprecate_parameter(
        "old_flag", since="0.5.0", removed_in="1.0.0", replacement="new_flag"
    )
    def handler(value, old_flag=None, new_flag=None):
        return None

    with pytest.warns(DeprecatedError, match="new_flag"):
        handler("x", old_flag=True)


def test_only_keyword_use_is_detected():
    """The check looks in kwargs, so passing the argument positionally slips
    past silently — a known limit of the keyword-only check."""

    @deprecate_parameter("old_flag", since="0.5.0", removed_in="1.0.0")
    def handler(value, old_flag=None):
        return old_flag

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert handler("x", True) is True
    assert caught == []


def test_parameter_deprecation_on_an_async_function():
    @deprecate_parameter("old_flag", since="0.5.0", removed_in="1.0.0")
    async def handler(value, old_flag=None):
        return old_flag

    with pytest.warns(DeprecatedError):
        assert _run(handler("x", old_flag="y")) == "y"


def test_an_async_function_without_the_parameter_does_not_warn():
    @deprecate_parameter("old_flag", since="0.5.0", removed_in="1.0.0")
    async def handler(value, old_flag=None):
        return value

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert _run(handler("x")) == "x"
    assert caught == []


def test_parameter_deprecation_preserves_the_name():
    @deprecate_parameter("old_flag", since="0.5.0", removed_in="1.0.0")
    def handler(value, old_flag=None):
        return value

    assert handler.__name__ == "handler"
