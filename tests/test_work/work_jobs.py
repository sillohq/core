"""Resolvable Job subclasses for sillo.work queue tests.

These are imported by qualified name (``tests.test_work.work_jobs.SendEmail``)
so that ``QueueWorker._resolve_job_class`` can reconstruct them from a
serialised payload, mirroring how real multi-process workers find jobs.
"""

from sillo.work.queue.job import Job


# Shared mutable side-effect sinks so tests can assert execution.
SENT_EMAILS: list[str] = []
FLIGHTS: list[str] = []


class SendEmail(Job):
    queue = "emails"
    tries = 1
    timeout = 30

    def __init__(self, to: str, subject: str = "Hi"):
        self.to = to
        self.subject = subject

    async def handle(self):
        SENT_EMAILS.append(f"{self.to}:{self.subject}")
        return f"sent:{self.to}"


class RecordFlight(Job):
    """Job that records a flight id; used for batch/chain assertions."""

    def __init__(self, flight: str):
        self.flight = flight

    async def handle(self):
        FLIGHTS.append(self.flight)
        return self.flight
