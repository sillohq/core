"""
sillo.record.logging — Query log, slow query detection, and N+1 warnings.

Tracks all database queries issued during a request and can report
slow queries or potential N+1 problems.
"""

from __future__ import annotations

import logging
import time
from typing import Annotated, Any, Dict, List, Optional

from typing_extensions import Doc

logger = logging.getLogger("sillo.record.logging")


class QueryLogEntry:
    """A single logged query."""

    def __init__(self, sql: str, params: Any, duration_ms: float, source: str = ""):
        """Init

        Args:
            sql: [description]
            params: [description]
            duration_ms: [description]
            source: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        self.sql = sql
        self.params = params
        self.duration_ms = duration_ms
        self.source = source
        self.timestamp = time.time()

    def __repr__(self):
        """Repr

        Returns:
            [description]

        Raises:
            [description]
        """
        return f"[{self.duration_ms:.1f}ms] {self.sql[:120]}"


class QueryLogger:
    """Query log collector — one per request.

    Usage::

        log = QueryLogger(slow_threshold_ms=100)
        log.start()
        # ... queries ...
        log.stop()
        report = log.report()
    """

    def __init__(
        self, slow_threshold_ms: float = 100.0, detect_n_plus_one: bool = True
    ):
        """Init

        Args:
            slow_threshold_ms: [description]
            detect_n_plus_one: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        self._entries: List[QueryLogEntry] = []
        self._slow_threshold = slow_threshold_ms
        self._detect_n1 = detect_n_plus_one
        self._started = False
        self._start_time = 0.0

    def start(self) -> None:
        """Start

        Returns:
            [description]

        Raises:
            [description]
        """
        self._entries.clear()
        self._started = True
        self._start_time = time.time()

    def stop(self) -> None:
        """Stop

        Returns:
            [description]

        Raises:
            [description]
        """
        self._started = False

    def log(
        self, sql: str, params: Any = None, duration_ms: float = 0, source: str = ""
    ) -> None:
        """Log

        Args:
            sql: [description]
            params: [description]
            duration_ms: [description]
            source: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        if self._started:
            entry = QueryLogEntry(sql, params, duration_ms, source)
            self._entries.append(entry)
            if duration_ms > self._slow_threshold:
                logger.warning("SLOW QUERY [%.1fms] %s", duration_ms, sql[:200])

    @property
    def total_time_ms(self) -> float:
        """Total Time Ms

        Returns:
            [description]

        Raises:
            [description]
        """
        return sum(e.duration_ms for e in self._entries)

    @property
    def total_queries(self) -> int:
        """Total Queries

        Returns:
            [description]

        Raises:
            [description]
        """
        return len(self._entries)

    @property
    def slow_queries(self) -> List[QueryLogEntry]:
        """Slow Queries

        Returns:
            [description]

        Raises:
            [description]
        """
        return [e for e in self._entries if e.duration_ms > self._slow_threshold]

    def detect_n_plus_one(self) -> List[str]:
        """Detect N+1 query patterns. Returns list of warning messages."""
        warnings = []
        sql_list = [e.sql for e in self._entries]
        for i, sql in enumerate(sql_list):
            count = sql_list.count(sql)
            if count > 5:
                warnings.append(f"N+1 detected: query '{sql[:100]}' ran {count} times")
        return list(set(warnings))

    def report(self) -> Dict[str, Any]:
        """Report

        Returns:
            [description]

        Raises:
            [description]
        """
        return {
            "total_queries": self.total_queries,
            "total_time_ms": self.total_time_ms,
            "slow_queries": len(self.slow_queries),
            "slow_details": [str(e) for e in self.slow_queries],
            "n_plus_one_warnings": self.detect_n_plus_one() if self._detect_n1 else [],
        }

    def entries(self) -> List[QueryLogEntry]:
        """Entries

        Returns:
            [description]

        Raises:
            [description]
        """
        return list(self._entries)
