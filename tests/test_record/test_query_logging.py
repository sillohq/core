"""
Query log collection, slow-query flagging, and N+1 detection.

The logger is fed synthetic entries rather than driven through a real
database, which keeps the thresholds exact and the timings deterministic.
"""

import pytest

from sillo.record.logging import QueryLogEntry, QueryLogger


@pytest.fixture
def log():
    logger = QueryLogger(slow_threshold_ms=100.0)
    logger.start()
    return logger


# ── entries ──────────────────────────────────────────────────────────────


def test_an_entry_keeps_its_sql_and_timing():
    entry = QueryLogEntry("SELECT 1", None, 12.5)
    assert entry.sql == "SELECT 1"
    assert entry.duration_ms == 12.5


def test_an_entry_records_its_parameters():
    entry = QueryLogEntry("SELECT ?", [42], 1.0)
    assert entry.params == [42]


def test_an_entry_is_timestamped():
    assert QueryLogEntry("SELECT 1", None, 1.0).timestamp > 0


def test_an_entry_records_its_source():
    assert QueryLogEntry("SELECT 1", None, 1.0, source="users.py:42").source == (
        "users.py:42"
    )


def test_the_repr_leads_with_the_duration():
    assert repr(QueryLogEntry("SELECT 1", None, 12.5)).startswith("[12.5ms]")


def test_a_long_statement_is_truncated_in_the_repr():
    """The log line is for scanning, not for replaying the query."""
    entry = QueryLogEntry("SELECT " + "x" * 500, None, 1.0)
    assert len(repr(entry)) < 200


# ── collection ───────────────────────────────────────────────────────────


def test_a_logged_query_is_counted(log):
    log.log("SELECT 1", duration_ms=5)
    assert log.total_queries == 1


def test_nothing_is_collected_before_start():
    logger = QueryLogger()
    logger.log("SELECT 1", duration_ms=5)
    assert logger.total_queries == 0


def test_nothing_is_collected_after_stop(log):
    log.stop()
    log.log("SELECT 1", duration_ms=5)
    assert log.total_queries == 0


def test_starting_again_clears_the_previous_run(log):
    """One logger per request means the second request must not inherit the
    first one's queries."""
    log.log("SELECT 1", duration_ms=5)
    log.start()
    assert log.total_queries == 0


def test_durations_are_summed(log):
    log.log("SELECT 1", duration_ms=5)
    log.log("SELECT 2", duration_ms=7.5)
    assert log.total_time_ms == 12.5


def test_the_total_of_an_empty_log_is_zero(log):
    assert log.total_time_ms == 0


def test_the_entries_are_returned_in_order(log):
    log.log("SELECT 1", duration_ms=1)
    log.log("SELECT 2", duration_ms=1)
    assert [e.sql for e in log.entries()] == ["SELECT 1", "SELECT 2"]


def test_the_entry_list_is_a_copy(log):
    log.log("SELECT 1", duration_ms=1)
    log.entries().clear()
    assert log.total_queries == 1


# ── slow queries ─────────────────────────────────────────────────────────


def test_a_query_over_the_threshold_is_slow(log):
    log.log("SELECT slow", duration_ms=250)
    assert len(log.slow_queries) == 1


def test_a_query_under_the_threshold_is_not(log):
    log.log("SELECT fast", duration_ms=5)
    assert log.slow_queries == []


def test_a_query_exactly_at_the_threshold_is_not_slow(log):
    assert QueryLogger(slow_threshold_ms=100).slow_queries == []
    log.log("SELECT borderline", duration_ms=100)
    assert log.slow_queries == []


def test_the_threshold_is_configurable():
    logger = QueryLogger(slow_threshold_ms=1.0)
    logger.start()
    logger.log("SELECT 1", duration_ms=5)
    assert len(logger.slow_queries) == 1


def test_a_slow_query_is_warned_about(log, caplog):
    with caplog.at_level("WARNING"):
        log.log("SELECT pg_sleep(1)", duration_ms=1500)
    assert "SLOW QUERY" in caplog.text


def test_a_fast_query_is_not_warned_about(log, caplog):
    with caplog.at_level("WARNING"):
        log.log("SELECT 1", duration_ms=1)
    assert "SLOW QUERY" not in caplog.text


def test_slow_queries_are_still_counted_in_the_total(log):
    log.log("SELECT slow", duration_ms=250)
    log.log("SELECT fast", duration_ms=1)
    assert log.total_queries == 2


# ── N+1 detection ────────────────────────────────────────────────────────


def test_a_repeated_query_is_flagged(log):
    """Six identical statements in one request is the signature of a loop
    fetching relations row by row."""
    for _ in range(6):
        log.log("SELECT * FROM posts WHERE user_id = ?", duration_ms=1)
    assert log.detect_n_plus_one()


def test_five_repeats_are_below_the_threshold(log):
    for _ in range(5):
        log.log("SELECT * FROM posts WHERE user_id = ?", duration_ms=1)
    assert log.detect_n_plus_one() == []


def test_distinct_queries_are_not_flagged(log):
    for i in range(10):
        log.log(f"SELECT * FROM table_{i}", duration_ms=1)
    assert log.detect_n_plus_one() == []


def test_each_offending_statement_is_reported_once(log):
    for _ in range(8):
        log.log("SELECT a", duration_ms=1)
    assert len(log.detect_n_plus_one()) == 1


def test_two_offending_statements_are_both_reported(log):
    for _ in range(6):
        log.log("SELECT a", duration_ms=1)
    for _ in range(6):
        log.log("SELECT b", duration_ms=1)
    assert len(log.detect_n_plus_one()) == 2


def test_the_warning_names_the_repeat_count(log):
    for _ in range(7):
        log.log("SELECT a", duration_ms=1)
    assert "7 times" in log.detect_n_plus_one()[0]


def test_detection_on_an_empty_log(log):
    assert log.detect_n_plus_one() == []


# ── the report ───────────────────────────────────────────────────────────


def test_the_report_counts_the_queries(log):
    log.log("SELECT 1", duration_ms=1)
    log.log("SELECT 2", duration_ms=2)
    assert log.report()["total_queries"] == 2


def test_the_report_totals_the_time(log):
    log.log("SELECT 1", duration_ms=1.5)
    assert log.report()["total_time_ms"] == 1.5


def test_the_report_counts_the_slow_queries(log):
    log.log("SELECT slow", duration_ms=500)
    log.log("SELECT fast", duration_ms=1)
    assert log.report()["slow_queries"] == 1


def test_the_report_details_the_slow_queries(log):
    log.log("SELECT pg_sleep(1)", duration_ms=500)
    assert "pg_sleep" in log.report()["slow_details"][0]


def test_the_report_includes_the_n_plus_one_warnings(log):
    for _ in range(6):
        log.log("SELECT a", duration_ms=1)
    assert log.report()["n_plus_one_warnings"]


def test_detection_can_be_switched_off():
    logger = QueryLogger(detect_n_plus_one=False)
    logger.start()
    for _ in range(10):
        logger.log("SELECT a", duration_ms=1)
    assert logger.report()["n_plus_one_warnings"] == []


def test_the_report_of_an_empty_log(log):
    report = log.report()
    assert report["total_queries"] == 0
    assert report["slow_queries"] == 0
    assert report["n_plus_one_warnings"] == []
