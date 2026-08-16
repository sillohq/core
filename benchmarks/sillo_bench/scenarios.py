"""What gets measured, and why each one is here.

A scenario is a single route that every framework implements identically. They
are chosen so that a slow result points at something specific rather than at
"the framework": ``plaintext`` isolates fixed overhead, ``rows`` isolates the
JSON encoder, and the two in between separate routing and validation from both.

Reading a result set is mostly a matter of comparing scenarios *within* a
framework. A framework that is quick on ``rows`` and slow on ``plaintext`` has
a fast encoder behind an expensive request path, which is a different problem
from being uniformly slow.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Scenario:
    """One route, implemented the same way by every framework.

    Attributes:
        name: The identifier used on the command line and in exports.
        path: The request path, already concrete — no framework is asked to
            substitute anything at run time.
        summary: One line on what this scenario isolates, shown by ``list``.
        expect_status: The status code a correct implementation returns. The
            runner checks this before measuring, so a framework that 404s is
            reported as broken rather than as very fast.
        expect_contains: A substring that must appear in the response body.
            This is the guard against measuring an error page: a 500 with a
            short body would otherwise post an excellent requests-per-second.
    """

    name: str
    path: str
    summary: str
    expect_status: int = 200
    expect_contains: str = ""


#: Registered in the order they are reported.
SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        name="plaintext",
        path="/plaintext",
        summary="Fixed per-request overhead: routing, request build, response send.",
        expect_contains="ok",
    ),
    Scenario(
        name="json",
        path="/json",
        summary="The same, plus encoding a small object.",
        expect_contains="SilloDraft",
    ),
    Scenario(
        name="path-param",
        path="/items/42",
        summary="Adds path extraction and integer coercion.",
        expect_contains="42",
    ),
    Scenario(
        name="query-param",
        path="/search?q=sillo&page=3&per_page=25",
        summary="Adds query string parsing and coercion of three values.",
        expect_contains="sillo",
    ),
    Scenario(
        name="rows",
        path="/rows",
        summary="Dominated by the JSON encoder: 200 nested objects.",
        expect_contains="Document 199",
    ),
)

SCENARIOS_BY_NAME: dict[str, Scenario] = {s.name: s for s in SCENARIOS}


def resolve(names: str | None) -> list[Scenario]:
    """Turn a comma-separated selection into scenarios.

    Args:
        names: Comma-separated scenario names, or ``None`` for all of them.

    Returns:
        The selected scenarios, in registration order rather than the order
        they were typed, so two runs with the same set are comparable.

    Raises:
        ValueError: If any name is not a registered scenario.
    """
    if not names:
        return list(SCENARIOS)

    wanted = {part.strip() for part in names.split(",") if part.strip()}
    unknown = wanted - set(SCENARIOS_BY_NAME)
    if unknown:
        raise ValueError(
            f"unknown scenario(s): {', '.join(sorted(unknown))}. "
            f"available: {', '.join(SCENARIOS_BY_NAME)}"
        )
    return [s for s in SCENARIOS if s.name in wanted]
