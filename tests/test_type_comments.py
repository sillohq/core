"""No prose comment may begin with ``# type:``.

mypy reads a line-initial ``# type:`` as a PEP 484 type comment, whatever the
words after it are. A sentence that happened to wrap so that "type:" landed at
the start of a line therefore parsed as an annotation, and mypy answered::

    sillo/core/encoding.py:291: error: Invalid syntax  [syntax]
    Found 1 error in 1 file (errors prevented further checking)

The second line is the damage. mypy stops on a syntax error, so *nothing* was
checked -- not the rest of that file and not the user's own code, since
importing sillo pulls the file in. Every sillo user running mypy got one
unactionable error pointing at a comment inside the framework, and no type
checking at all.

Nothing else catches this: the comment is valid Python, ruff is happy, the
tests pass, and the file behaves correctly at runtime. It is visible only to
a type checker, and only as a failure that looks like it belongs to whoever
is running it.
"""

from __future__ import annotations

import re
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1] / "sillo"

#: A comment that opens a line with `# type:`. `# type: ignore` is the real
#: directive and is left alone.
#:
#: The lookahead swallows the whitespace itself. Written as `\s*(?!ignore)`
#: the `\s*` backtracks to zero characters, the lookahead then compares
#: against " ignore", and every real `# type: ignore` matches.
TYPE_COMMENT = re.compile(r"^\s*#\s*type:(?!\s*ignore)")


def test_no_comment_is_mistaken_for_a_type_annotation() -> None:
    offenders: list[str] = []

    for path in PACKAGE.rglob("*.py"):
        for number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if TYPE_COMMENT.match(line):
                offenders.append(f"{path.relative_to(PACKAGE.parent)}:{number}: {line.strip()}")

    assert not offenders, (
        "these comments start a line with `# type:`, which mypy parses as a "
        "PEP 484 type comment and then fails the whole file on: "
        f"{offenders}. Reword or reflow so `type:` is not the first thing "
        "after the `#`."
    )


def test_the_scan_reads_real_files() -> None:
    """Guard against the glob matching nothing and the test passing empty."""
    assert len(list(PACKAGE.rglob("*.py"))) > 50
