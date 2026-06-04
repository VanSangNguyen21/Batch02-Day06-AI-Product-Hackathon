"""JSONL logging support for backend runtime logs."""

import json
import logging
import os
import traceback
from datetime import datetime, timezone
from typing import Any, Dict


class JsonlLogHandler(logging.Handler):
    """Append structured log records to a JSONL file."""

    def __init__(self, path: str, level: int = logging.INFO):
        super().__init__(level=level)
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "a", encoding="utf-8").close()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            payload = self._record_to_payload(record)
            with open(self.path, "a", encoding="utf-8") as log_file:
                log_file.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception:
            self.handleError(record)

    def _record_to_payload(self, record: logging.LogRecord) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "process": record.process,
            "thread": record.threadName,
        }

        if record.exc_info:
            payload["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else "",
                "traceback": "".join(traceback.format_exception(*record.exc_info)),
            }

        if record.stack_info:
            payload["stack"] = record.stack_info

        return payload


def install_jsonl_logging(data_dir: str) -> None:
    """Install app-wide JSONL handlers once."""
    root_logger = logging.getLogger()
    app_log_path = os.path.join(data_dir, "app_logs.jsonl")
    error_log_path = os.path.join(data_dir, "error_logs.jsonl")

    existing_paths = {
        getattr(handler, "path", None)
        for handler in root_logger.handlers
        if isinstance(handler, JsonlLogHandler)
    }

    if app_log_path not in existing_paths:
        root_logger.addHandler(JsonlLogHandler(app_log_path, level=logging.INFO))
    if error_log_path not in existing_paths:
        root_logger.addHandler(JsonlLogHandler(error_log_path, level=logging.ERROR))
