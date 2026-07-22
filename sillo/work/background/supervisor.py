"""
sillo.work.background.supervisor — Task supervision with restart policies.

A ``Supervisor`` monitors background tasks and can restart them if they
fail, enforcing policies like "always restart", "restart up to N times",
or "backoff-based restart".
"""

from __future__ import annotations

import asyncio
import logging
from enum import Enum
from typing import Annotated, Any, Awaitable, Callable, Dict, Optional

from typing_extensions import Doc

from .tasks import BackgroundTask

logger = logging.getLogger("sillo.work.background.supervisor")


class RestartPolicy(Enum):
    """Restart behaviour when a supervised task fails."""

    NEVER = "never"
    ALWAYS = "always"
    ON_FAILURE = "on_failure"
    EXPONENTIAL_BACKOFF = "exponential_backoff"


class Supervisor:
    """Monitors a background task and restarts it according to a policy.

    Usage::

        supervisor = Supervisor(send_email, RestartPolicy.EXPONENTIAL_BACKOFF, max_restarts=5)
        await supervisor.start("user@ex.com")
    """

    def __init__(
        self,
        func: Annotated[
            Callable[..., Awaitable[Any]], Doc("Async callable to supervise.")
        ],
        policy: Annotated[
            RestartPolicy, Doc("Restart behaviour.")
        ] = RestartPolicy.ON_FAILURE,
        *,
        max_restarts: Annotated[int, Doc("Max total restarts before giving up.")] = 3,
        base_delay: Annotated[float, Doc("Initial backoff seconds.")] = 1.0,
        max_delay: Annotated[float, Doc("Max backoff seconds.")] = 60.0,
        name: Annotated[Optional[str], Doc("Label for logging.")] = None,
    ):
        """Init

        Args:
            func: [description]
            policy: [description]

        Returns:
            [description]

        Raises:
            [description]
        """
        self.func = func
        self.policy = policy
        self.max_restarts = max_restarts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.name = name or func.__name__
        self._restarts = 0
        self._current_task: Optional[BackgroundTask] = None
        self._running = False
        self._stopped = asyncio.Event()

    async def start(self, *args: Any, **kwargs: Any) -> None:
        """Launch the supervised task and begin monitoring."""
        self._running = True
        self._restarts = 0
        self._stopped.clear()

        while self._running:
            self._current_task = BackgroundTask.run(
                self.func, *args, name=self.name, **kwargs
            )
            try:
                await self._current_task.wait()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("Supervised task %s failed: %s", self.name, exc)
                if not self._should_restart():
                    logger.error(
                        "Supervised task %s exhausted restarts (%d)",
                        self.name,
                        self.max_restarts,
                    )
                    break
                delay = min(self.base_delay * (2**self._restarts), self.max_delay)
                logger.info(
                    "Restarting %s in %.1fs (attempt %d)",
                    self.name,
                    delay,
                    self._restarts + 1,
                )
                await asyncio.sleep(delay)
                self._restarts += 1
            else:
                if (
                    self.policy == RestartPolicy.NEVER
                    or self.policy == RestartPolicy.ON_FAILURE
                ):
                    break

        self._stopped.set()

    def stop(self) -> None:
        """Signal the supervisor to stop (does not cancel the current task)."""
        self._running = False
        if self._current_task:
            self._current_task.cancel()

    async def wait(self, timeout: Optional[float] = None) -> None:
        """Block until the supervisor stops."""
        await asyncio.wait_for(self._stopped.wait(), timeout=timeout)

    def _should_restart(self) -> bool:
        """Should Restart

        Returns:
            [description]

        Raises:
            [description]
        """
        if self.policy == RestartPolicy.NEVER:
            return False
        if self.policy == RestartPolicy.ALWAYS:
            return self.max_restarts == 0 or self._restarts < self.max_restarts
        if self.policy in (RestartPolicy.ON_FAILURE, RestartPolicy.EXPONENTIAL_BACKOFF):
            return self.max_restarts == 0 or self._restarts < self.max_restarts
        return False

    def to_dict(self) -> Dict[str, Any]:
        """To Dict

        Returns:
            [description]

        Raises:
            [description]
        """
        return {
            "name": self.name,
            "policy": self.policy.value,
            "restarts": self._restarts,
            "max_restarts": self.max_restarts,
            "running": self._running,
        }
