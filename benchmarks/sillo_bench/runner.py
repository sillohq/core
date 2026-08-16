"""Orchestration: start a server, prove it correct, measure it, stop it.

The order matters and is the part most home-grown benchmarks get wrong.

Each framework gets its own uvicorn process on its own port, started fresh and
stopped before the next one begins, so nothing is competing for the event loop
or holding warm caches from another framework's run. Within a process, every
scenario is *verified* before it is measured: the response must have the
expected status and contain the expected content. A framework that 404s or 500s
answers extremely quickly, and without that check it would top the table.

Then each scenario runs an unmeasured warmup followed by N measured rounds, and
the reported figure is the **median** round. Medians rather than means because
a single scheduler hiccup or a background process waking up skews a mean and
cannot be distinguished from a real result afterwards.
"""

from __future__ import annotations

import os
import socket
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from sillo_bench.loadtools import LoadTool, Measurement
from sillo_bench.scenarios import Scenario

#: Each framework's ASGI application, as uvicorn import strings.
#:
#: Ordered roughly by what they are: the two being compared head to head, then
#: the ASGI toolkit FastAPI is built on, then the two batteries-included
#: incumbents. Report column order follows this.
FRAMEWORKS: dict[str, str] = {
    "sillo": "sillo_bench.apps.sillo_app:app",
    "fastapi": "sillo_bench.apps.fastapi_app:app",
    "litestar": "sillo_bench.apps.litestar_app:app",
    "starlette": "sillo_bench.apps.starlette_app:app",
    "django": "sillo_bench.apps.django_app:app",
    "flask": "sillo_bench.apps.flask_app:app",
}

#: Distribution name for each framework, for version reporting. Read from
#: installed metadata rather than a ``__version__`` attribute, because not
#: every framework exposes one and Litestar's is a structured object rather
#: than a string.
DISTRIBUTIONS: dict[str, str] = {
    "sillo": "sillo-framework",
    "fastapi": "fastapi",
    "litestar": "litestar",
    "starlette": "starlette",
    "django": "django",
    "flask": "flask",
}


@dataclass
class Result:
    """One framework's measured result for one scenario.

    Attributes:
        framework: Which framework produced it.
        scenario: Which scenario was run.
        rounds: Every measured round, in order.
        error: Why this cell is empty, when it is. A result carries either
            rounds or an error, never both.
    """

    framework: str
    scenario: str
    rounds: list[Measurement] = field(default_factory=list)
    error: str = ""

    @property
    def ok(self) -> bool:
        """Whether this result has usable numbers."""
        return not self.error and bool(self.rounds)

    def _median_of(self, attribute: str) -> float:
        """Return the median across rounds of one measurement attribute."""
        if not self.rounds:
            return 0.0
        return statistics.median(getattr(round_, attribute) for round_ in self.rounds)

    @property
    def rps(self) -> float:
        """Median throughput across rounds."""
        return self._median_of("requests_per_second")

    @property
    def p50(self) -> float:
        """Median p50 latency across rounds."""
        return self._median_of("latency_p50_ms")

    @property
    def p95(self) -> float:
        """Median p95 latency across rounds."""
        return self._median_of("latency_p95_ms")

    @property
    def p99(self) -> float:
        """Median p99 latency across rounds."""
        return self._median_of("latency_p99_ms")

    @property
    def mean_latency(self) -> float:
        """Median mean-latency across rounds."""
        return self._median_of("latency_mean_ms")

    @property
    def total_requests(self) -> int:
        """Total requests completed across every round."""
        return sum(r.total_requests for r in self.rounds)

    @property
    def non_2xx(self) -> int:
        """Non-2xx responses across every round."""
        return sum(r.non_2xx for r in self.rounds)

    @property
    def spread(self) -> float:
        """Relative spread between the fastest and slowest round, as a fraction.

        A high value means the rounds disagreed and the median is not standing
        for much. The reporters flag anything above 10%, which usually means
        something else was running on the machine.
        """
        if len(self.rounds) < 2:
            return 0.0
        values = [r.requests_per_second for r in self.rounds]
        low, high = min(values), max(values)
        return (high - low) / high if high else 0.0


def free_port() -> int:
    """Return a port number nothing is currently listening on.

    Bound and released rather than picked at random, so two runs on the same
    machine cannot collide.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class Server:
    """A uvicorn process serving one framework, as a context manager.

    Every framework is served by the same uvicorn, with the same flags and the
    same worker count, so the server is a constant and what differs between
    rows is the application.
    """

    def __init__(
        self,
        framework: str,
        port: int,
        workers: int = 1,
        log: Path | None = None,
    ) -> None:
        """Prepare a server for one framework.

        Args:
            framework: Key into ``FRAMEWORKS``.
            port: Port to bind on localhost.
            workers: uvicorn worker processes. One by default: the suite
                measures framework overhead, and multiple workers mostly
                measure how many cores the machine has.
            log: Where to write the server's own output. Kept, because a
                framework that fails to boot explains itself there.
        """
        self.framework = framework
        self.port = port
        self.workers = workers
        self.log = log
        self.process: subprocess.Popen | None = None

    @property
    def base_url(self) -> str:
        """The server's root URL."""
        return f"http://127.0.0.1:{self.port}"

    def __enter__(self) -> Server:
        """Start uvicorn and wait for it to answer.

        Returns:
            This server, once it is serving.

        Raises:
            RuntimeError: If the process dies or never becomes reachable. The
                server log is quoted into the message, since that is where the
                actual cause is.
        """
        command = [
            sys.executable,
            "-m",
            "uvicorn",
            FRAMEWORKS[self.framework],
            "--host",
            "127.0.0.1",
            "--port",
            str(self.port),
            "--workers",
            str(self.workers),
            # Access logging writes a line per request. Left on, it would
            # measure the logger.
            "--no-access-log",
            "--log-level",
            "warning",
        ]
        handle = open(self.log, "w") if self.log else subprocess.DEVNULL

        environment = dict(os.environ)
        # The apps import `sillo_bench`, which lives one directory up.
        package_root = str(Path(__file__).resolve().parent.parent)
        existing = environment.get("PYTHONPATH", "")
        environment["PYTHONPATH"] = (
            f"{package_root}{os.pathsep}{existing}" if existing else package_root
        )

        self.process = subprocess.Popen(
            command,
            stdout=handle,
            stderr=subprocess.STDOUT,
            env=environment,
        )
        self._await_ready()
        return self

    def _await_ready(self, timeout: float = 45.0) -> None:
        """Poll until the server answers, or give up.

        Args:
            timeout: How long to wait before declaring failure.

        Raises:
            RuntimeError: If the process exits or the deadline passes.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.process and self.process.poll() is not None:
                raise RuntimeError(
                    f"{self.framework} server exited with code "
                    f"{self.process.returncode} before serving.{self._log_tail()}"
                )
            try:
                # Any answer proves the socket is up and the app is mounted;
                # a 404 here is as good a proof as a 200.
                urllib.request.urlopen(f"{self.base_url}/plaintext", timeout=1)
                return
            except urllib.error.HTTPError:
                return
            except (urllib.error.URLError, OSError, TimeoutError):
                time.sleep(0.1)

        raise RuntimeError(
            f"{self.framework} server did not answer within {timeout:.0f}s."
            f"{self._log_tail()}"
        )

    def _log_tail(self) -> str:
        """Return the last few lines of the server log, for error messages."""
        if not self.log or not self.log.exists():
            return ""
        tail = self.log.read_text(errors="replace").strip().splitlines()[-15:]
        return "\n  " + "\n  ".join(tail) if tail else ""

    def __exit__(self, *exc_info: object) -> None:
        """Stop the server, escalating to a kill if it will not go."""
        if self.process is None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=10)


def verify(base_url: str, scenario: Scenario) -> None:
    """Prove a scenario is correctly implemented before it is measured.

    Without this, a framework whose route is missing returns a fast 404 and
    posts the best number in the table.

    Args:
        base_url: The server root.
        scenario: The scenario to check.

    Raises:
        RuntimeError: If the response has the wrong status or is missing the
            expected content.
    """
    url = f"{base_url}{scenario.path}"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            status = response.status
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as error:
        status = error.code
        body = error.read().decode("utf-8", errors="replace")

    if status != scenario.expect_status:
        raise RuntimeError(
            f"{scenario.path} returned {status}, expected {scenario.expect_status}. "
            f"body: {body[:200]}"
        )
    if scenario.expect_contains and scenario.expect_contains not in body:
        raise RuntimeError(
            f"{scenario.path} did not contain {scenario.expect_contains!r}. "
            f"body: {body[:200]}"
        )


@dataclass
class RunConfig:
    """Everything that controls one invocation of the suite.

    Attributes:
        duration: Seconds per measured round.
        connections: Concurrent connections held open by the load generator.
        rounds: Measured rounds per scenario. The median is reported, so an
            odd number above one is the useful setting.
        warmup: Seconds of unmeasured load before the rounds, to get the
            interpreter's caches and the JIT-less import paths settled.
        workers: uvicorn worker processes per framework.
        settle: Seconds of quiet between rounds, so one round's queued work
            does not land inside the next one's window.
    """

    duration: int = 10
    connections: int = 64
    rounds: int = 3
    warmup: int = 3
    workers: int = 1
    settle: float = 1.0


def run_framework(
    framework: str,
    scenarios: list[Scenario],
    tool: LoadTool,
    config: RunConfig,
    log_dir: Path | None = None,
    on_event=None,
) -> list[Result]:
    """Measure one framework across every scenario.

    Args:
        framework: Key into ``FRAMEWORKS``.
        scenarios: Scenarios to run, in report order.
        tool: The load generator to drive.
        config: Run parameters.
        log_dir: Where to write the server log, if anywhere.
        on_event: Optional progress callback taking ``(event, detail)``.

    Returns:
        One ``Result`` per scenario. A scenario that could not be measured
        comes back carrying an error rather than being dropped, so the report
        shows what failed instead of quietly narrowing.
    """
    def emit(event: str, detail: str = "") -> None:
        if on_event:
            on_event(event, detail)

    results: list[Result] = []
    port = free_port()
    log = (log_dir / f"{framework}.log") if log_dir else None

    try:
        with Server(framework, port, config.workers, log) as server:
            emit("server-up", f"{framework} on {server.base_url}")

            for scenario in scenarios:
                result = Result(framework=framework, scenario=scenario.name)
                url = f"{server.base_url}{scenario.path}"

                try:
                    verify(server.base_url, scenario)
                except RuntimeError as error:
                    result.error = str(error)
                    results.append(result)
                    emit("scenario-failed", f"{framework}/{scenario.name}: {error}")
                    continue

                if config.warmup:
                    emit("warmup", f"{framework}/{scenario.name}")
                    try:
                        tool.run(url, config.warmup, config.connections)
                    except (RuntimeError, ValueError):
                        # A warmup that fails is not itself a result; the
                        # measured rounds below will report the real problem.
                        pass

                for index in range(config.rounds):
                    emit("round", f"{framework}/{scenario.name} {index + 1}/{config.rounds}")
                    try:
                        result.rounds.append(
                            tool.run(url, config.duration, config.connections)
                        )
                    except (RuntimeError, ValueError) as error:
                        result.error = str(error)
                        break
                    if index + 1 < config.rounds:
                        time.sleep(config.settle)

                if result.ok and result.non_2xx:
                    result.error = (
                        f"{result.non_2xx} non-2xx responses under load; "
                        "the server was shedding requests"
                    )

                results.append(result)
                emit("scenario-done", f"{framework}/{scenario.name}")

    except (RuntimeError, KeyError) as error:
        # The server never came up. Every scenario is reported as failed for
        # the same reason rather than the run aborting.
        return [
            Result(framework=framework, scenario=s.name, error=str(error))
            for s in scenarios
        ]

    return results
