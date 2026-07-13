"""
sillo.work.background — Fire-and-forget tasks with supervision.

- ``BackgroundTask`` — launch & track async work
- ``Supervisor`` — auto-restart on failure with configurable policies
"""

from .tasks import BackgroundTask
from .supervisor import Supervisor, RestartPolicy

__all__ = ["BackgroundTask", "Supervisor", "RestartPolicy"]
