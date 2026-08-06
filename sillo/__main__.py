"""
sillo.__main__ — the ``sillo`` command.

Installed as a console script, so ``sillo`` is on the path after
``uv add sillo-framework``. ``python -m sillo`` runs the same thing.

A project needs no file of its own. ``sillo`` finds the application, and the
application already knows what the project has: the database manager that
:func:`sillo.record.manager.setup_record` put on ``app.state``, the scheduler
:func:`sillo.work.scheduler.setup_scheduler` put there, the user model it
authenticates against, and whatever commands the project registered with
:meth:`silloApp.add_command`. Everything follows from importing it.

The application is looked for in this order:

1. ``SILLO_APP``, as a ``module:attribute`` import string.
2. ``[tool.sillo] app`` in the working directory's ``pyproject.toml``.
3. The usual places: ``app.main:app``, ``main:app``, ``app:app``.

Outside a project none of those resolve and the framework-level commands are
all that is offered. Creating a project is not one of them: that is
``sillo-start``, which exists so the framework does not carry a copy of the
starter it would have to keep in step.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, List, Optional, Tuple

from .console import Argument, Command, Console, Flag, Option

__all__ = ["build_console", "discover_application", "main"]


#: Names an application is looked for under when nothing points at one.
DEFAULT_APPS = ("app.main:app", "main:app", "app:app")

#: Overrides where the application is imported from.
APP_VARIABLE = "SILLO_APP"

#: The optional feature groups, and the import that proves each is installed.
EXTRAS = {
    "jwt": "jwt",
    "record": "tortoise",
    "cache": "redis",
    "templating": "jinja2",
    "graphql": "strawberry",
    "bcrypt": "bcrypt",
    "argon2": "argon2",
}


def _ensure_cwd_importable() -> None:
    """Put the working directory on the path.

    A console script's ``sys.path`` starts at its own bin directory, so a
    project's packages are not importable without this.
    """
    if str(Path.cwd()) not in sys.path:
        sys.path.insert(0, str(Path.cwd()))


def _import_string(target: str) -> Any:
    """Import the object a ``module:attribute`` string names.

    Args:
        target: An import string, such as ``app.main:app``.

    Returns:
        The named object.

    Raises:
        ValueError: If the string has no colon, or nothing matches.
    """
    if ":" not in target:
        raise ValueError(
            f"{target!r} should be written as 'module:attribute', e.g. 'app.main:app'"
        )

    module_name, _, attribute = target.partition(":")
    _ensure_cwd_importable()

    from importlib import import_module

    try:
        module = import_module(module_name)
    except ImportError as error:
        raise ValueError(f"Could not import {module_name!r}: {error}")

    try:
        return getattr(module, attribute)
    except AttributeError:
        raise ValueError(f"{module_name!r} has no attribute {attribute!r}")


def _configured_app() -> Optional[str]:
    """Read the import string a project configured, if it did.

    Returns:
        The import string from ``SILLO_APP`` or ``[tool.sillo] app``, or None.
    """
    from_environment = os.environ.get(APP_VARIABLE)
    if from_environment:
        return from_environment

    config = Path.cwd() / "pyproject.toml"
    if not config.is_file():
        return None

    try:
        import tomllib

        data = tomllib.loads(config.read_text())
    except Exception:
        # A pyproject that will not parse is the packaging tools' problem to
        # report, not something to fail a console over.
        return None

    app = data.get("tool", {}).get("sillo", {}).get("app")
    return app if isinstance(app, str) else None


def discover_application() -> Tuple[Any, Optional[str]]:
    """Find the project's application.

    Returns:
        The application and None, or ``(None, reason)``. A reason is only
        given when the project pointed at an application and that failed —
        finding nothing in an ordinary directory is not a problem to report.
    """
    configured = _configured_app()
    if configured:
        try:
            return _import_string(configured), None
        except ValueError as error:
            return None, f"{configured} could not be loaded: {error}"

    _ensure_cwd_importable()
    for candidate in DEFAULT_APPS:
        try:
            return _import_string(candidate), None
        except ValueError:
            continue

    return None, None


# -- framework commands ------------------------------------------------


class Version(Command):
    """Report the installed version and what it can do."""

    name = "version"
    help = "Show the installed version and available features"
    aliases = ["about"]

    async def handle(self) -> None:
        import sillo

        self.pairs(
            [
                ("sillo", getattr(sillo, "__version__", "unknown")),
                ("python", sys.version.split()[0]),
                ("path", Path(sillo.__file__).parent),
            ]
        )

        present, absent = self._features()
        self.blank()
        self.line("Optional features")
        for name in present:
            self.bullet(name)
        for name in absent:
            self.muted(f"    {name} — not installed")

    @staticmethod
    def _features() -> Tuple[List[str], List[str]]:
        """Split the optional extras into installed and missing.

        Returns:
            The names that import, and the names that do not.
        """
        from importlib.util import find_spec

        present, absent = [], []
        for name, module in EXTRAS.items():
            try:
                found = find_spec(module) is not None
            except (ImportError, ValueError):
                found = False
            (present if found else absent).append(name)
        return present, absent


class Serve(Command):
    """Run the application with uvicorn."""

    name = "serve"
    help = "Run the application with uvicorn"

    arguments = [
        Argument("app", default=None, help="Import string. Defaults to the app found"),
        Option("host", default="127.0.0.1", help="Interface to bind"),
        Option("port", type=int, default=8000, short="p", help="Port to bind"),
        Flag("reload", short="r", help="Restart when the source changes"),
    ]

    def handle(self) -> Optional[int]:
        """Run the server.

        Synchronous: uvicorn owns the event loop, and starting it from inside
        one would nest two.

        Returns:
            An exit code, or None when the server stopped cleanly.
        """
        try:
            import uvicorn
        except ImportError:
            self.fail("uvicorn is not installed. uv add uvicorn")

        _ensure_cwd_importable()
        target = self.argument("app") or _configured_app() or DEFAULT_APPS[0]

        self.pairs(
            [
                ("app", target),
                ("address", f"http://{self.option('host')}:{self.option('port')}"),
            ]
        )
        self.blank()

        uvicorn.run(
            target,
            host=self.option("host"),
            port=self.option("port"),
            reload=self.flag("reload"),
        )
        return None


class Routes(Command):
    """List the routes the application registers."""

    name = "routes"
    help = "List the application's routes"

    arguments = [
        Argument("app", default=None, help="Import string. Defaults to the app found"),
        Option("method", short="m", help="Only routes accepting this method"),
    ]

    async def handle(self) -> Optional[int]:
        target = self.argument("app")
        if target:
            try:
                application = _import_string(target)
            except ValueError as error:
                self.fail(str(error))
        else:
            application, _ = discover_application()
            if application is None:
                self.fail(
                    "No application found. Name one as an argument, set "
                    f"{APP_VARIABLE}, or add [tool.sillo] app to pyproject.toml."
                )

        routes = getattr(getattr(application, "router", None), "routes", None)
        if routes is None:
            self.fail("That does not look like a sillo application.")

        wanted = (self.option("method") or "").upper()
        rows = []
        for route in routes:
            methods = sorted(getattr(route, "methods", None) or ["WEBSOCKET"])
            if wanted and wanted not in methods:
                continue
            rows.append(
                [
                    ",".join(methods),
                    self._path(route),
                    getattr(route, "name", "") or self._handler_name(route),
                ]
            )

        if not rows:
            self.muted("No routes registered.")
            return None

        rows.sort(key=lambda row: row[1])
        self.table(["method", "path", "name"], rows)
        self.blank()
        self.muted(f"  {len(rows)} routes")
        return None

    @staticmethod
    def _path(route: Any) -> str:
        """The pattern a route matches.

        Args:
            route: The route.

        Returns:
            The path as it was declared. sillo's Route keeps it on
            ``raw_path``; ``path`` exists on some route types and not others,
            so both are tried before giving up.
        """
        return getattr(route, "raw_path", None) or getattr(route, "path", "") or ""

    @staticmethod
    def _handler_name(route: Any) -> str:
        """Name the function a route dispatches to.

        Args:
            route: The route.

        Returns:
            The handler's name, or an empty string.
        """
        handler = getattr(route, "endpoint", None) or getattr(route, "handler", None)
        return getattr(handler, "__name__", "") if handler else ""


#: The commands that need no project.
COMMANDS = [Version, Serve, Routes]


# -- assembling ---------------------------------------------------------


def _register_project(console: Console, application: Any) -> None:
    """Add everything the application implies to *console*.

    What a project gets is decided by what it set up, not by configuration it
    has to repeat somewhere else. A database manager on ``app.state`` means
    migrations and accounts; a scheduler means the schedule commands.

    Args:
        console: The console being assembled.
        application: The project's application.
    """
    state = getattr(application, "state", {}) or {}
    database = state.get("record")
    scheduler = state.get("scheduler")

    if database is not None:
        from sillo.record.console import record_commands
        from sillo.users.console import user_commands

        console.add_many(record_commands(database))
        console.add_many(
            user_commands(
                model=getattr(application, "auth_user_model", None),
                context=database,
            )
        )

    from sillo.work.console import work_commands

    console.add_many(
        work_commands(
            url=os.environ.get("QUEUE_URL") or None,
            scheduler=scheduler,
            context=database,
        )
    )

    # The project's own go on last, so a name it chose wins over a bundled one.
    for command in getattr(application, "commands", []):
        console.add(command, override=True)


def build_console() -> Tuple[Console, Optional[str]]:
    """Assemble the ``sillo`` console.

    Returns:
        The console, and a warning to show when an application was pointed at
        but could not be used.
    """
    import sillo

    console = Console(
        prog="sillo",
        description="The sillo command line.",
        version=getattr(sillo, "__version__", None),
    )
    console.add_many(COMMANDS)

    application, problem = discover_application()
    if application is None:
        return console, problem

    try:
        _register_project(console, application)
    except Exception as error:
        # A project whose wiring raises should not cost the framework commands
        # too — `sillo version` is often what someone runs to find out why.
        return console, f"The application's commands could not be built: {error}"

    return console, None


def main(argv: Optional[List[str]] = None) -> None:
    """Run the ``sillo`` command.

    Args:
        argv: Tokens after the program name. Defaults to ``sys.argv[1:]``.

    Raises:
        SystemExit: Always, with the command's exit code.
    """
    console, warning = build_console()
    if warning:
        console.error_output.warn(warning)

    raise SystemExit(console.run(argv))


if __name__ == "__main__":
    main()
