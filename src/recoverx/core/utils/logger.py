"""Logging configuration for RecoverX.

Provides dual logging:
  - Console output via Rich (INFO level, formatted for readability)
  - File output (DEBUG level, structured with timestamps)
"""

import logging
from pathlib import Path

from rich.logging import RichHandler


def setup_logger(name: str = "recoverx", log_dir: str = "logs") -> logging.Logger:
    """Configure and return a logger instance.

    Creates both a Rich console handler (stdout, INFO+) and a file handler
    (log file, DEBUG+) for comprehensive logging.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if logger.hasHandlers():
        logger.handlers.clear()

    console_handler = RichHandler(
        rich_tracebacks=True,
        show_time=False,
        show_path=False,
        markup=True,
    )
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)

    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    file_handler = logging.FileHandler(
        log_path / "recoverx.log",
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
