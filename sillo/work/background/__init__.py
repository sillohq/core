"""
sillo.work.background — Fire-and-forget tasks with supervision.

- ``BackgroundTask`` — launch & track async work
- ``Supervisor`` — auto-restart on failure with configurable policies
"""

from .supervisor import RestartPolicy, Supervisor
from .tasks import BackgroundTask

__all__ = ["BackgroundTask", "RestartPolicy", "Supervisor"]
