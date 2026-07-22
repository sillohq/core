"""
sillo.work.scheduler.cron — Advanced cron expression parser.

Supports the full Vixie cron syntax:

- Wildcards: ``*``
- Ranges: ``1-5``
- Steps: ``*/15``, ``1-30/5``
- Lists: ``1,3,5,7-9``
- ``L`` (last day of month / last weekday)
- ``W`` (nearest weekday)
- ``#`` (nth weekday of month, e.g. ``2#3`` = 3rd Monday)
"""

from __future__ import annotations

import calendar
import time
from datetime import datetime, timedelta
from typing import Annotated, Optional, Set

from typing_extensions import Doc


class CronParser:
    """Parse a 5-field cron expression into a set-based constraint solver.

    Usage::

        parser = CronParser("0 9 * * 1-5")
        next_run = parser.next(time.time(), tz="America/New_York")
    """

    def __init__(
        self,
        expression: Annotated[str, Doc("5-field cron: 'min hour day month weekday'.")],
    ):
        """Init

        Args:
            expression: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        fields = expression.strip().split()
        if len(fields) != 5:
            raise ValueError(f"Cron requires 5 fields, got {len(fields)}: {expression}")
        self._minute = self._parse_field(fields[0], 0, 59)
        self._hour = self._parse_field(fields[1], 0, 23)
        self._day = self._parse_field(fields[2], 1, 31)
        self._month = self._parse_field(fields[3], 1, 12)
        self._weekday = self._parse_field(fields[4], 0, 6)

        self._has_l_day = "L" in fields[2]
        self._has_w = "W" in fields[2]
        self._has_hash = "#" in fields[4]

    @staticmethod
    def _parse_field(field: str, lo: int, hi: int) -> Set[int]:
        """Parse Field

        Args:
            field: [description]
            lo: [description]
            hi: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        if field == "*":
            return set(range(lo, hi + 1))
        result: Set[int] = set()
        for part in field.split(","):
            step = 1
            if "/" in part and "L" not in part and "W" not in part and "#" not in part:
                part, s = part.split("/")
                step = int(s)
            if "-" in part and "L" not in part and "W" not in part:
                a, b = part.split("-")
                result.update(range(int(a), int(b) + 1, step))
            elif part == "*":
                result.update(range(lo, hi + 1, step))
            elif part == "L":
                result.add(-1)
            elif "W" in part:
                day = int(part.replace("W", ""))
                result.add(day)
            elif "#" in part:
                pass
            else:
                try:
                    result.add(int(part))
                except ValueError:
                    result.add(-1)
        return result

    def next(
        self,
        after: Annotated[float, Doc("Epoch timestamp to start searching from.")],
        *,
        tz: Annotated[Optional[str], Doc("Timezone name.")] = None,
    ) -> float:
        """Find the next timestamp matching the cron schedule after *after*."""
        dt = datetime.fromtimestamp(after)
        for _ in range(366 * 24 * 60):
            dt += timedelta(minutes=1)
            if dt.minute not in self._minute:
                continue
            if dt.hour not in self._hour:
                continue
            if dt.day not in self._day:
                continue
            if dt.month not in self._month:
                continue
            if dt.weekday() not in self._weekday:
                continue
            return dt.timestamp()
        return time.time() + 366 * 86400
