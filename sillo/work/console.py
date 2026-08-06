"""
sillo.work.console — queues, workers and the scheduler, as console commands.

``sillo.work.commands`` supplies the operations as plain functions. This binds
them to a broker and gives them names, arguments and output::

    from sillo.console import Console
    from sillo.work.console import work_commands

    console = Console(prog="python console.py")
    console.add_many(
        work_commands(
            url=os.getenv("QUEUE_URL"),
            queues=["mail", "reports"],
            scheduler=lambda: manager,
        )
    )

Two things are worth knowing before reading the commands.

Without a ``redis://`` URL the queue is a :class:`SyncConnection`, which lives
in the worker's own process. Nothing dispatched from a web process reaches it,
so ``queue:work`` says so rather than sitting at zero and looking healthy.

The failed-job repository defaults to the in-memory one, which is empty in a
fresh process. ``queue:failed`` reports that distinction instead of printing
"no failures" at somebody about to go home.
"""

from __future__ import annotations

from typing import Any, Callable, ClassVar, List, Optional, Type, Union

from sillo.console import Argument, Command, Flag, Option

__all__ = ["work_commands"]


Source = Union[Any, Callable[[], Any], None]

#: Queue consumed when a project names none.
DEFAULT_QUEUE = "default"


def _resolve(value: Source) -> Any:
    """Call *value* when it is a factory, otherwise return it.

    Args:
        value: A value, a callable returning one, or None.

    Returns:
        The value.
    """
    if value is None:
        return None
    return value() if callable(value) else value


class _Config:
    """What the work commands were bound to.

    Args:
        url: Broker URL. None keeps the queue in-process.
        queues: Queues to consume, highest priority first.
        prefix: Key prefix for Redis.
        scheduler: A SchedulerManager, or a callable returning one.
        failed: A failed-job repository, or a callable returning one.
        context: An async context manager opened around every command.
    """

    def __init__(
        self,
        url: Optional[str],
        queues: Optional[List[str]],
        prefix: str,
        scheduler: Source,
        failed: Source,
        context: Source,
    ) -> None:
        self.url = url
        self.queues = list(queues) if queues else [DEFAULT_QUEUE]
        self.prefix = prefix
        self.scheduler = scheduler
        self.failed = failed
        self.context = context

    @property
    def shared(self) -> bool:
        """Whether the queue is reachable from another process.

        Returns:
            True for a broker URL, False for the in-process queue.
        """
        return bool(self.url)


class WorkCommand(Command):
    """Base for the queue and scheduler commands.

    Attributes:
        config: Set by :func:`work_commands` on a subclass.
    """

    config: ClassVar[Optional[_Config]] = None

    def context(self) -> Any:
        """Open the bound context manager around the command.

        Returns:
            The context manager, or None.
        """
        return _resolve(self.config.context) if self.config else None

    @property
    def settings(self) -> _Config:
        """The bound configuration.

        Returns:
            The configuration.

        Raises:
            RuntimeError: If the command was registered directly instead of
                through :func:`work_commands`.
        """
        if self.config is None:
            raise RuntimeError(
                f"{type(self).__name__} is not configured. Register it with "
                f"work_commands(...) rather than adding the class directly."
            )
        return self.config

    def connection(self) -> Any:
        """Build the queue connection this console was bound to.

        Returns:
            A connection to the broker, or an in-process one.
        """
        from .commands import connection_for

        return connection_for(self.settings.url, prefix=self.settings.prefix)

    def repository(self) -> Any:
        """The failed-job repository to read.

        Returns:
            The bound repository, or a fresh in-memory one.
        """
        from .queue import MemoryFailedRepository

        return _resolve(self.settings.failed) or MemoryFailedRepository()

    def manager(self) -> Any:
        """The scheduler this console was bound to.

        Returns:
            The scheduler manager.

        Raises:
            CommandError: If none was bound, since there is nothing to report.
        """
        manager = _resolve(self.settings.scheduler)
        if manager is None:
            self.fail(
                "No scheduler was bound to this console. Pass "
                "work_commands(scheduler=...) with the manager your project "
                "registers tasks on."
            )
        return manager

    def warn_if_in_process(self) -> None:
        """Say so when the queue cannot be reached from another process."""
        if not self.settings.shared:
            self.warn("This queue is in-process.")
            self.muted(
                "  Jobs dispatched by a web process land in that process, not "
                "here. Set a redis:// URL to share one."
            )


# -- queues ------------------------------------------------------------


class Work(WorkCommand):
    """Run the queue worker until stopped.

    Consumes the queues in the order they are named, so the first is drained
    before the second is looked at.
    """

    name = "queue:work"
    help = "Run the queue worker until stopped"
    aliases = ["worker"]

    arguments = [
        Option(
            "queue",
            short="q",
            multiple=True,
            help="Queue to consume. Repeatable, highest priority first",
        ),
        Option("concurrency", type=int, default=4, short="c", help="Jobs at once"),
        Option("timeout", type=float, default=60.0, help="Seconds one job may run"),
        Option(
            "max-jobs",
            type=int,
            default=0,
            help="Restart after this many jobs. 0 is unlimited",
        ),
    ]

    async def handle(self) -> None:
        from .commands import run_worker

        queues = self.option("queue") or self.settings.queues

        self.pairs(
            [
                ("queues", ", ".join(queues)),
                ("concurrency", self.option("concurrency")),
                ("broker", self.settings.url or "in-process"),
            ]
        )
        self.warn_if_in_process()
        self.blank()
        self.info("Waiting for jobs. Ctrl-C to stop.")

        await run_worker(
            url=self.settings.url,
            queues=queues,
            concurrency=self.option("concurrency"),
            timeout=self.option("timeout"),
            max_jobs=self.option("max_jobs"),
            prefix=self.settings.prefix,
        )


class QueueList(WorkCommand):
    """Show how much work is waiting on each queue."""

    name = "queue:list"
    help = "Show how much work is waiting on each queue"

    arguments = [
        Option(
            "queue",
            short="q",
            multiple=True,
            help="Queue to inspect. Repeatable. Defaults to the bound set",
        ),
    ]

    async def handle(self) -> None:
        queues = self.option("queue") or self.settings.queues
        connection = self.connection()

        rows = []
        for name in queues:
            try:
                size = await connection.size(name)
            except Exception as error:
                # A broker that is down should name itself, not surface as a
                # traceback from inside the table builder.
                self.fail(f"Could not reach the queue backend: {error}")
            rows.append([name, size])

        self.table(["queue", "waiting"], rows, align=["left", "right"])
        self.blank()
        self.pairs([("broker", self.settings.url or "in-process")])
        self.warn_if_in_process()


class QueueFailed(WorkCommand):
    """List jobs that exhausted their retries."""

    name = "queue:failed"
    help = "List jobs that exhausted their retries"

    arguments = [
        Option("limit", type=int, default=50, short="l", help="Maximum rows"),
        Option("offset", type=int, default=0, help="Rows to skip"),
    ]

    async def handle(self) -> None:
        repository = self.repository()
        jobs = await repository.all(
            limit=self.option("limit"), offset=self.option("offset")
        )

        if not jobs:
            self.muted("No failed jobs recorded.")
            if _resolve(self.settings.failed) is None:
                self.blank()
                self.warn("Failures are only kept in memory.")
                self.muted(
                    "  This process has its own empty record. Bind a durable "
                    "repository with work_commands(failed=...) to see the "
                    "worker's."
                )
            return

        self.table(
            ["id", "job", "queue", "failed at", "error"],
            [
                [
                    getattr(job, "id", ""),
                    getattr(job, "job_class", ""),
                    getattr(job, "queue", ""),
                    getattr(job, "failed_at", ""),
                    str(getattr(job, "exception", ""))[:60],
                ]
                for job in jobs
            ],
        )


class QueueForget(WorkCommand):
    """Drop one failed job from the record."""

    name = "queue:forget"
    help = "Drop one failed job from the record"

    arguments = [Argument("id", help="The failed job's id")]

    async def handle(self) -> None:
        removed = await self.repository().forget(self.argument("id"))
        if not removed:
            self.fail(f"No failed job with id {self.argument('id')!r}.")
        self.success("Forgotten.")


class QueueFlush(WorkCommand):
    """Drop every failed job from the record."""

    name = "queue:flush"
    help = "Drop every failed job from the record"

    arguments = [Flag("force", short="f", help="Skip the confirmation")]

    async def handle(self) -> Optional[int]:
        if not self.flag("force") and not self.confirm(
            "Drop every recorded failure?", default=False
        ):
            self.muted("Nothing done.")
            return 1

        await self.repository().flush()
        self.success("Failed jobs cleared.")
        return None


# -- the scheduler -----------------------------------------------------


class ScheduleRun(WorkCommand):
    """Run scheduled tasks until stopped."""

    name = "schedule:run"
    help = "Run scheduled tasks until stopped"
    aliases = ["scheduler"]

    async def handle(self) -> None:
        from .commands import run_scheduler

        manager = self.manager()
        jobs = manager.list()

        self.pairs([("tasks", len(jobs))])
        for job in jobs:
            self.bullet(f"{job.name} — {self._trigger(job)}")
        self.blank()
        self.info("Running. Ctrl-C to stop.")

        # `manager=`, not the positional `register=`: that one is a callback
        # invoked *with* the manager to attach tasks to. Passing an already
        # populated manager there calls it with an argument it does not take.
        await run_scheduler(manager=manager)

    @staticmethod
    def _trigger(job: Any) -> str:
        """Describe when a job runs.

        Args:
            job: The scheduled job.

        Returns:
            The cron expression, the interval, or the one-shot time. An
            unrecognised trigger falls back to its class name, which still
            tells the reader more than a generic word would.
        """
        trigger = getattr(job, "trigger", None)
        if trigger is None:
            return "—"

        expression = getattr(trigger, "expression", None)
        if expression:
            return str(expression)

        seconds = getattr(trigger, "seconds", None)
        if seconds is not None:
            return f"every {seconds:g}s"

        at = getattr(trigger, "at", None)
        if at is not None:
            return f"once at {at}"

        return type(trigger).__name__


class ScheduleList(WorkCommand):
    """List the registered scheduled tasks."""

    name = "schedule:list"
    help = "List the registered scheduled tasks"

    async def handle(self) -> None:
        manager = self.manager()
        jobs = manager.list()

        if not jobs:
            self.muted("No scheduled tasks registered.")
            return

        self.table(
            ["name", "trigger", "status", "runs", "last run"],
            [
                [
                    getattr(job, "name", getattr(job, "id", "")),
                    ScheduleRun._trigger(job),
                    getattr(getattr(job, "status", ""), "value", ""),
                    getattr(job, "run_count", 0),
                    getattr(job, "last_run_at", "") or "—",
                ]
                for job in jobs
            ],
            align=["left", "left", "left", "right", "left"],
        )


class SchedulePause(WorkCommand):
    """Stop a scheduled task from running."""

    name = "schedule:pause"
    help = "Stop a scheduled task from running"

    arguments = [Argument("id", help="The task's id")]

    async def handle(self) -> None:
        if not self.manager().pause(self.argument("id")):
            self.fail(f"No scheduled task with id {self.argument('id')!r}.")
        self.success("Paused.")


class ScheduleResume(WorkCommand):
    """Let a paused scheduled task run again."""

    name = "schedule:resume"
    help = "Let a paused task run again"

    arguments = [Argument("id", help="The task's id")]

    async def handle(self) -> None:
        if not self.manager().resume(self.argument("id")):
            self.fail(f"No scheduled task with id {self.argument('id')!r}.")
        self.success("Resumed.")


#: Every command this module defines, in the order they are listed.
COMMANDS: List[Type[WorkCommand]] = [
    Work,
    QueueList,
    QueueFailed,
    QueueForget,
    QueueFlush,
    ScheduleRun,
    ScheduleList,
    SchedulePause,
    ScheduleResume,
]


def work_commands(
    *,
    url: Optional[str] = None,
    queues: Optional[List[str]] = None,
    prefix: str = "sillo:queue:",
    scheduler: Source = None,
    failed: Source = None,
    context: Source = None,
    only: Optional[List[str]] = None,
) -> List[Type[Command]]:
    """Return the queue and scheduler commands.

    Args:
        url: Broker URL. A ``redis://`` URL gives a queue shared between
            processes; None keeps it in-process.
        queues: Queues to consume, highest priority first.
        prefix: Key prefix for Redis.
        scheduler: The project's :class:`SchedulerManager`, or a callable
            returning one. Required by the ``schedule:`` commands.
        failed: A failed-job repository, or a callable returning one. Defaults
            to the in-memory one, which is empty in a fresh process.
        context: An async context manager, or a callable returning one, opened
            around every command — a job that touches models needs the database.
        only: Names to include. Omit it for all of them.

    Returns:
        Command classes ready to pass to :meth:`~sillo.console.Console.add_many`.

    Raises:
        ValueError: If *only* names a command this module does not define.
    """
    config = _Config(url, queues, prefix, scheduler, failed, context)
    chosen = COMMANDS

    if only is not None:
        available = {command.name: command for command in COMMANDS}
        unknown = [name for name in only if name not in available]
        if unknown:
            raise ValueError(
                f"work_commands has no {unknown[0]!r}. "
                f"It defines: {', '.join(sorted(available))}"
            )
        chosen = [available[name] for name in only]

    return [
        type(command.__name__, (command,), {"config": config}) for command in chosen
    ]
