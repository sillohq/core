"""The ``sillo`` command: its own commands, and the application it discovers.

A project registers commands on its application and ``sillo`` finds them there.
There is no file to write and nothing to point at in the ordinary case, so most
of what is worth testing is the discovery: where the application is looked for,
what is derived from it, and what happens when there is none.
"""

from __future__ import annotations

import io
import textwrap

import pytest

from sillo.__main__ import (
    APP_VARIABLE,
    DEFAULT_APPS,
    Routes,
    Version,
    _configured_app,
    _import_string,
    build_console,
    discover_application,
)
from sillo.console import Argument, Command, Console, strip_ansi


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    """Start each test with nothing pointing at an application.

    The modules these tests write are also dropped afterwards. Without that,
    ``import main`` in one test hands back the module a previous test wrote,
    and discovery appears to find an application in an empty directory.
    """
    monkeypatch.delenv(APP_VARIABLE, raising=False)
    monkeypatch.delenv("QUEUE_URL", raising=False)

    import sys

    before = set(sys.modules)
    yield
    for name in set(sys.modules) - before:
        sys.modules.pop(name, None)


@pytest.fixture
def elsewhere(tmp_path, monkeypatch):
    """A working directory with no application in it."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


def write_app(directory, body: str, name: str = "main.py") -> None:
    """Write an application module into *directory*."""
    (directory / name).write_text(textwrap.dedent(body))


PLAIN_APP = """
    from sillo import silloApp

    app = silloApp(title="Plain")

    @app.get("/things")
    async def things(request, response):
        return response.json([])
    """


def run(console, argv) -> tuple:
    """Run *argv* against *console*, capturing what it wrote."""
    stream = io.StringIO()
    console.output.stream = stream
    console.output.palette.enabled = False
    console.error_output.stream = stream
    console.error_output.palette.enabled = False
    code = console.run(argv)
    return code, strip_ansi(stream.getvalue())


# -- the framework's own commands --------------------------------------


def test_the_framework_commands_are_always_available(elsewhere):
    console, warning = build_console()

    assert warning is None
    assert {"version", "serve", "routes"} <= set(console.commands)


def test_creating_a_project_is_not_one_of_them(elsewhere):
    # Scaffolding lives in sillo-start; the framework does not carry a copy of
    # the starter it would have to keep in step.
    console, _ = build_console()

    assert "new" not in console.commands


def test_version_reports_the_installed_version(elsewhere):
    import sillo

    console, _ = build_console()
    code, written = run(console, ["version"])

    assert code == 0
    assert sillo.__version__ in written


def test_version_reports_which_extras_are_present(elsewhere):
    console, _ = build_console()
    _, written = run(console, ["version"])

    assert "Optional features" in written


def test_version_is_reachable_as_about(elsewhere):
    console, _ = build_console()

    assert console.resolve("about") is console.resolve("version")


def test_the_features_split_into_present_and_absent():
    present, absent = Version._features()

    assert present
    assert set(present) | set(absent)


# -- finding the application -------------------------------------------


def test_nothing_is_found_in_an_ordinary_directory(elsewhere):
    application, problem = discover_application()

    assert application is None
    # Not finding an application where none was configured is not a problem
    # worth reporting; plenty of directories are not projects.
    assert problem is None


def test_an_application_is_found_by_convention(elsewhere, monkeypatch):
    write_app(elsewhere, PLAIN_APP)
    monkeypatch.syspath_prepend(str(elsewhere))

    application, problem = discover_application()

    assert problem is None
    assert application is not None


@pytest.mark.parametrize("candidate", DEFAULT_APPS)
def test_each_conventional_name_is_an_import_string(candidate):
    module, _, attribute = candidate.partition(":")

    assert attribute == "app"
    assert module in ("app.main", "main", "app")


def test_the_environment_variable_points_at_one(elsewhere, monkeypatch):
    write_app(elsewhere, PLAIN_APP, name="somewhere_else.py")
    monkeypatch.syspath_prepend(str(elsewhere))
    monkeypatch.setenv(APP_VARIABLE, "somewhere_else:app")

    application, problem = discover_application()

    assert problem is None
    assert application.openapi_config.openapi_spec.info.title == "Plain"


def test_pyproject_points_at_one(elsewhere, monkeypatch):
    write_app(elsewhere, PLAIN_APP, name="configured.py")
    (elsewhere / "pyproject.toml").write_text('[tool.sillo]\napp = "configured:app"\n')
    monkeypatch.syspath_prepend(str(elsewhere))

    assert _configured_app() == "configured:app"

    application, problem = discover_application()
    assert problem is None
    assert application is not None


def test_the_environment_variable_wins_over_pyproject(elsewhere, monkeypatch):
    (elsewhere / "pyproject.toml").write_text('[tool.sillo]\napp = "from_file:app"\n')
    monkeypatch.setenv(APP_VARIABLE, "from_env:app")

    assert _configured_app() == "from_env:app"


def test_a_pyproject_without_the_section_configures_nothing(elsewhere):
    (elsewhere / "pyproject.toml").write_text('[project]\nname = "thing"\n')

    assert _configured_app() is None


def test_an_unparseable_pyproject_is_not_fatal(elsewhere):
    (elsewhere / "pyproject.toml").write_text("this is not toml {{{")

    assert _configured_app() is None


def test_an_application_that_will_not_import_is_reported(elsewhere, monkeypatch):
    monkeypatch.setenv(APP_VARIABLE, "no_such_module:app")

    application, problem = discover_application()

    assert application is None
    assert "could not be loaded" in problem


def test_a_broken_application_leaves_the_framework_commands(elsewhere, monkeypatch):
    monkeypatch.setenv(APP_VARIABLE, "no_such_module:app")

    console, warning = build_console()

    # `sillo version` is often what someone runs to work out why; it must not
    # be taken down by the thing they are diagnosing.
    assert warning is not None
    assert "version" in console.commands


# -- what the application implies --------------------------------------


DATABASE_APP = """
    from sillo import silloApp
    from sillo.record import DatabaseConfig, setup_record

    app = silloApp(title="With database")

    database = setup_record(
        app,
        DatabaseConfig(url="sqlite://:memory:"),
        model_modules=["sillo.users.base"],
    )
    database.set_migrations("migrations_pkg")
    """


def test_a_database_brings_the_migration_and_account_commands(elsewhere, monkeypatch):
    write_app(elsewhere, DATABASE_APP, name="with_db.py")
    monkeypatch.syspath_prepend(str(elsewhere))
    monkeypatch.setenv(APP_VARIABLE, "with_db:app")

    console, warning = build_console()

    assert warning is None
    assert "db:migrate" in console.commands
    assert "user:admin" in console.commands


def test_no_database_means_no_migration_commands(elsewhere, monkeypatch):
    write_app(elsewhere, PLAIN_APP, name="plain_only.py")
    monkeypatch.syspath_prepend(str(elsewhere))
    monkeypatch.setenv(APP_VARIABLE, "plain_only:app")

    console, warning = build_console()

    assert warning is None
    assert "db:migrate" not in console.commands
    assert "user:admin" not in console.commands


def test_the_queue_commands_are_offered_regardless(elsewhere, monkeypatch):
    write_app(elsewhere, PLAIN_APP, name="plain_queue.py")
    monkeypatch.syspath_prepend(str(elsewhere))
    monkeypatch.setenv(APP_VARIABLE, "plain_queue:app")

    console, _ = build_console()

    assert "queue:list" in console.commands


SCHEDULER_APP = """
    from sillo import silloApp
    from sillo.work.scheduler import setup_scheduler

    app = silloApp()
    scheduler = setup_scheduler(app)

    @scheduler.cron("0 3 * * *", name="prune")
    async def prune():
        pass
    """


def test_a_scheduler_on_the_app_reaches_the_schedule_commands(elsewhere, monkeypatch):
    write_app(elsewhere, SCHEDULER_APP, name="with_scheduler.py")
    monkeypatch.syspath_prepend(str(elsewhere))
    monkeypatch.setenv(APP_VARIABLE, "with_scheduler:app")

    console, _ = build_console()
    code, written = run(console, ["schedule:list"])

    assert code == 0
    assert "prune" in written


def test_without_a_scheduler_the_command_says_how_to_bind_one(elsewhere, monkeypatch):
    write_app(elsewhere, PLAIN_APP, name="plain_sched.py")
    monkeypatch.syspath_prepend(str(elsewhere))
    monkeypatch.setenv(APP_VARIABLE, "plain_sched:app")

    console, _ = build_console()
    code, _ = run(console, ["schedule:list"])

    assert code == 1


def test_the_user_model_comes_from_the_application(elsewhere, monkeypatch):
    write_app(
        elsewhere,
        """
        from sillo import silloApp
        from sillo.record import DatabaseConfig, setup_record
        from sillo.users.base import User

        app = silloApp(auth_user_model=User)
        setup_record(
            app,
            DatabaseConfig(url="sqlite://:memory:"),
            model_modules=["sillo.users.base"],
        )
        """,
        name="with_model.py",
    )
    monkeypatch.syspath_prepend(str(elsewhere))
    monkeypatch.setenv(APP_VARIABLE, "with_model:app")

    from sillo.users.base import User

    console, _ = build_console()

    assert console.resolve("user:admin").config.model is User


# -- commands the project registers -------------------------------------


REGISTERED_APP = """
    from sillo import silloApp
    from sillo.console import Argument, Command

    app = silloApp()


    class Backfill(Command):
        name = "posts:backfill"
        help = "Backfill post slugs"

        arguments = [Argument("since", default=None)]

        async def handle(self):
            self.success(f"from {self.argument('since') or 'the beginning'}")


    app.add_command(Backfill)


    @app.command("cache:clear", help="Drop every cached entry")
    async def clear(command):
        command.success("Cache cleared.")
    """


def test_a_command_registered_on_the_app_is_available(elsewhere, monkeypatch):
    write_app(elsewhere, REGISTERED_APP, name="registered.py")
    monkeypatch.syspath_prepend(str(elsewhere))
    monkeypatch.setenv(APP_VARIABLE, "registered:app")

    console, _ = build_console()
    code, written = run(console, ["posts:backfill"])

    assert code == 0
    assert "from the beginning" in written


def test_a_registered_command_takes_its_arguments(elsewhere, monkeypatch):
    write_app(elsewhere, REGISTERED_APP, name="registered_args.py")
    monkeypatch.syspath_prepend(str(elsewhere))
    monkeypatch.setenv(APP_VARIABLE, "registered_args:app")

    console, _ = build_console()
    _, written = run(console, ["posts:backfill", "2024-01-01"])

    assert "from 2024-01-01" in written


def test_the_decorator_form_registers_too(elsewhere, monkeypatch):
    write_app(elsewhere, REGISTERED_APP, name="registered_decorated.py")
    monkeypatch.syspath_prepend(str(elsewhere))
    monkeypatch.setenv(APP_VARIABLE, "registered_decorated:app")

    console, _ = build_console()
    code, written = run(console, ["cache:clear"])

    assert code == 0
    assert "Cache cleared." in written


def test_a_projects_name_wins_over_a_bundled_one(elsewhere, monkeypatch):
    write_app(
        elsewhere,
        """
        from sillo import silloApp
        from sillo.console import Command
        from sillo.record import DatabaseConfig, setup_record

        app = silloApp()
        setup_record(app, DatabaseConfig(url="sqlite://:memory:"))


        class OwnMigrate(Command):
            name = "db:migrate"
            help = "The project's own"

            async def handle(self):
                self.line("project migrate")


        app.add_command(OwnMigrate)
        """,
        name="overriding.py",
    )
    monkeypatch.syspath_prepend(str(elsewhere))
    monkeypatch.setenv(APP_VARIABLE, "overriding:app")

    console, _ = build_console()
    code, written = run(console, ["db:migrate"])

    assert code == 0
    assert "project migrate" in written


# -- registering on the application -------------------------------------


def test_add_command_returns_the_class_so_it_can_decorate():
    from sillo import silloApp

    app = silloApp()

    @app.add_command
    class Thing(Command):
        name = "thing"

        async def handle(self):
            pass

    assert Thing in app.commands


def test_a_command_without_a_name_is_refused():
    from sillo import silloApp

    app = silloApp()

    class Nameless(Command):
        pass

    with pytest.raises(ValueError, match="needs a name"):
        app.add_command(Nameless)


def test_registering_the_same_name_twice_is_refused():
    from sillo import silloApp

    app = silloApp()

    class First(Command):
        name = "same"

    class Second(Command):
        name = "same"

    app.add_command(First)
    with pytest.raises(ValueError, match="already registered"):
        app.add_command(Second)


def test_the_decorator_builds_a_command_from_a_function():
    from sillo import silloApp

    app = silloApp()

    @app.command("ping", help="Say pong", arguments=[Argument("to", default="world")])
    async def ping(command):
        command.line(f"pong {command.argument('to')}")

    assert len(app.commands) == 1
    assert app.commands[0].name == "ping"
    assert app.commands[0].help == "Say pong"


def test_a_fresh_application_has_no_commands():
    from sillo import silloApp

    assert silloApp().commands == []


# -- import strings ----------------------------------------------------


def test_an_import_string_resolves_an_object():
    assert _import_string("sillo:__version__")


def test_an_import_string_without_a_colon_is_rejected():
    with pytest.raises(ValueError, match="module:attribute"):
        _import_string("sillo")


def test_an_unimportable_module_is_reported():
    with pytest.raises(ValueError, match="Could not import"):
        _import_string("no_such_module_at_all:app")


def test_a_missing_attribute_is_reported():
    with pytest.raises(ValueError, match="has no attribute"):
        _import_string("sillo:not_a_real_attribute")


# -- routes ------------------------------------------------------------


def test_routes_uses_the_discovered_application(elsewhere, monkeypatch):
    write_app(elsewhere, PLAIN_APP, name="routed.py")
    monkeypatch.syspath_prepend(str(elsewhere))
    monkeypatch.setenv(APP_VARIABLE, "routed:app")

    console, _ = build_console()
    code, written = run(console, ["routes"])

    assert code == 0
    assert "/things" in written


def test_routes_accepts_an_explicit_import_string(elsewhere, monkeypatch):
    write_app(elsewhere, PLAIN_APP, name="named_app.py")
    monkeypatch.syspath_prepend(str(elsewhere))

    console, _ = build_console()
    code, written = run(console, ["routes", "named_app:app"])

    assert code == 0
    assert "/things" in written


def test_routes_can_filter_by_method(elsewhere, monkeypatch):
    write_app(
        elsewhere,
        """
        from sillo import silloApp

        app = silloApp()

        @app.get("/only-get")
        async def a(request, response):
            return response.json([])

        @app.post("/only-post")
        async def b(request, response):
            return response.json([])
        """,
        name="filtered.py",
    )
    monkeypatch.syspath_prepend(str(elsewhere))

    console, _ = build_console()
    _, written = run(console, ["routes", "filtered:app", "-m", "post"])

    assert "/only-post" in written
    assert "/only-get" not in written


def test_routes_with_no_application_says_how_to_name_one(elsewhere):
    console, _ = build_console()
    code, written = run(console, ["routes"])

    assert code == 1
    assert APP_VARIABLE in written


def test_routes_on_something_that_is_not_an_app_fails(elsewhere):
    console, _ = build_console()
    code, written = run(console, ["routes", "sillo:__version__"])

    assert code == 1
    assert "does not look like a sillo application" in written


def test_the_path_comes_from_raw_path():
    class Route:
        raw_path = "/widgets/{id:int}"

    assert Routes._path(Route()) == "/widgets/{id:int}"


def test_the_handler_name_is_used_when_a_route_has_no_name():
    def list_widgets():
        pass

    class Route:
        endpoint = staticmethod(list_widgets)

    assert Routes._handler_name(Route()) == "list_widgets"


# -- the console script ------------------------------------------------


def test_main_exits_with_the_commands_code(elsewhere):
    from sillo.__main__ import main

    with pytest.raises(SystemExit) as caught:
        main(["version"])

    assert caught.value.code == 0


def test_main_exits_two_on_an_unknown_command(elsewhere):
    from sillo.__main__ import main

    with pytest.raises(SystemExit) as caught:
        main(["no-such-command"])

    assert caught.value.code == 2


def test_the_console_script_is_declared():
    # The entry point is why `sillo` exists on PATH after an install; losing it
    # is silent until somebody installs the package.
    from pathlib import Path

    try:
        import tomllib
    except ModuleNotFoundError:  # 3.10
        import tomli as tomllib

    root = Path(__file__).resolve().parents[2]
    config = tomllib.loads((root / "pyproject.toml").read_text())

    assert config["project"]["scripts"]["sillo"] == "sillo.__main__:main"


def test_the_console_is_a_console(elsewhere):
    console, _ = build_console()

    assert isinstance(console, Console)
    assert console.prog == "sillo"


def test_routes_descends_into_mounted_routers(elsewhere, monkeypatch):
    """A mounted router is one entry holding routes of its own.

    Listing only the top level shows `/api` and hides every route under it,
    which is the opposite of what someone runs this to find out.
    """
    write_app(
        elsewhere,
        """
        from sillo import Router, silloApp

        app = silloApp()
        api = Router(prefix="/api")

        @api.get("/health")
        async def health(request, response):
            return response.json({})

        @api.post("/items")
        async def create_item(request, response):
            return response.json({})

        app.mount_router(api)
        """,
        name="mounted.py",
    )
    monkeypatch.syspath_prepend(str(elsewhere))

    console, _ = build_console()
    code, written = run(console, ["routes", "mounted:app"])

    assert code == 0
    assert "/api/health" in written
    assert "/api/items" in written


def test_a_mount_is_not_labelled_a_websocket(elsewhere, monkeypatch):
    # Groups declare no methods. Calling them WEBSOCKET because of that is a
    # guess, and a wrong one — /api is a mounted router, not a socket.
    write_app(
        elsewhere,
        """
        from sillo import Router, silloApp

        app = silloApp()
        api = Router(prefix="/api")

        @api.get("/health")
        async def health(request, response):
            return response.json({})

        app.mount_router(api)
        """,
        name="not_a_socket.py",
    )
    monkeypatch.syspath_prepend(str(elsewhere))

    console, _ = build_console()
    _, written = run(console, ["routes", "not_a_socket:app"])

    assert "WEBSOCKET" not in written


def test_a_real_websocket_is_labelled(elsewhere, monkeypatch):
    write_app(
        elsewhere,
        """
        from sillo import silloApp

        app = silloApp()

        @app.ws_route("/ws")
        async def socket(ws):
            pass
        """,
        name="with_socket.py",
    )
    monkeypatch.syspath_prepend(str(elsewhere))

    console, _ = build_console()
    _, written = run(console, ["routes", "with_socket:app"])

    assert "WEBSOCKET" in written
    assert "/ws" in written


def test_filtering_by_method_reaches_mounted_routes(elsewhere, monkeypatch):
    write_app(
        elsewhere,
        """
        from sillo import Router, silloApp

        app = silloApp()
        api = Router(prefix="/api")

        @api.get("/health")
        async def health(request, response):
            return response.json({})

        @api.post("/items")
        async def create_item(request, response):
            return response.json({})

        app.mount_router(api)
        """,
        name="mounted_filter.py",
    )
    monkeypatch.syspath_prepend(str(elsewhere))

    console, _ = build_console()
    _, written = run(console, ["routes", "mounted_filter:app", "-m", "post"])

    assert "/api/items" in written
    assert "/api/health" not in written


def test_pyproject_configuration_works_without_tomllib(elsewhere, monkeypatch):
    """tomllib is 3.11+, and sillo supports 3.10.

    The first version of this read pyproject inside a bare `except Exception`,
    so on 3.10 the missing parser looked exactly like "no app configured" and
    [tool.sillo] silently did nothing.
    """
    (elsewhere / "pyproject.toml").write_text('[tool.sillo]\napp = "somewhere:app"\n')

    assert _configured_app() == "somewhere:app"


def test_the_pyproject_parser_falls_back_when_tomllib_is_absent(tmp_path):
    """On 3.10 there is no tomllib, and sillo supports 3.10.

    Run in a subprocess with tomllib blocked and tomli standing in, which is
    exactly the 3.10 arrangement. CI caught the first version of this on 3.10
    after it passed locally on 3.12.
    """
    import subprocess
    import sys
    import textwrap

    (tmp_path / "tomli.py").write_text(
        "from tomllib_real import loads, TOMLDecodeError\n"
    )
    # A stand-in that forwards to the real parser under the older name.
    (tmp_path / "tomllib_real.py").write_text(
        "import tomllib as _t\nloads = _t.loads\nTOMLDecodeError = _t.TOMLDecodeError\n"
    )
    (tmp_path / "pyproject.toml").write_text('[tool.sillo]\napp = "configured:app"\n')

    script = textwrap.dedent(
        """
        import sys

        real_tomllib = __import__("tomllib")
        sys.modules["tomllib_real"] = real_tomllib


        class Blocked:
            def find_spec(self, name, path=None, target=None):
                if name == "tomllib":
                    raise ModuleNotFoundError("No module named 'tomllib'")
                return None


        del sys.modules["tomllib"]
        sys.meta_path.insert(0, Blocked())

        from sillo.__main__ import _configured_app

        print(_configured_app())
        """
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "PYTHONPATH": str(tmp_path)},
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "configured:app"
