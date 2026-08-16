"""Command line for the benchmark suite.

Four commands. ``doctor`` reports what is installed and is the right first
thing to run. ``list`` shows what can be measured. ``serve`` runs one
framework's application so it can be poked at by hand. ``run`` does the work.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from sillo_bench import loadtools, report
from sillo_bench import scenarios as scenario_registry
from sillo_bench.environment import Environment
from sillo_bench.runner import FRAMEWORKS, RunConfig, Server, free_port, run_framework

DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "results"


def _framework_importable(name: str) -> tuple[bool, str]:
    """Check whether a framework can be imported in a fresh interpreter.

    Run out-of-process because importing Django configures global state, and
    ``doctor`` should not leave the checking process in a different condition
    than it found it.

    Args:
        name: The framework key.

    Returns:
        ``(importable, detail)`` where detail is the version or the error.
    """
    module = {"sillo": "sillo", "fastapi": "fastapi", "django": "django"}[name]
    probe = (
        f"import {module}; "
        f"print(getattr({module}, '__version__', 'unknown'))"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        return False, (result.stderr.strip().splitlines() or ["import failed"])[-1]
    return True, result.stdout.strip()


def cmd_doctor(args: argparse.Namespace) -> int:
    """Report what is installed, and what is missing.

    Returns:
        ``0`` if the suite can run, ``1`` otherwise.
    """
    print("\nframeworks")
    installed_frameworks = []
    for name in FRAMEWORKS:
        ok, detail = _framework_importable(name)
        mark = "ok  " if ok else "MISSING"
        print(f"  {mark} {name:10} {detail}")
        if ok:
            installed_frameworks.append(name)

    print("\nload generators")
    installed_tools = []
    for tool in loadtools.TOOLS:
        if tool.available():
            structured = "" if tool.structured_output else "   (text output, parsed)"
            print(f"  ok   {tool.name:12} {tool.version()}{structured}")
            installed_tools.append(tool.name)
        else:
            print(f"  --   {tool.name:12} {tool.install_hint}")

    print("\nserver")
    server_ok, server_detail = True, ""
    try:
        import uvicorn

        server_detail = uvicorn.__version__
    except ImportError as error:
        server_ok, server_detail = False, str(error)
    print(f"  {'ok  ' if server_ok else 'MISSING'} uvicorn      {server_detail}")

    problems = []
    if not installed_tools:
        problems.append("no load generator installed — see the hints above")
    if len(installed_frameworks) < 2:
        problems.append("fewer than two frameworks installed; nothing to compare")
    if not server_ok:
        problems.append("uvicorn is required to serve the applications")

    print()
    if problems:
        for problem in problems:
            print(f"  problem: {problem}")
        print("\n  fix with: uv pip install -e '.[all]'   (from benchmarks/)")
        return 1

    print("  ready. run:  python -m sillo_bench run")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """Print the scenarios and frameworks available.

    Returns:
        Always ``0``.
    """
    print("\nscenarios")
    for scenario in scenario_registry.SCENARIOS:
        print(f"  {scenario.name:14} {scenario.path}")
        print(f"  {'':14} {scenario.summary}")

    print("\nframeworks")
    for name, target in FRAMEWORKS.items():
        print(f"  {name:14} {target}")

    print("\nload generators (preference order)")
    for tool in loadtools.TOOLS:
        state = "installed" if tool.available() else "not installed"
        print(f"  {tool.name:14} {state}")
    print()
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    """Serve one framework until interrupted, for manual inspection.

    Returns:
        ``0`` on a clean exit, ``1`` if the server would not start.
    """
    port = args.port or free_port()
    print(f"serving {args.framework} on http://127.0.0.1:{port}")
    print("routes:")
    for scenario in scenario_registry.SCENARIOS:
        print(f"  http://127.0.0.1:{port}{scenario.path}")
    print("\nctrl-c to stop\n")

    try:
        with Server(args.framework, port, workers=args.workers) as server:
            assert server.process is not None
            server.process.wait()
    except KeyboardInterrupt:
        return 0
    except RuntimeError as error:
        print(f"\nerror: {error}", file=sys.stderr)
        return 1
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """Run the benchmark matrix and export the results.

    Returns:
        ``0`` if every requested cell was measured, ``1`` if any failed.
    """
    try:
        selected_scenarios = scenario_registry.resolve(args.scenarios)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    frameworks = [f.strip() for f in args.frameworks.split(",") if f.strip()]
    unknown = [f for f in frameworks if f not in FRAMEWORKS]
    if unknown:
        print(
            f"error: unknown framework(s): {', '.join(unknown)}. "
            f"available: {', '.join(FRAMEWORKS)}",
            file=sys.stderr,
        )
        return 1

    try:
        tool = loadtools.resolve(args.tool)
    except (ValueError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    config = RunConfig(
        duration=args.duration,
        connections=args.connections,
        rounds=args.rounds,
        warmup=args.warmup,
        workers=args.workers,
        settle=args.settle,
    )

    environment = Environment.capture(load_tool=f"{tool.name} {tool.version()}")
    if args.note:
        environment.notes.extend(args.note)

    output = Path(args.out).expanduser().resolve()
    log_dir = output / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    estimate = (
        len(frameworks)
        * len(selected_scenarios)
        * (config.warmup + config.rounds * (config.duration + config.settle))
    )
    print(
        f"\n{len(frameworks)} frameworks x {len(selected_scenarios)} scenarios "
        f"x {config.rounds} rounds of {config.duration}s "
        f"at {config.connections} connections"
    )
    print(f"driver: {tool.name}   estimated: ~{estimate / 60:.0f} min\n")

    def on_event(event: str, detail: str) -> None:
        if event in {"round", "warmup", "server-up"} and not args.quiet:
            print(f"  {event:16} {detail}", flush=True)
        elif event == "scenario-failed":
            print(f"  FAILED           {detail}", file=sys.stderr, flush=True)

    results = []
    for framework in frameworks:
        results.extend(
            run_framework(
                framework,
                selected_scenarios,
                tool,
                config,
                log_dir=log_dir,
                on_event=on_event,
            )
        )

    print(report.render_table(results, frameworks, selected_scenarios, environment))

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    formats = {f.strip() for f in args.export.split(",") if f.strip()}
    written = []

    if "csv" in formats:
        written.append(report.write_csv(results, output / f"results-{stamp}.csv"))
        written.append(
            report.write_environment_csv(environment, output / f"environment-{stamp}.csv")
        )
    if "json" in formats:
        written.append(
            report.write_json(results, environment, output / f"results-{stamp}.json")
        )
    if "md" in formats:
        written.append(
            report.write_markdown(
                results,
                frameworks,
                selected_scenarios,
                environment,
                output / f"results-{stamp}.md",
            )
        )

    if written:
        print("\nwrote:")
        for path in written:
            print(f"  {path}")

    failed = [r for r in results if r.error]
    return 1 if failed else 0


def build_parser() -> argparse.ArgumentParser:
    """Assemble the argument parser.

    Returns:
        The configured parser.
    """
    parser = argparse.ArgumentParser(
        prog="python -m sillo_bench",
        description="The official Sillo benchmark: Sillo, FastAPI and Django "
        "under a real HTTP load generator.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  python -m sillo_bench doctor\n"
            "  python -m sillo_bench run\n"
            "  python -m sillo_bench run --frameworks sillo,fastapi --scenarios json,rows\n"
            "  python -m sillo_bench run --duration 30 --rounds 5 --connections 128\n"
            "  python -m sillo_bench run --export csv,json,md --out ./results\n"
            "  python -m sillo_bench serve sillo\n"
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="check the suite can run here")
    doctor.set_defaults(func=cmd_doctor)

    listing = subparsers.add_parser("list", help="show scenarios and frameworks")
    listing.set_defaults(func=cmd_list)

    serve = subparsers.add_parser("serve", help="serve one framework for inspection")
    serve.add_argument("framework", choices=sorted(FRAMEWORKS))
    serve.add_argument("--port", type=int, default=0, help="default: a free port")
    serve.add_argument("--workers", type=int, default=1)
    serve.set_defaults(func=cmd_serve)

    run = subparsers.add_parser("run", help="run the benchmark and export results")
    run.add_argument(
        "--frameworks",
        default=",".join(FRAMEWORKS),
        help="comma-separated (default: all)",
    )
    run.add_argument(
        "--scenarios",
        default="",
        help="comma-separated (default: all). see `list`",
    )
    run.add_argument(
        "--tool",
        default="auto",
        help="oha, bombardier, wrk, hey, or auto (default: auto)",
    )
    run.add_argument("--duration", type=int, default=10, help="seconds per round")
    run.add_argument("--connections", type=int, default=64, help="concurrent connections")
    run.add_argument(
        "--rounds",
        type=int,
        default=3,
        help="measured rounds per scenario; the median is reported (default: 3)",
    )
    run.add_argument(
        "--warmup", type=int, default=3, help="unmeasured warmup seconds (default: 3)"
    )
    run.add_argument("--workers", type=int, default=1, help="uvicorn workers per server")
    run.add_argument(
        "--settle", type=float, default=1.0, help="quiet seconds between rounds"
    )
    run.add_argument(
        "--export",
        default="csv,json,md",
        help="comma-separated: csv, json, md (default: all three)",
    )
    run.add_argument("--out", default=str(DEFAULT_OUTPUT), help="output directory")
    run.add_argument(
        "--note",
        action="append",
        default=[],
        help="a caveat to record with the results; repeatable",
    )
    run.add_argument("--quiet", action="store_true", help="suppress progress lines")
    run.set_defaults(func=cmd_run)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point.

    Args:
        argv: Argument vector, defaulting to ``sys.argv[1:]``.

    Returns:
        The chosen command's exit code.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130
