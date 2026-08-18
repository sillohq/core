"""
sillo.__main__ — the ``sillo`` command.

Installed as a console script, so ``sillo`` is on the path after
``uv add sillo-framework``. ``python -m sillo`` runs the same thing.

A project needs no file of its own. ``sillo`` finds the application, and the
application already knows what the project has: the database manager that
:func:`sillo.record.manager.setup_record` put on ``app.state``, the scheduler
:func:`sillo.work.scheduler.setup_scheduler` put there, the user model it
authenticates against, and whatever commands the project registered with
:meth:`SilloApp.add_command`. Everything follows from importing it.

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
from typing import Any, ClassVar

from sillo.env import autoload

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


def _configured_app() -> str | None:
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
        text = config.read_text()
    except OSError:
        return None

    in_sillo = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_sillo = stripped == "[tool.sillo]"
            continue
        if in_sillo and stripped.startswith("app = "):
            value = stripped[len("app = ") :].strip()
            if value.startswith('"') and value.endswith('"'):
                return value[1:-1]
            if value.startswith("'") and value.endswith("'"):
                return value[1:-1]
    return None


def discover_application_string() -> str | None:
    """Find the import string naming the project's application.

    The sibling of :func:`discover_application`, which returns the object. The
    server needs the *string*: ``--reload`` and ``--workers`` re-import the
    application in a fresh process, and an already-imported object cannot
    survive that.

    Returns:
        The configured or discovered import string, or None when neither a
        configuration nor any of :data:`DEFAULT_APPS` resolves.
    """
    configured = _configured_app()
    if configured:
        return configured

    _ensure_cwd_importable()
    for candidate in DEFAULT_APPS:
        try:
            _import_string(candidate)
        except ValueError:
            continue
        return candidate

    return None


def discover_application() -> tuple[Any, str | None]:
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
    aliases: ClassVar[list[str]] = ["about"]

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
    def _features() -> tuple[list[str], list[str]]:
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
    """Run the application on the Sillo server."""

    name = "serve"
    help = "Run the application on the Sillo server"

    arguments: ClassVar[list] = [
        Argument("app", default=None, help="Import string. Defaults to the app found"),
        Option("host", default="127.0.0.1", help="Interface to bind"),
        Option("port", type=int, default=8000, short="p", help="Port to bind"),
        Option("workers", type=int, default=1, short="w", help="Worker processes"),
        Option(
            "log-level",
            default="info",
            help="debug, info, warning or error",
        ),
        Flag("reload", short="r", help="Restart when the source changes"),
        Flag("no-access-log", help="Do not log a line per request"),
        Flag(
            "no-inspect",
            help="Do not mount the clickable request inspector",
        ),
        Flag(
            "plain",
            help="Use uvicorn's own output instead of Sillo's",
        ),
    ]

    def handle(self) -> int | None:
        """Run the server.

        Synchronous: the server owns the event loop, and starting it from
        inside one would nest two.

        Returns:
            An exit code, or None when the server stopped cleanly.
        """
        _ensure_cwd_importable()
        # `DEFAULT_APPS` is a list of candidates to try, and this used to take
        # `DEFAULT_APPS[0]` and nothing else. So "Defaults to the app found"
        # meant "assumes app.main:app", and the most ordinary layout of all,
        # a `main.py` in the working directory, failed with a bare
        # `ModuleNotFoundError: No module named 'app'` raised from inside
        # importlib rather than anything naming the real problem.
        target = self.argument("app") or discover_application_string()
        if target is None:
            self.fail(
                "No application found. Looked for "
                + ", ".join(DEFAULT_APPS)
                + ". Name one as an argument (sillo serve main:app), set "
                f"{APP_VARIABLE}, or add [tool.sillo] app to pyproject.toml."
            )

        if self.flag("plain"):
            # An escape hatch, for anyone diagnosing a problem who needs to see
            # what uvicorn itself is saying rather than Sillo's rendering of it.
            try:
                import uvicorn
            except ImportError:
                self.fail("uvicorn is not installed. uv add uvicorn")

            uvicorn.run(
                target,
                host=self.option("host"),
                port=self.option("port"),
                workers=self.option("workers"),
                log_level=self.option("log-level"),
                reload=self.flag("reload"),
            )
            return None

        from sillo.server import run

        try:
            run(
                target,
                host=self.option("host"),
                port=self.option("port"),
                workers=self.option("workers"),
                log_level=self.option("log-level"),
                reload=self.flag("reload"),
                access_log=not self.flag("no-access-log"),
                inspect=not self.flag("no-inspect"),
            )
        except RuntimeError as error:
            self.fail(str(error))
        return None


class Routes(Command):
    """List the routes the application registers."""

    name = "routes"
    help = "List the application's routes"

    arguments: ClassVar[list] = [
        Argument("app", default=None, help="Import string. Defaults to the app found"),
        Option("method", short="m", help="Only routes accepting this method"),
    ]

    async def handle(self) -> int | None:
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
        for methods, path, name in self._walk(routes):
            if wanted and wanted not in methods:
                continue
            rows.append([",".join(methods), path, name])

        if not rows:
            self.muted("No routes registered.")
            return None

        rows.sort(key=lambda row: row[1])
        self.table(["method", "path", "name"], rows)
        self.blank()
        self.muted(f"  {len(rows)} routes")
        return None

    @classmethod
    def _walk(cls, routes: Any, prefix: str = "") -> list[Any]:
        """Flatten *routes*, descending into mounted routers.

        A mounted router is one entry in ``router.routes`` holding routes of
        its own, and its children carry paths relative to the mount. Listing
        only the top level shows ``/api`` and hides every route under it, which
        is the opposite of what someone runs this to find out.

        Args:
            routes: Routes to walk.
            prefix: Path the enclosing mount is under.

        Returns:
            Tuples of methods, full path, and name.
        """
        found = []
        for route in routes:
            path = prefix + cls._path(route)
            children = getattr(route, "routes", None)

            if children:
                found.extend(cls._walk(children, path))
                continue

            methods = getattr(route, "methods", None)
            if methods:
                label = sorted(methods)
            elif "websocket" in type(route).__name__.lower():
                label = ["WEBSOCKET"]
            else:
                # A mount with nothing under it — a static directory, say.
                # Calling it WEBSOCKET because it declares no methods would be
                # a guess, and a wrong one.
                label = ["MOUNT"]

            found.append(
                (label, path, getattr(route, "name", "") or cls._handler_name(route))
            )
        return found

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


def build_console() -> tuple[Console, str | None]:
    """Assemble the ``sillo`` console.

    Returns:
        The console, and a warning to show when an application was pointed at
        but could not be used.
    """
    import sillo

    # Before the project is imported, so a module that reads os.environ at
    # import time sees what .env says. Nothing has to install python-dotenv.
    autoload()

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


def main(argv: list[str] | None = None) -> None:
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
