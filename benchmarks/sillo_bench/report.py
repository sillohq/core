"""Turning results into a table, a file, or both.

Four formats, each for a different reader. The terminal table is for whoever is
sitting there. CSV is for a spreadsheet or pandas. JSON keeps the individual
rounds and the raw tool output, so a disputed number can be traced. Markdown is
what gets pasted into a README or an issue.

All four render the same numbers from the same results, and all four carry the
environment block. A benchmark table published without the machine it ran on is
not a result, it is a claim.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from sillo_bench.environment import Environment
from sillo_bench.runner import Result
from sillo_bench.scenarios import Scenario

#: Column order for CSV. Fixed, so appended runs stay concatenable.
CSV_COLUMNS = [
    "scenario",
    "framework",
    "requests_per_second",
    "latency_mean_ms",
    "latency_p50_ms",
    "latency_p95_ms",
    "latency_p99_ms",
    "rounds",
    "total_requests",
    "non_2xx",
    "round_spread_pct",
    "error",
]


def _rows(results: list[Result]) -> list[dict]:
    """Flatten results into one dictionary per scenario/framework cell."""
    rows = []
    for result in results:
        rows.append(
            {
                "scenario": result.scenario,
                "framework": result.framework,
                "requests_per_second": round(result.rps, 1) if result.ok else "",
                "latency_mean_ms": round(result.mean_latency, 3) if result.ok else "",
                "latency_p50_ms": round(result.p50, 3) if result.ok else "",
                "latency_p95_ms": round(result.p95, 3) if result.ok else "",
                "latency_p99_ms": round(result.p99, 3) if result.ok else "",
                "rounds": len(result.rounds),
                "total_requests": result.total_requests if result.ok else "",
                "non_2xx": result.non_2xx if result.ok else "",
                "round_spread_pct": round(result.spread * 100, 1) if result.ok else "",
                "error": result.error,
            }
        )
    return rows


def write_csv(results: list[Result], path: Path) -> Path:
    """Write results as CSV.

    Args:
        results: Every measured cell.
        path: Destination file. Parent directories are created.

    Returns:
        The path written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(_rows(results))
    return path


def write_environment_csv(environment: Environment, path: Path) -> Path:
    """Write the environment as its own two-column CSV.

    Kept separate from the results file so the results stay a clean rectangle
    that loads into a dataframe without a header block to skip.

    Args:
        environment: The captured snapshot.
        path: Destination file.

    Returns:
        The path written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    data = environment.as_dict()
    packages = data.pop("packages", {})
    notes = data.pop("notes", [])

    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["key", "value"])
        for key, value in data.items():
            writer.writerow([key, value])
        for name, version in packages.items():
            writer.writerow([f"package.{name}", version])
        for index, note in enumerate(notes):
            writer.writerow([f"note.{index}", note])
    return path


def write_json(results: list[Result], environment: Environment, path: Path) -> Path:
    """Write the full record, including every round and the raw tool output.

    This is the archival format. The terminal table and the CSV both collapse
    rounds to a median; this keeps what was collapsed, so a number that looks
    wrong later can be checked rather than re-argued.

    Args:
        results: Every measured cell.
        environment: The captured snapshot.
        path: Destination file.

    Returns:
        The path written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "environment": environment.as_dict(),
        "results": [
            {
                "framework": result.framework,
                "scenario": result.scenario,
                "error": result.error,
                "median": {
                    "requests_per_second": result.rps,
                    "latency_mean_ms": result.mean_latency,
                    "latency_p50_ms": result.p50,
                    "latency_p95_ms": result.p95,
                    "latency_p99_ms": result.p99,
                }
                if result.ok
                else None,
                "rounds": [asdict(round_) for round_ in result.rounds],
            }
            for result in results
        ],
    }
    path.write_text(json.dumps(document, indent=2))
    return path


def _grouped(results: list[Result]) -> dict[str, dict[str, Result]]:
    """Index results by scenario then framework."""
    grouped: dict[str, dict[str, Result]] = {}
    for result in results:
        grouped.setdefault(result.scenario, {})[result.framework] = result
    return grouped


def render_table(
    results: list[Result],
    frameworks: list[str],
    scenarios: list[Scenario],
    environment: Environment,
) -> str:
    """Render the terminal report.

    Throughput is shown with a relative multiplier against the fastest
    framework in each row, because the absolute figure is machine-specific and
    the ratio is the part that carries between machines.

    Args:
        results: Every measured cell.
        frameworks: Column order.
        scenarios: Row order.
        environment: Printed above the table.

    Returns:
        The rendered report.
    """
    grouped = _grouped(results)
    lines: list[str] = ["", environment.describe(), ""]

    name_width = max([len(s.name) for s in scenarios] + [8]) + 2
    cell_width = 22

    header = "scenario".ljust(name_width) + "".join(
        f.ljust(cell_width) for f in frameworks
    )
    lines.append(header)
    lines.append("-" * len(header))

    for scenario in scenarios:
        row = grouped.get(scenario.name, {})
        best = max(
            (r.rps for r in row.values() if r.ok),
            default=0.0,
        )

        cells = []
        for framework in frameworks:
            result = row.get(framework)
            if result is None:
                cells.append("-".ljust(cell_width))
            elif not result.ok:
                cells.append("failed".ljust(cell_width))
            else:
                ratio = f" ({result.rps / best:.2f}x)" if best else ""
                cells.append(f"{result.rps:>10,.0f} rps{ratio}".ljust(cell_width))

        lines.append(scenario.name.ljust(name_width) + "".join(cells))

        latency_cells = []
        for framework in frameworks:
            result = row.get(framework)
            if result is None or not result.ok:
                latency_cells.append("".ljust(cell_width))
            else:
                latency_cells.append(
                    f"  p50 {result.p50:.2f}ms".ljust(cell_width)
                )
        lines.append(" " * name_width + "".join(latency_cells))

    lines.append("")
    lines.append("throughput is the median of the measured rounds; higher is better.")
    lines.append("the multiplier compares each framework to the fastest in that row.")

    noisy = [r for r in results if r.ok and r.spread > 0.10]
    if noisy:
        lines.append("")
        lines.append("rounds disagreed by more than 10% here, so treat these as soft:")
        for result in noisy:
            lines.append(
                f"  {result.framework}/{result.scenario}: "
                f"{result.spread * 100:.0f}% spread across {len(result.rounds)} rounds"
            )

    failures = [r for r in results if r.error]
    if failures:
        lines.append("")
        lines.append("failed:")
        for result in failures:
            lines.append(f"  {result.framework}/{result.scenario}: {result.error}")

    return "\n".join(lines)


def write_markdown(
    results: list[Result],
    frameworks: list[str],
    scenarios: list[Scenario],
    environment: Environment,
    path: Path,
) -> Path:
    """Write a Markdown report suitable for a README or an issue.

    Args:
        results: Every measured cell.
        frameworks: Column order.
        scenarios: Row order.
        environment: Rendered as a detail block beneath the table.
        path: Destination file.

    Returns:
        The path written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    grouped = _grouped(results)

    lines = [
        "# Sillo benchmark results",
        "",
        f"Generated {environment.captured_at} with `{environment.load_tool}`.",
        "",
        "Throughput, requests per second. Higher is better. Each figure is the",
        "median of the measured rounds.",
        "",
        "| scenario | " + " | ".join(frameworks) + " |",
        "| --- | " + " | ".join("---:" for _ in frameworks) + " |",
    ]

    for scenario in scenarios:
        row = grouped.get(scenario.name, {})
        cells = []
        for framework in frameworks:
            result = row.get(framework)
            if result is None:
                cells.append("–")
            elif not result.ok:
                cells.append("failed")
            else:
                cells.append(f"{result.rps:,.0f}")
        lines.append(f"| `{scenario.name}` | " + " | ".join(cells) + " |")

    lines += ["", "p99 latency, milliseconds. Lower is better.", ""]
    lines.append("| scenario | " + " | ".join(frameworks) + " |")
    lines.append("| --- | " + " | ".join("---:" for _ in frameworks) + " |")
    for scenario in scenarios:
        row = grouped.get(scenario.name, {})
        cells = []
        for framework in frameworks:
            result = row.get(framework)
            cells.append(f"{result.p99:.2f}" if result and result.ok else "–")
        lines.append(f"| `{scenario.name}` | " + " | ".join(cells) + " |")

    lines += ["", "## What each scenario measures", ""]
    for scenario in scenarios:
        lines.append(f"- **`{scenario.name}`** — {scenario.summary}")

    lines += ["", "## Environment", "", "```"]
    lines.append(environment.describe())
    lines += ["```", ""]

    failures = [r for r in results if r.error]
    if failures:
        lines += ["## Failures", ""]
        for result in failures:
            lines.append(f"- `{result.framework}/{result.scenario}` — {result.error}")
        lines.append("")

    path.write_text("\n".join(lines))
    return path
