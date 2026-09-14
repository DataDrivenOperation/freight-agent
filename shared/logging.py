"""Structured logging shared by every agent in the freight platform.

get_logger(name) returns a stdlib Logger that writes JSON lines to
/logs/<name>.log and also prints human-readable output to the console at
the level configured by LOG_LEVEL.
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

_LOGS_DIR = Path("logs")
_CONFIGURED_LOGGERS: set[str] = set()


class _JsonLinesFormatter(logging.Formatter):
    """Formats each log record as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        """Render a log record as a single JSON line."""
        payload = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def get_logger(name: str) -> logging.Logger:
    """Return a configured Logger that writes JSON lines to /logs/<name>.log.

    Also attaches a console handler that prints at the LOG_LEVEL env var
    (default INFO). Safe to call multiple times for the same name; handlers
    are only attached once.

    Args:
        name: Logger name, also used as the log file's base name.

    Returns:
        A stdlib logging.Logger configured for structured output.
    """
    logger = logging.getLogger(name)

    if name in _CONFIGURED_LOGGERS:
        return logger

    _LOGS_DIR.mkdir(parents=True, exist_ok=True)

    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logger.setLevel(level)
    logger.propagate = False

    file_handler = logging.FileHandler(_LOGS_DIR / f"{name}.log")
    file_handler.setFormatter(_JsonLinesFormatter())
    file_handler.setLevel(level)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
    )
    console_handler.setLevel(level)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    _CONFIGURED_LOGGERS.add(name)

    return logger
