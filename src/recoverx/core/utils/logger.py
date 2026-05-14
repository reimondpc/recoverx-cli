"""Logging configuration for RecoverX.

Provides multi-level logging with forensic support:
  - Console output via Rich (INFO level, formatted for readability)
  - File output (DEBUG level, structured with timestamps)
  - FORENSIC level for audit-grade recovery trails
"""

import logging
from pathlib import Path

from rich.logging import RichHandler

FORENSIC_LEVEL_NUM = 15
FORENSIC_NAME = "FORENSIC"

logging.addLevelName(FORENSIC_LEVEL_NUM, FORENSIC_NAME)


def forensic(self: logging.Logger, message: str, *args, **kwargs) -> None:
    if self.isEnabledFor(FORENSIC_LEVEL_NUM):
        self._log(FORENSIC_LEVEL_NUM, message, args, **kwargs)


logging.Logger.forensic = forensic  # type: ignore[attr-defined]


class ForensicLogger(logging.Logger):
    def forensic(self, message: str, *args, **kwargs) -> None:
        if self.isEnabledFor(FORENSIC_LEVEL_NUM):
            self._log(FORENSIC_LEVEL_NUM, message, args, **kwargs)


def setup_logger(
    name: str = "recoverx",
    log_dir: str = "logs",
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG,
) -> logging.Logger:
    """Configure and return a logger instance.

    Creates both a Rich console handler and a structured file handler.
    Supports standard levels plus FORENSIC (level 15) for audit trails.
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
    console_handler.setLevel(console_level)
    logger.addHandler(console_handler)

    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    file_handler = logging.FileHandler(
        log_path / "recoverx.log",
        encoding="utf-8",
    )
    file_handler.setLevel(file_level)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(threadName)-12s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
