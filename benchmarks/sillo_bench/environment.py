"""What the numbers were produced on.

Throughput figures are meaningless without this. A result of 40,000 req/s says
nothing on its own; the same suite on a laptop with thermal throttling and on a
dedicated server disagree by more than the frameworks do. Every export carries
this block so a published table can be checked, reproduced, or dismissed.

Framework versions are read from installed metadata rather than from imports,
so the recorded version is the distribution that is actually installed.
"""

from __future__ import annotations

import platform
import socket
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version


def _package_version(name: str) -> str:
    """Return an installed distribution's version, or ``"not installed"``."""
    try:
        return version(name)
    except PackageNotFoundError:
        return "not installed"


def _cpu_model() -> str:
    """Return a human-readable CPU name, falling back to the architecture."""
    try:
        if sys.platform == "darwin":
            out = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout.strip()
        elif sys.platform.startswith("linux"):
            with open("/proc/cpuinfo") as handle:
                for line in handle:
                    if line.startswith("model name"):
                        return line.split(":", 1)[1].strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return platform.processor() or platform.machine()


def _cpu_count() -> int:
    """Return the number of logical CPUs visible to this process."""
    import os

    return os.cpu_count() or 0


@dataclass
class Environment:
    """A snapshot of the machine and the software under test.

    Attributes:
        captured_at: UTC timestamp, ISO 8601.
        hostname: The machine's name.
        platform: OS and release.
        cpu: CPU model string.
        cpu_count: Logical CPU count.
        python: Full Python version.
        implementation: CPython, PyPy, and so on. Worth recording because it
            moves results more than most framework differences do.
        packages: Version of every package that can affect a result.
        load_tool: Name and version of the generator that produced the numbers.
        notes: Free-form caveats attached by the runner.
    """

    captured_at: str
    hostname: str
    platform: str
    cpu: str
    cpu_count: int
    python: str
    implementation: str
    packages: dict[str, str]
    load_tool: str = ""
    notes: list[str] = field(default_factory=list)

    @classmethod
    def capture(cls, load_tool: str = "") -> Environment:
        """Take a snapshot of the current machine.

        Args:
            load_tool: Name and version of the load generator in use.

        Returns:
            A populated ``Environment``.
        """
        return cls(
            captured_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            hostname=socket.gethostname(),
            platform=f"{platform.system()} {platform.release()} ({platform.machine()})",
            cpu=_cpu_model(),
            cpu_count=_cpu_count(),
            python=platform.python_version(),
            implementation=platform.python_implementation(),
            packages={
                name: _package_version(name)
                for name in (
                    "sillo-framework",
                    "fastapi",
                    "starlette",
                    "django",
                    "uvicorn",
                    "pydantic",
                    "httptools",
                    "uvloop",
                )
            },
            load_tool=load_tool,
        )

    def as_dict(self) -> dict:
        """Return the snapshot as a plain dictionary for serialization."""
        return asdict(self)

    def describe(self) -> str:
        """Render the snapshot as the block printed above a result table."""
        lines = [
            f"  machine   {self.cpu} ({self.cpu_count} cores)",
            f"  platform  {self.platform}",
            f"  python    {self.python} ({self.implementation})",
            f"  load tool {self.load_tool}",
        ]
        installed = {k: v for k, v in self.packages.items() if v != "not installed"}
        lines.append("  packages  " + ", ".join(f"{k} {v}" for k, v in installed.items()))
        return "\n".join(lines)
