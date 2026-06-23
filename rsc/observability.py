from __future__ import annotations

import json
import logging
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOG_SCHEMA_VERSION = "rsc.log.v2"


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "schema_version": LOG_SCHEMA_VERSION,
            "event": getattr(record, "event", record.getMessage()),
            "timestamp": getattr(
                record, "timestamp", datetime.now(timezone.utc).isoformat()
            ),
            "session_id": getattr(record, "session_id", ""),
            "depth": getattr(record, "depth", 0),
            "level": record.levelname,
            "logger": record.name,
        }
        for key, value in getattr(record, "fields", {}).items():
            payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, sort_keys=True)


class DailyJSONFileHandler(logging.Handler):
    def __init__(
        self,
        log_dir: str | Path = "./rsc/logs",
        *,
        prefix: str = "rsc",
        level: int = logging.INFO,
        utc: bool = True,
    ) -> None:
        super().__init__(level)
        self.log_dir = Path(log_dir)
        self.prefix = prefix
        self.utc = utc
        self.setFormatter(JSONFormatter())

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            path = self.log_dir / f"{self.prefix}-{self._date_label()}.jsonl"
            with path.open("a", encoding="utf-8") as handle:
                handle.write(f"{self.format(record)}\n")
        except (OSError, TypeError, ValueError):
            self.handleError(record)

    def _date_label(self) -> str:
        now = datetime.now(timezone.utc) if self.utc else datetime.now().astimezone()
        return now.date().isoformat()


def get_logger(component: str) -> logging.Logger:
    return logging.getLogger(f"rsc.{component}")


def configure_daily_file_logging(
    log_dir: str | Path = "./rsc/logs",
    *,
    level: str | int = logging.INFO,
    logger_name: str = "rsc",
    prefix: str = "rsc",
) -> Path:
    numeric_level = _coerce_log_level(level)
    logger = logging.getLogger(logger_name)
    logger.setLevel(numeric_level)
    logger.propagate = False
    resolved_log_dir = Path(log_dir)
    resolved_log_dir.mkdir(parents=True, exist_ok=True)
    for handler in logger.handlers:
        if (
            isinstance(handler, DailyJSONFileHandler)
            and handler.log_dir == resolved_log_dir
        ):
            handler.setLevel(numeric_level)
            return resolved_log_dir
    logger.addHandler(
        DailyJSONFileHandler(
            resolved_log_dir,
            prefix=prefix,
            level=numeric_level,
        )
    )
    return resolved_log_dir


def text_summary(text: str | None, *, preview_chars: int = 240) -> dict[str, Any]:
    value = text or ""
    preview = value[:preview_chars]
    if len(value) > preview_chars:
        preview = f"{preview}..."
    return {
        "chars": len(value),
        "sha256": stable_hash(value),
        "preview": preview,
        "text": value,
        "line_count": value.count("\n") + (1 if value else 0),
    }


def stable_hash(value: Any) -> str:
    if isinstance(value, str):
        encoded = value.encode("utf-8")
    else:
        encoded = json.dumps(value, default=str, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def model_dump_summary(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        payload = value.model_dump(mode="json")
    else:
        payload = value
    return {
        "sha256": stable_hash(payload),
        "type": value.__class__.__name__,
        "payload": payload,
    }


def _coerce_log_level(level: str | int) -> int:
    if isinstance(level, int):
        return level
    normalized = level.strip().upper()
    value = getattr(logging, normalized, None)
    return value if isinstance(value, int) else logging.INFO


def log_event(
    logger: logging.Logger,
    event: str,
    *,
    session_id: str,
    depth: int,
    level: int = logging.INFO,
    **fields: Any,
) -> None:
    logger.log(
        level,
        event,
        extra={
            "event": event,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
            "depth": depth,
            "fields": fields,
        },
    )
