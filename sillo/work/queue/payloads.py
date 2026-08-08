"""
sillo.work.queue.payloads — Job serialisation and deserialisation.

Encodes a job's class name, arguments, and metadata into a JSON string
that can be pushed onto any queue backend and reconstructed on the
worker side.
"""

from __future__ import annotations

import json
from typing import Annotated, Any

from typing_extensions import Doc


class JobPayload:
    """Serialisable snapshot of a job ready for the queue."""

    def __init__(
        self,
        job_class: Annotated[str, Doc("Fully qualified class name.")],
        data: Annotated[dict[str, Any], Doc("Job constructor kwargs.")],
        *,
        max_tries: Annotated[int, Doc("Max attempts.")] = 1,
        timeout: Annotated[float | None, Doc("Per-job timeout in seconds.")] = None,
        delay: Annotated[int, Doc("Seconds to delay.")] = 0,
        priority: Annotated[int, Doc("0=normal, higher=more urgent.")] = 0,
        queue: Annotated[str, Doc("Target queue name.")] = "default",
    ):
        """Init"""
        self.job_class = job_class
        self.data = data
        self.max_tries = max_tries
        self.timeout = timeout
        self.delay = delay
        self.priority = priority
        self.queue = queue

    def to_json(self) -> str:
        """To Json"""
        return json.dumps(self.__dict__, default=str)


class PayloadSerializer:
    """Serialise / deserialise job payloads."""

    def serialize(
        self,
        job_class: Annotated[
            str, Doc("Fully qualified job class name (e.g. 'mymodule.MyJob').")
        ],
        data: Annotated[
            dict[str, Any], Doc("Keyword arguments for the job constructor.")
        ],
        *,
        max_tries: Annotated[int, Doc("Maximum execution attempts.")] = 1,
        timeout: Annotated[float | None, Doc("Per-job timeout.")] = None,
        delay: Annotated[int, Doc("Delay in seconds.")] = 0,
        queue: Annotated[str, Doc("Queue name.")] = "default",
    ) -> str:
        """Encode a job into a queue-ready JSON string."""
        payload = JobPayload(
            job_class=job_class,
            data=data,
            max_tries=max_tries,
            timeout=timeout,
            delay=delay,
            queue=queue,
        )
        return payload.to_json()

    def deserialize(
        self, payload_str: Annotated[str, Doc("JSON string from the queue.")]
    ) -> dict[str, Any]:
        """Decode a queue payload back into a dict ready for job construction."""
        return json.loads(payload_str)
