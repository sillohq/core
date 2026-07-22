from __future__ import annotations

import sys
from logging import (
    DEBUG,
    Formatter,
    Handler,
    Logger,
    LogRecord,
    StreamHandler,
    getLogger,
)
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
from queue import SimpleQueue as Queue
from typing import TYPE_CHECKING, Optional, Tuple

if TYPE_CHECKING:
    pass


class LocalQueueHandler(QueueHandler):
    """Custom QueueHandler to avoid unnecessary record preparation.

    Since we use an in-process queue, there's no need to prepare records,
    reducing logging overhead.

    The standard ``QueueHandler.prepare`` method performs formatting and
    pickling operations designed for cross-process communication. Since
    this handler operates entirely within a single process using an
    in-memory ``SimpleQueue``, those steps are unnecessary overhead.
    This subclass overrides ``prepare`` to return the record unchanged.

    Args:
        queue: The queue instance to which log records are sent. Inherited
            from the parent ``QueueHandler`` class.
    """

    def prepare(self, record: LogRecord) -> LogRecord:
        """Return the log record without any transformation or formatting.

        Overrides the base ``QueueHandler.prepare`` method to skip the
        standard preparation steps (formatting, pickling) that are only
        needed for cross-process queue communication. Since the sillo
        logging queue operates entirely in-process, the record can be
        passed through unchanged for maximum performance.

        Args:
            record: The log record to be enqueued. Contains all logging
                metadata such as level, message, timestamp, and module.

        Returns:
            The same ``LogRecord`` instance, unmodified.
        """
        return record


def _setup_logging_queue(*handlers: Handler) -> QueueHandler:
    """Create a queue-based logging handler with a background listener thread.

    Sets up a high-performance asynchronous logging pipeline by creating a
    ``LocalQueueHandler`` backed by an in-process ``SimpleQueue`` and a
    ``QueueListener`` that dispatches records to the provided handlers on
    a dedicated background thread. This decouples log emission from log
    output, preventing I/O operations from blocking the main event loop.

    The ``QueueListener`` is started immediately and runs for the lifetime
    of the process. It respects each handler's configured log level, so
    records below a handler's threshold are silently dropped.

    Args:
        *handlers: One or more ``Handler`` instances that will receive
            log records from the queue. Typically includes at least a
            ``StreamHandler`` for console output and optionally a
            ``RotatingFileHandler`` for file-based logging.

    Returns:
        A configured ``LocalQueueHandler`` instance that can be added to
        a logger. Log records sent to this handler are enqueued and
        processed asynchronously by the background listener.
    """
    queue: Queue[LogRecord] = Queue()
    queue_handler = LocalQueueHandler(queue)

    listener = QueueListener(queue, *handlers, respect_handler_level=True)
    listener.start()

    return queue_handler


def has_level_handler(logger: Logger) -> bool:
    """Check if the logger already has an appropriate handler configured.

    Walks the logger hierarchy from the given logger up through its parents,
    checking whether any logger in the chain has a handler whose level is
    at or below the logger's effective level. This prevents duplicate handler
    registration when ``create_logger`` is called multiple times with the
    same logger name.

    The traversal stops when a logger with ``propagate`` set to ``False``
    is encountered, since records would not propagate beyond that point.

    Args:
        logger: The logger instance to inspect. The check examines both
            the logger's own handlers and those of its ancestors in the
            logging hierarchy.

    Returns:
        ``True`` if at least one handler with an appropriate level exists
        in the logger chain, ``False`` if no suitable handler is found
        and a new handler should be added.
    """
    level = logger.getEffectiveLevel()
    current_logger: Optional[Logger] = logger

    while current_logger:
        if any(handler.level <= level for handler in current_logger.handlers):
            return True
        if not current_logger.propagate:
            break
        current_logger = current_logger.parent

    return False


def create_logger(
    logger_name: str = "sillo",
    log_level: int = DEBUG,
    log_file: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB per log file
    backup_count: int = 5,
) -> Logger:
    """Create a high-performance, configurable logger for the sillo framework.

    Constructs a logger with a console handler writing to ``stderr`` and
    an optional rotating file handler. Both handlers use a timestamped
    format including the log level and module name. Handlers are wired
    through an in-process queue for asynchronous, non-blocking log output.

    If the logger already has an appropriate handler (as determined by
    ``has_level_handler``), no additional handlers are added, making this
    function safe to call multiple times with the same logger name.

    Args:
        logger_name: The name of the logger to create or retrieve. Defaults
            to ``"sillo"``. Multiple calls with the same name return the
            same underlying logger instance.
        log_level: The minimum severity level for log records. Use standard
            logging constants such as ``DEBUG``, ``INFO``, ``WARNING``,
            ``ERROR``, or ``CRITICAL``. Defaults to ``DEBUG``.
        log_file: Optional file path for a ``RotatingFileHandler``. If
            provided, log records are also written to this file with
            automatic rotation when the file exceeds ``max_bytes``.
        max_bytes: Maximum size in bytes of a single log file before it
            is rotated. Only used when ``log_file`` is specified. Defaults
            to 10 MB.
        backup_count: Number of rotated backup log files to retain. Only
            used when ``log_file`` is specified. Defaults to 5.

    Returns:
        A fully configured ``Logger`` instance ready for use. The logger
        has at least a console handler and optionally a rotating file
        handler, both wired through an asynchronous queue.
    """
    logger = getLogger(logger_name)
    logger.setLevel(log_level)

    console_handler = StreamHandler(sys.stderr)
    console_handler.setFormatter(
        Formatter("[%(asctime)s] %(levelname)s in %(module)s: %(message)s")
    )

    handlers: Tuple[Handler, ...] = (console_handler,)

    if log_file:
        file_handler = RotatingFileHandler(
            log_file, maxBytes=max_bytes, backupCount=backup_count
        )
        file_handler.setFormatter(
            Formatter("[%(asctime)s] %(levelname)s in %(module)s: %(message)s")
        )
        handlers += (file_handler,)

    if not has_level_handler(logger):
        queue_handler = _setup_logging_queue(*handlers)
        logger.addHandler(queue_handler)

    return logger
