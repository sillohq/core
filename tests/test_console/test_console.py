"""Registering commands, dispatching to them, and reporting what went wrong."""

from __future__ import annotations

import io

import pytest

from sillo.console import (
    Abort,
    Argument,
    Command,
    CommandError,
    Console,
    Flag,
    Option,
    strip_ansi,
)


class Greet(Command):
    """Say hello to somebody.

    Repeats as many times as asked.
    """

    name = "app:greet"
    help = "Say hello"
    aliases = ["hi"]
    arguments = [
        Argument("who", help="Who to greet"),
        Option("times", type=int, default=1, short="t", help="How many times"),
        Flag("loud", short="l", help="Shout it"),
    ]

    async def handle(self):
        for _ in range(self.option("times")):
            text = f"Hello, {self.argument('who')}"
            self.line(text.upper() if self.flag("loud") else text)


def build(*commands, **kwargs) -> tuple:
    """A console writing into one buffer, with *commands* registered."""
    stream = io.StringIO()
    console = Console(
        prog="console.py",
        output=stream,
        error=stream,
        input=io.StringIO(),
        color=False,
        interactive=False,
        **kwargs,
    )
    for command in commands:
        console.add(command)
    return console, stream


def output_of(console, stream, argv) -> str:
    """Run *argv* and return what was written, without styling."""
    console.run(argv)
    return strip_ansi(stream.getvalue())


# -- registration ------------------------------------------------------


def test_a_registered_command_can_be_resolved():
    console, _ = build(Greet)

    assert console.resolve("app:greet") is Greet


def test_an_alias_resolves_to_the_same_command():
    console, _ = build(Greet)

    assert console.resolve("hi") is Greet


def test_an_unknown_name_resolves_to_nothing():
    console, _ = build(Greet)

    assert console.resolve("nope") is None


def test_a_command_without_a_name_is_rejected():
    console, _ = build()

    class Nameless(Command):
        pass

    with pytest.raises(ValueError, match="needs a name"):
        console.add(Nameless)


def test_registering_the_same_name_twice_is_rejected():
    console, _ = build(Greet)

    class Other(Command):
        name = "app:greet"

    with pytest.raises(ValueError, match="already registered"):
        console.add(Other)


def test_a_clashing_alias_is_rejected():
    console, _ = build(Greet)

    class Other(Command):
        name = "app:other"
        aliases = ["hi"]

    with pytest.raises(ValueError, match="already registered"):
        console.add(Other)


def test_add_many_registers_each():
    class First(Command):
        name = "a"

    class Second(Command):
        name = "b"

    console, _ = build()
    console.add_many([First, Second])

    assert set(console.commands) == {"a", "b"}


def test_the_registry_is_handed_out_as_a_copy():
    console, _ = build(Greet)

    console.commands["injected"] = Greet

    assert "injected" not in console.commands


# -- dispatch ----------------------------------------------------------


def test_a_command_runs_and_reports_success():
    console, stream = build(Greet)

    assert console.run(["app:greet", "Ada"]) == 0
    assert "Hello, Ada" in stream.getvalue()


def test_options_and_flags_reach_the_command():
    console, stream = build(Greet)

    console.run(["app:greet", "Ada", "-t", "2", "--loud"])

    assert strip_ansi(stream.getvalue()).count("HELLO, ADA") == 2


def test_a_command_runs_through_its_alias():
    console, stream = build(Greet)

    console.run(["hi", "Ada"])

    assert "Hello, Ada" in stream.getvalue()


def test_a_synchronous_handle_is_supported():
    class Sync(Command):
        name = "sync"

        def handle(self):
            self.line("done")

    console, stream = build()
    console.add(Sync)

    assert console.run(["sync"]) == 0
    assert "done" in stream.getvalue()


def test_a_synchronous_handle_may_start_its_own_loop():
    import asyncio

    class Serves(Command):
        name = "serves"

        def handle(self):
            # The shape of `uvicorn.run`: starting a loop from a command only
            # works when the console has not already started one for it.
            asyncio.run(asyncio.sleep(0))
            self.line("served")

    console, stream = build(Serves)

    assert console.run(["serves"]) == 0
    assert "served" in stream.getvalue()


def test_an_integer_return_becomes_the_exit_code():
    class Fails(Command):
        name = "fails"

        async def handle(self):
            return 3

    console, _ = build(Fails)

    assert console.run(["fails"]) == 3


def test_returning_nothing_is_success():
    class Quiet(Command):
        name = "quiet"

        async def handle(self):
            return None

    console, _ = build(Quiet)

    assert console.run(["quiet"]) == 0


def test_a_command_without_handle_says_so():
    class Bare(Command):
        name = "bare"

    console, _ = build(Bare)

    with pytest.raises(NotImplementedError, match="does not define handle"):
        console.run(["bare"])


# -- the context hook --------------------------------------------------


def test_the_context_wraps_the_handler():
    events = []

    class Tracked(Command):
        name = "tracked"

        def context(self):
            class Manager:
                async def __aenter__(inner):
                    events.append("open")

                async def __aexit__(inner, *exception):
                    events.append("close")

            return Manager()

        async def handle(self):
            events.append("handle")

    console, _ = build(Tracked)
    console.run(["tracked"])

    assert events == ["open", "handle", "close"]


def test_the_context_closes_even_when_the_handler_fails():
    events = []

    class Tracked(Command):
        name = "tracked"

        def context(self):
            class Manager:
                async def __aenter__(inner):
                    events.append("open")

                async def __aexit__(inner, *exception):
                    events.append("close")

            return Manager()

        async def handle(self):
            self.fail("no good")

    console, _ = build(Tracked)

    assert console.run(["tracked"]) == 1
    assert events == ["open", "close"]


# -- failures ----------------------------------------------------------


def test_an_unknown_command_exits_two():
    console, stream = build(Greet)

    assert console.run(["nope"]) == 2
    assert "Unknown command 'nope'" in strip_ansi(stream.getvalue())


def test_a_near_miss_is_suggested():
    console, stream = build(Greet)

    console.run(["app:gret"])

    assert "Did you mean app:greet?" in strip_ansi(stream.getvalue())


def test_a_missing_argument_exits_two_with_the_usage_line():
    console, stream = build(Greet)
    written = strip_ansi(output_of(console, stream, ["app:greet"]))

    assert "missing argument <WHO>" in written
    assert "Usage: console.py app:greet <WHO> [options]" in written


def test_a_bad_option_value_exits_two():
    console, stream = build(Greet)

    assert console.run(["app:greet", "Ada", "-t", "many"]) == 2
    assert "not a valid int" in strip_ansi(stream.getvalue())


def test_fail_reports_the_message_and_its_code():
    class Fails(Command):
        name = "fails"

        async def handle(self):
            self.fail("the database is unreachable", exit_code=4)

    console, stream = build(Fails)

    assert console.run(["fails"]) == 4
    assert "the database is unreachable" in strip_ansi(stream.getvalue())


def test_a_command_error_raised_directly_is_reported():
    class Fails(Command):
        name = "fails"

        async def handle(self):
            raise CommandError("nope")

    console, stream = build(Fails)

    assert console.run(["fails"]) == 1
    assert "nope" in strip_ansi(stream.getvalue())


def test_an_abandoned_prompt_exits_one_hundred_and_thirty():
    class Asks(Command):
        name = "asks"

        async def handle(self):
            raise Abort("cancelled")

    console, stream = build(Asks)

    assert console.run(["asks"]) == 130
    assert "Cancelled." in strip_ansi(stream.getvalue())


def test_a_keyboard_interrupt_is_treated_as_a_cancelled_prompt():
    class Interrupted(Command):
        name = "interrupted"

        async def handle(self):
            raise KeyboardInterrupt

    console, _ = build(Interrupted)

    assert console.run(["interrupted"]) == 130


def test_an_unexpected_error_is_not_swallowed():
    class Broken(Command):
        name = "broken"

        async def handle(self):
            raise RuntimeError("a real bug")

    console, _ = build(Broken)

    # A programming error must surface with its traceback rather than being
    # flattened into an exit code.
    with pytest.raises(RuntimeError, match="a real bug"):
        console.run(["broken"])


# -- help --------------------------------------------------------------


def test_no_arguments_prints_the_listing():
    console, stream = build(Greet)

    assert console.run([]) == 0
    assert "app:greet" in strip_ansi(stream.getvalue())


def test_help_prints_the_listing():
    console, stream = build(Greet)

    assert "USAGE" in output_of(console, stream, ["--help"])


def test_commands_are_listed_under_their_group():
    console, stream = build(Greet)
    written = output_of(console, stream, [])

    assert "APP" in written


def test_an_ungrouped_command_is_listed_under_commands():
    class Loose(Command):
        name = "serve"
        help = "Run it"

    console, stream = build(Loose)

    assert "COMMANDS" in output_of(console, stream, [])


def test_a_hidden_command_is_left_out_of_the_listing_but_still_runs():
    class Secret(Command):
        name = "secret"
        hidden = True

        async def handle(self):
            self.line("ran")

    console, stream = build(Secret)

    assert "secret" not in output_of(console, stream, [])
    assert console.run(["secret"]) == 0


def test_a_command_prints_its_own_help():
    console, stream = build(Greet)
    written = output_of(console, stream, ["app:greet", "--help"])

    assert "ARGUMENTS" in written
    assert "Who to greet" in written
    assert "How many times" in written


def test_command_help_shows_an_option_default():
    console, stream = build(Greet)

    assert "[1]" in output_of(console, stream, ["app:greet", "--help"])


def test_command_help_falls_back_to_the_docstring():
    console, stream = build(Greet)

    assert "Repeats as many times as asked." in output_of(
        console, stream, ["app:greet", "--help"]
    )


def test_asking_for_help_does_not_run_the_command():
    console, stream = build(Greet)

    assert "Hello" not in output_of(console, stream, ["app:greet", "Ada", "--help"])


def test_the_version_is_reported_when_one_was_given():
    console, stream = build(Greet, version="1.2.3")

    assert console.run(["--version"]) == 0
    assert "1.2.3" in stream.getvalue()


def test_without_a_version_the_flag_is_not_offered():
    console, stream = build(Greet)

    assert "--version" not in output_of(console, stream, [])


# -- the function form -------------------------------------------------


def test_a_function_can_be_registered_as_a_command():
    console, stream = build()

    @console.command("cache:clear", help="Drop every entry")
    async def clear(command):
        command.line("cleared")

    assert console.run(["cache:clear"]) == 0
    assert "cleared" in stream.getvalue()


def test_a_registered_function_takes_parameters():
    console, stream = build()

    @console.command("echo", arguments=[Argument("text")])
    async def echo(command):
        command.line(command.argument("text"))

    console.run(["echo", "hello"])

    assert "hello" in stream.getvalue()


def test_a_synchronous_function_is_supported():
    console, stream = build()

    @console.command("ping")
    def ping(command):
        command.line("pong")

    assert console.run(["ping"]) == 0
    assert "pong" in stream.getvalue()


def test_a_registered_function_takes_its_help_from_the_docstring():
    console, stream = build()

    @console.command("noop")
    def noop(command):
        """Do nothing at all."""

    assert "Do nothing at all." in output_of(console, stream, [])


# -- sync and async entry points ---------------------------------------


def test_run_drives_the_loop_itself():
    console, stream = build(Greet)

    assert console.run(["app:greet", "Ada"]) == 0
    assert "Hello, Ada" in stream.getvalue()


async def test_run_refuses_to_nest_inside_a_running_loop():
    console, _ = build(Greet)

    with pytest.raises(RuntimeError, match=r"await console\.run_async"):
        console.run(["app:greet", "Ada"])


async def test_run_async_works_inside_a_running_loop():
    console, stream = build(Greet)

    assert await console.run_async(["app:greet", "Ada"]) == 0
    assert "Hello, Ada" in stream.getvalue()


async def test_run_async_reports_usage_errors_the_same_way():
    console, stream = build(Greet)

    assert await console.run_async(["app:greet"]) == 2
    assert "missing argument <WHO>" in strip_ansi(stream.getvalue())
