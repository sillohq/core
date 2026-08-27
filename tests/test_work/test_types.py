"""Coverage for sillo.work.types: TaskResult's derived properties and
serialisation, plus QueueStats/WorkerStats/SchedulerStats.to_dict(), none of
which had direct tests.
"""

from __future__ import annotations

from sillo.work.types import (
    CircuitState,
    QueueHealth,
    QueueStats,
    SchedulerStats,
    TaskPriority,
    TaskResult,
    TaskStatus,
    WorkerStats,
)


def _result(**kwargs):
    defaults = dict(task_id="t1", name="job", status=TaskStatus.COMPLETED)
    defaults.update(kwargs)
    return TaskResult(**defaults)


def test_latency_ms_zero_without_timestamps():
    assert _result().latency_ms == 0


def test_latency_ms_computed_from_created_and_started():
    result = _result(created_at=1.0, started_at=1.25)
    assert result.latency_ms == 250


def test_is_terminal_true_for_completed_failed_cancelled():
    assert _result(status=TaskStatus.COMPLETED).is_terminal is True
    assert _result(status=TaskStatus.FAILED).is_terminal is True
    assert _result(status=TaskStatus.CANCELLED).is_terminal is True
    assert _result(status=TaskStatus.RUNNING).is_terminal is False


def test_serialise_result_none():
    result = _result(result=None)
    data = result.to_dict()
    assert data["result"] is None


def test_serialise_result_truncates_long_values():
    long_value = "x" * 600
    result = _result(result=long_value)
    serialised = result.to_dict()["result"]
    assert serialised.endswith("…")
    assert len(serialised) == 501


def test_serialise_result_falls_back_on_str_error():
    class Unstringable:
        def __str__(self):
            raise RuntimeError("nope")

    result = _result(result=Unstringable())
    assert result.to_dict()["result"] == "<unserialisable>"


def test_task_result_repr():
    result = _result(task_id="12345678-abcd", attempt=2)
    text = repr(result)
    assert "12345678" in text
    assert "job" in text
    assert "attempt=2" in text


def test_queue_stats_to_dict():
    stats = QueueStats(
        name="default", size=3, completed=10, failed=1, oldest_age_ms=500
    )
    assert stats.to_dict() == {
        "name": "default",
        "size": 3,
        "completed": 10,
        "failed": 1,
        "oldest_age_ms": 500,
        "status": QueueHealth.HEALTHY.value,
    }


def test_worker_stats_to_dict():
    stats = WorkerStats(processed=5, failed=1, active=2, workers=4)
    data = stats.to_dict()
    assert data["processed"] == 5
    assert data["circuit"] == CircuitState.CLOSED.value


def test_scheduler_stats_to_dict():
    stats = SchedulerStats(jobs_total=2, jobs_active=1, runs_total=10)
    assert stats.to_dict() == {
        "jobs_total": 2,
        "jobs_active": 1,
        "jobs_paused": 0,
        "runs": 10,
        "errors": 0,
    }
