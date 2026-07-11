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
    """

    def prepare(self, record: LogRecord) -> LogRecord:
        return record


def _setup_logging_queue(*handlers: Handler) -> QueueHandler:
    """Creates a LocalQueueHandler and starts a QueueListener."""
    queue: Queue[LogRecord] = Queue()
    queue_handler = LocalQueueHandler(queue)

    listener = QueueListener(queue, *handlers, respect_handler_level=True)
    listener.start()

    return queue_handler


def has_level_handler(logger: Logger) -> bool:
    """Checks if the logger already has an appropriate handler."""
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
    """Creates a high-performance, configurable logger for sillo.

    Args:
        logger_name (str): The name of the logger.
        log_level (int): The logging level (DEBUG, INFO, ERROR, etc.).
        log_file (Optional[str]): Path to a log file for file-based logging.
        max_bytes (int): Max size of each log file before rotating.
        backup_count (int): Number of backup log files to keep.

    Returns:
        Logger: A configured logger instance.
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
