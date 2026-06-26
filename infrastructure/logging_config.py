"""Application-wide logging setup."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from config.paths import get_logs_dir


LOG_FILE_NAME = "mug.log"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
MAX_LOG_BYTES = 1_000_000
BACKUP_COUNT = 5


def configure_logging(debug: bool = False) -> logging.Logger:
    root_logger = logging.getLogger()
    if getattr(root_logger, "_mug_configured", False):
        return logging.getLogger("mug")

    level = logging.DEBUG if debug else logging.INFO
    root_logger.setLevel(level)

    formatter = logging.Formatter(LOG_FORMAT)
    log_path = get_logs_dir() / LOG_FILE_NAME

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=MAX_LOG_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    root_logger._mug_configured = True  # type: ignore[attr-defined]

    logger = logging.getLogger("mug")
    logger.info("Logging initialized at %s", log_path)
    return logger


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

