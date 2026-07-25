"""
sillo.work.scheduler.triggers — Advanced schedule trigger types.

Supports four trigger families:

* ``IntervalTrigger`` — fire every N seconds with optional jitter
* ``CronTrigger`` — standard 5-field cron with timezone support
* ``DateTrigger`` — one-shot fire at a specific epoch timestamp
* ``CompoundTrigger`` — combine multiple triggers with AND/OR logic
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Annotated, List, Optional

from typing_extensions import Doc

from .cron import CronParser


class TriggerType(Enum):
    """Triggertype

    Returns:
        [description]

    Raises:
        [description]
    """

    INTERVAL = "interval"
    CRON = "cron"
    DATETIME = "datetime"
    COMPOUND = "compound"


class CompoundLogic(Enum):
    """Compoundlogic

    Returns:
        [description]

    Raises:
        [description]
    """

    AND = "and"
    OR = "or"


@dataclass
class IntervalTrigger:
    """Fire repeatedly every *seconds* with optional jitter.

    Parameters
    ----------
    seconds:
        Interval in seconds.
    jitter:
        Random offset added to each fire time to spread load.
    """

    seconds: Annotated[float, Doc("Interval in seconds.")]
    jitter: Annotated[float, Doc("Max random jitter in seconds.")] = 0.0

    def next_fire(
        self, last_fire: Annotated[float, Doc("Timestamp of last execution.")]
    ) -> float:
        """Calculate the next fire timestamp."""
        j = random.uniform(0, self.jitter) if self.jitter else 0
        return time.time() + self.seconds + j


@dataclass
class CronTrigger:
    """Standard 5-field cron expression with optional timezone.

    Supports ranges (``1-5``), steps (``*/15``, ``1-5/2``), lists
    (``1,3,5``), and the special characters ``L`` (last) and ``W``
    (nearest weekday).

    Parameters
    ----------
    expression:
        5-field cron string: ``"minute hour day month weekday"``
    timezone:
        IANA timezone name (e.g. ``"America/New_York"``).
    """

    expression: Annotated[str, Doc("Cron expression — 'min hour day month weekday'.")]
    timezone: Annotated[Optional[str], Doc("IANA timezone name.")] = None

    def __post_init__(self):
        """Post Init

        Returns:
            [description]

        Raises:
            [description]
        """
        parser = CronParser(self.expression)
        self._parser = parser

    def next_fire(
        self, last_fire: Annotated[float, Doc("Timestamp of last execution.")]
    ) -> float:
        """Calculate the next fire timestamp from the cron schedule."""
        base = last_fire if last_fire > 0 else time.time()
        return self._parser.next(base, tz=self.timezone)


@dataclass
class DateTrigger:
    """One-shot trigger — fires once at *at* and never again.

    Parameters
    ----------
    at:
        Absolute epoch timestamp when the job should fire.
    """

    at: Annotated[float, Doc("Epoch timestamp for one-shot execution.")]

    def next_fire(
        self, last_fire: Annotated[float, Doc("Timestamp of last execution.")]
    ) -> Optional[float]:
        """Return the fire time. Returns None after first fire."""
        return None if last_fire > 0 else self.at


@dataclass
class CompoundTrigger:
    """Combine multiple triggers with AND or OR logic.

    ``OR`` fires whenever ANY child trigger is due.
    ``AND`` fires only when ALL child triggers are simultaneously due.

    Parameters
    ----------
    triggers:
        List of child trigger instances.
    logic:
        ``CompoundLogic.OR`` (default) or ``CompoundLogic.AND``.
    """

    triggers: Annotated[List[object], Doc("Child triggers.")] = field(
        default_factory=list
    )
    logic: Annotated[CompoundLogic, Doc("OR or AND logic.")] = CompoundLogic.OR

    def next_fire(
        self, last_fire: Annotated[float, Doc("Timestamp of last execution.")]
    ) -> Optional[float]:
        """Calculate the next fire time based on the compound logic."""
        candidates = []
        for t in self.triggers:
            nf = t.next_fire(last_fire)  # ty: ignore[unresolved-attribute]
            if nf is not None:
                candidates.append(nf)
        if not candidates:
            return None
        if self.logic == CompoundLogic.OR:
            return min(candidates)
        else:
            return max(candidates)
