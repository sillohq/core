"""Adapters for real HTTP load generators.

The measurement is not done in Python. Timing requests from the same process
that serves them hides everything a deployed application actually pays —
the socket, the event loop under contention, the server's own request parsing —
and it cannot generate concurrency in any realistic way. So the suite drives
established load generators and parses what they report.

Four are supported. ``oha`` and ``bombardier`` emit JSON and are preferred for
that reason: their numbers are read out of a document rather than scraped from
formatted text that changes between releases. ``wrk`` and ``hey`` are parsed
from stdout, which works but is the more fragile path.

Adding a fifth means writing one ``LoadTool`` subclass: a command line and a
parser returning a ``Measurement``.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class Measurement:
    """One tool's report for one run against one URL.

    Latencies are milliseconds and ``requests_per_second`` is the tool's own
    throughput figure rather than anything this suite recomputes — deriving it
    from a duration the tool rounded for display is how benchmarks end up
    disagreeing with themselves.

    Attributes:
        requests_per_second: Throughput over the measured window.
        latency_mean_ms: Mean latency.
        latency_p50_ms: Median latency.
        latency_p95_ms: 95th percentile.
        latency_p99_ms: 99th percentile.
        total_requests: How many requests completed.
        non_2xx: Responses outside 2xx. Anything above zero invalidates the
            row — a server shedding load returns errors quickly and posts a
            flattering throughput.
        raw: The tool's unparsed output, kept so a suspicious number can be
            traced back to what the tool actually said.
    """

    requests_per_second: float
    latency_mean_ms: float
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    total_requests: int
    non_2xx: int
    raw: str = ""


class LoadTool(ABC):
    """A load generator this suite knows how to drive and read."""

    #: Executable name, looked up on PATH.
    binary: str = ""
    #: Shown by ``doctor`` when the tool is missing.
    install_hint: str = ""
    #: Preferred tools are tried first by ``auto`` and emit machine-readable
    #: output rather than text that has to be scraped.
    structured_output: bool = False

    @property
    def name(self) -> str:
        """The tool's identifier on the command line."""
        return self.binary

    def available(self) -> bool:
        """Whether the tool is installed and on PATH."""
        return shutil.which(self.binary) is not None

    def version(self) -> str:
        """Return the tool's reported version, or a short failure note."""
        try:
            result = subprocess.run(
                [self.binary, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError) as error:
            return f"(unreadable: {error})"
        return (result.stdout or result.stderr).strip().splitlines()[0][:60]

    @abstractmethod
    def command(self, url: str, duration: int, connections: int) -> list[str]:
        """Build the argument vector for one run.

        Args:
            url: The full URL to hit.
            duration: Measurement window in seconds.
            connections: Concurrent connections to hold open.

        Returns:
            The command to execute.
        """

    @abstractmethod
    def parse(self, stdout: str) -> Measurement:
        """Turn the tool's output into a ``Measurement``.

        Args:
            stdout: Everything the tool wrote to standard output.

        Returns:
            The parsed measurement.

        Raises:
            ValueError: If the output cannot be understood, which is treated
                as a failed run rather than a zero.
        """

    def run(self, url: str, duration: int, connections: int) -> Measurement:
        """Execute one measurement.

        Args:
            url: The full URL to hit.
            duration: Measurement window in seconds.
            connections: Concurrent connections.

        Returns:
            The parsed measurement.

        Raises:
            RuntimeError: If the tool exits non-zero.
            ValueError: If its output cannot be parsed.
        """
        completed = subprocess.run(
            self.command(url, duration, connections),
            capture_output=True,
            text=True,
            timeout=duration + 120,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"{self.binary} exited {completed.returncode}: "
                f"{(completed.stderr or completed.stdout).strip()[:400]}"
            )
        return self.parse(completed.stdout)


class Oha(LoadTool):
    """`oha <https://github.com/hatoo/oha>`_ — the recommended tool.

    Emits a full JSON document including a percentile map, so nothing has to be
    scraped, and it saturates a local server without needing several of its own
    threads to do it.
    """

    binary = "oha"
    install_hint = "brew install oha  |  cargo install oha"
    structured_output = True

    def command(self, url: str, duration: int, connections: int) -> list[str]:
        """Build the ``oha`` command line."""
        return [
            self.binary,
            "--no-tui",
            "--output-format",
            "json",
            "-z",
            f"{duration}s",
            "-c",
            str(connections),
            url,
        ]

    def parse(self, stdout: str) -> Measurement:
        """Read ``oha``'s JSON report."""
        try:
            report = json.loads(stdout)
        except json.JSONDecodeError as error:
            raise ValueError(f"oha did not emit JSON: {error}") from error

        summary = report.get("summary", {})
        percentiles = report.get("latencyPercentiles", {})

        # `statusCodeDistribution` is the authority when present. Note that
        # oha's `errorDistribution` is deliberately *not* consulted: its
        # commonest entry is "aborted due to deadline", which is the handful of
        # requests still in flight when the window closed. Those are normal and
        # counting them as failures would condemn every run.
        codes = report.get("statusCodeDistribution") or {}
        total = sum(codes.values())
        ok = sum(count for code, count in codes.items() if str(code).startswith("2"))

        if not total:
            # No distribution reported. `summary.total` is the elapsed seconds
            # rather than a request count, so the count has to be derived.
            elapsed = float(summary.get("total", 0.0))
            total = int(round(float(summary.get("requestsPerSec", 0.0)) * elapsed))
            ok = int(round(total * float(summary.get("successRate", 1.0))))

        return Measurement(
            requests_per_second=float(summary.get("requestsPerSec", 0.0)),
            latency_mean_ms=float(summary.get("average", 0.0)) * 1000,
            latency_p50_ms=float(percentiles.get("p50", 0.0)) * 1000,
            latency_p95_ms=float(percentiles.get("p95", 0.0)) * 1000,
            latency_p99_ms=float(percentiles.get("p99", 0.0)) * 1000,
            total_requests=total,
            non_2xx=max(total - ok, 0),
            raw=stdout,
        )


class Bombardier(LoadTool):
    """`bombardier <https://github.com/codesenberg/bombardier>`_.

    The other structured-output option. Reports latency in microseconds, which
    is why everything is divided by a thousand on the way out.
    """

    binary = "bombardier"
    install_hint = (
        "brew install bombardier  |  "
        "go install github.com/codesenberg/bombardier@latest"
    )
    structured_output = True

    def command(self, url: str, duration: int, connections: int) -> list[str]:
        """Build the ``bombardier`` command line."""
        return [
            self.binary,
            "-c",
            str(connections),
            "-d",
            f"{duration}s",
            "-l",
            "--print",
            "result",
            "-o",
            "json",
            url,
        ]

    def parse(self, stdout: str) -> Measurement:
        """Read ``bombardier``'s JSON report."""
        try:
            report = json.loads(stdout)
        except json.JSONDecodeError as error:
            raise ValueError(f"bombardier did not emit JSON: {error}") from error

        result = report.get("result", {})
        rps = result.get("rps", {})
        latency = result.get("latency", {})
        percentiles = latency.get("percentiles", {})
        codes = {
            key: value
            for key, value in result.items()
            if key.startswith("req") and key[3:].isdigit()
        }
        ok = int(result.get("req2xx", 0))
        total = int(sum(codes.values())) or ok

        return Measurement(
            requests_per_second=float(rps.get("mean", 0.0)),
            latency_mean_ms=float(latency.get("mean", 0.0)) / 1000,
            latency_p50_ms=float(percentiles.get("50", 0.0)) / 1000,
            latency_p95_ms=float(percentiles.get("95", 0.0)) / 1000,
            latency_p99_ms=float(percentiles.get("99", 0.0)) / 1000,
            total_requests=total,
            non_2xx=max(total - ok, 0),
            raw=stdout,
        )


class Wrk(LoadTool):
    """`wrk <https://github.com/wg/wrk>`_, parsed from its text report.

    Widely installed, which is the reason it is here. It prints no percentile
    beyond p99 without a Lua script, so p95 is reported as p99's value would
    mislead — it is left at zero and the exporters render it blank.
    """

    binary = "wrk"
    install_hint = "brew install wrk"

    _LATENCY = re.compile(r"^\s+Latency\s+([\d.]+)(\w+)", re.MULTILINE)
    _P99 = re.compile(r"^\s+99%\s+([\d.]+)(\w+)", re.MULTILINE)
    _P50 = re.compile(r"^\s+50%\s+([\d.]+)(\w+)", re.MULTILINE)
    _REQUESTS = re.compile(r"([\d]+) requests in")
    _RPS = re.compile(r"Requests/sec:\s+([\d.]+)")
    _NON_2XX = re.compile(r"Non-2xx or 3xx responses:\s+(\d+)")

    @staticmethod
    def _ms(value: str, unit: str) -> float:
        """Convert a wrk duration to milliseconds.

        Args:
            value: The numeric part.
            unit: wrk's unit suffix (``us``, ``ms``, ``s`` or ``m``).

        Returns:
            The duration in milliseconds.
        """
        scale = {"us": 0.001, "ms": 1.0, "s": 1000.0, "m": 60000.0}
        return float(value) * scale.get(unit, 1.0)

    def command(self, url: str, duration: int, connections: int) -> list[str]:
        """Build the ``wrk`` command line."""
        threads = min(connections, 8)
        return [
            self.binary,
            "--latency",
            "-t",
            str(threads),
            "-c",
            str(connections),
            "-d",
            f"{duration}s",
            url,
        ]

    def parse(self, stdout: str) -> Measurement:
        """Scrape ``wrk``'s text report."""
        rps = self._RPS.search(stdout)
        if not rps:
            raise ValueError(f"could not find Requests/sec in wrk output:\n{stdout[:400]}")

        mean = self._LATENCY.search(stdout)
        p50 = self._P50.search(stdout)
        p99 = self._P99.search(stdout)
        total = self._REQUESTS.search(stdout)
        non_2xx = self._NON_2XX.search(stdout)

        return Measurement(
            requests_per_second=float(rps.group(1)),
            latency_mean_ms=self._ms(*mean.groups()) if mean else 0.0,
            latency_p50_ms=self._ms(*p50.groups()) if p50 else 0.0,
            # wrk reports no p95 without a Lua script. Left at zero rather than
            # filled with a neighbouring percentile.
            latency_p95_ms=0.0,
            latency_p99_ms=self._ms(*p99.groups()) if p99 else 0.0,
            total_requests=int(total.group(1)) if total else 0,
            non_2xx=int(non_2xx.group(1)) if non_2xx else 0,
            raw=stdout,
        )


class Hey(LoadTool):
    """`hey <https://github.com/rakyll/hey>`_, parsed from its text report."""

    binary = "hey"
    install_hint = "brew install hey  |  go install github.com/rakyll/hey@latest"

    _RPS = re.compile(r"Requests/sec:\s+([\d.]+)")
    _AVERAGE = re.compile(r"Average:\s+([\d.]+) secs")
    _TOTAL = re.compile(r"Total:\s+([\d.]+) secs")
    _PERCENTILE = re.compile(r"^\s+(\d+)% in ([\d.]+) secs", re.MULTILINE)
    _STATUS = re.compile(r"^\s+\[(\d+)\]\s+(\d+) responses", re.MULTILINE)

    def command(self, url: str, duration: int, connections: int) -> list[str]:
        """Build the ``hey`` command line."""
        return [
            self.binary,
            "-z",
            f"{duration}s",
            "-c",
            str(connections),
            "-disable-keepalive=false",
            url,
        ]

    def parse(self, stdout: str) -> Measurement:
        """Scrape ``hey``'s text report."""
        rps = self._RPS.search(stdout)
        if not rps:
            raise ValueError(f"could not find Requests/sec in hey output:\n{stdout[:400]}")

        percentiles = {int(p): float(v) * 1000 for p, v in self._PERCENTILE.findall(stdout)}
        statuses = {int(code): int(count) for code, count in self._STATUS.findall(stdout)}
        ok = sum(count for code, count in statuses.items() if 200 <= code < 300)
        total = sum(statuses.values())
        average = self._AVERAGE.search(stdout)

        return Measurement(
            requests_per_second=float(rps.group(1)),
            latency_mean_ms=float(average.group(1)) * 1000 if average else 0.0,
            latency_p50_ms=percentiles.get(50, 0.0),
            latency_p95_ms=percentiles.get(95, 0.0),
            latency_p99_ms=percentiles.get(99, 0.0),
            total_requests=total,
            non_2xx=max(total - ok, 0),
            raw=stdout,
        )


#: Registration order is also ``auto``'s preference order.
TOOLS: tuple[LoadTool, ...] = (Oha(), Bombardier(), Wrk(), Hey())
TOOLS_BY_NAME: dict[str, LoadTool] = {tool.name: tool for tool in TOOLS}


def resolve(name: str) -> LoadTool:
    """Pick the load generator to use.

    Args:
        name: A tool name, or ``"auto"`` to take the first installed one in
            preference order.

    Returns:
        An installed, ready-to-run tool.

    Raises:
        ValueError: If the named tool is unknown.
        RuntimeError: If the named tool is not installed, or if ``auto`` finds
            none at all. Both messages carry the install command, because the
            only useful thing to say at that point is how to fix it.
    """
    if name == "auto":
        for tool in TOOLS:
            if tool.available():
                return tool
        hints = "\n".join(f"  {t.name:12} {t.install_hint}" for t in TOOLS)
        raise RuntimeError(
            "no load generator found on PATH. Install one of:\n" + hints
        )

    tool = TOOLS_BY_NAME.get(name)
    if tool is None:
        raise ValueError(
            f"unknown tool '{name}'. available: {', '.join(TOOLS_BY_NAME)}, auto"
        )
    if not tool.available():
        raise RuntimeError(f"{name} is not installed. {tool.install_hint}")
    return tool
