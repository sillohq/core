import time
from typing import Any, Dict

from .emitter import EventEmitter

class EventBenchmark:
    """
    Utility for benchmarking event performance.
    """

    @staticmethod
    def benchmark(
        emitter: EventEmitter, event_name: str, iterations: int = 1000
    ) -> Dict[str, Any]:
        """
        Benchmark event triggering performance.

        Args:
            emitter: Event emitter instance
            event_name: Name of the event to benchmark
            iterations: Number of iterations to run

        Returns:
            Dictionary with benchmark results
        """

        # Add a simple listener
        def dummy_listener(*args: Any, **kwargs: Any) -> None:
            pass

        emitter.on(event_name)(dummy_listener)

        # Run benchmark
        start_time = time.time()
        for _ in range(iterations):
            emitter.emit(event_name)
        total_time = time.time() - start_time

        # Clean up
        emitter.remove_listener(event_name, dummy_listener)

        return {
            "iterations": iterations,
            "total_time": total_time,
            "average_time": total_time / iterations,
            "events_per_second": iterations / total_time,
        }
