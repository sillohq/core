"""The data every framework serves.

There is exactly one definition of each payload and all three applications
import it from here. That is not tidiness, it is the thing that makes the
comparison mean anything: a benchmark where one framework serves a slightly
smaller object, or builds its rows a different way, measures the difference in
the fixtures rather than the difference in the frameworks.

Nothing here is generated per request. The objects are built once at import and
handed to the serializer as-is, so what is timed is the framework's encoding
and response path, not list comprehensions in the benchmark's own code.
"""

from __future__ import annotations

from typing import Any

#: The plaintext body. Deliberately tiny — this scenario exists to isolate
#: fixed per-request overhead, so the body should contribute nothing.
PLAINTEXT: str = "ok"

#: A small object, the shape of a typical API response for a single record.
SMALL_JSON: dict[str, Any] = {
    "id": 1,
    "name": "SilloDraft",
    "active": True,
}


def _rows(count: int) -> list[dict[str, Any]]:
    """Build the row set served by the ``rows`` scenario.

    Args:
        count: How many rows to generate.

    Returns:
        A list of nested dictionaries. Nesting is deliberate: a flat list of
        scalars is encoded by a fast path in most serializers and would not
        resemble the query results an application actually returns.
    """
    return [
        {
            "id": index,
            "title": f"Document {index}",
            "words": index * 13,
            "status": "published",
            "author": {"id": index % 7, "name": f"User {index % 7}"},
        }
        for index in range(count)
    ]


#: 200 nested rows, the size of a generous page of results.
ROWS: list[dict[str, Any]] = _rows(200)

#: The ``rows`` scenario's full response body.
ROWS_RESPONSE: dict[str, Any] = {"data": ROWS}
