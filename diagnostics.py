from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from app_paths import diagnostic_log_path


LOGGER_NAME = "eft_task_assistant"


def log_path() -> Path:
    return diagnostic_log_path()


def configure_logging() -> Path:
    path = log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    if not any(getattr(handler, "baseFilename", None) == str(path) for handler in logger.handlers):
        handler = RotatingFileHandler(path, maxBytes=5_000_000, backupCount=5, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    return path


def log_event(event: str, *, level: int = logging.INFO, **fields: Any) -> None:
    configure_logging()
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "event": event,
        **fields,
    }
    logging.getLogger(LOGGER_NAME).log(
        level,
        json.dumps(entry, ensure_ascii=False, separators=(",", ":"), default=str),
    )
