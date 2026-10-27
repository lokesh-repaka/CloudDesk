import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, TextIO

# Context variables for per-request and per-workflow tracing
request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
workflow_id_ctx: ContextVar[str | None] = ContextVar("workflow_id", default=None)

STANDARD_LOG_RECORD_ATTRS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
}


def set_request_id(request_id: str | None) -> None:
    """Set the request_id context variable."""
    request_id_ctx.set(request_id)


def get_request_id() -> str | None:
    """Get the active request_id context variable."""
    return request_id_ctx.get()


def set_workflow_id(workflow_id: str | None) -> None:
    """Set the workflow_id context variable."""
    workflow_id_ctx.set(workflow_id)


def get_workflow_id() -> str | None:
    """Get the active workflow_id context variable."""
    return workflow_id_ctx.get()


def clear_context() -> None:
    """Reset both request_id and workflow_id context variables."""
    request_id_ctx.set(None)
    workflow_id_ctx.set(None)


class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON entries including tracing context."""

    def format(self, record: logging.LogRecord) -> str:
        # Base structured fields
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None) or get_request_id(),
            "workflow_id": getattr(record, "workflow_id", None) or get_workflow_id(),
        }

        # Include exception trace if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Include custom extra fields
        for key, value in record.__dict__.items():
            if key not in STANDARD_LOG_RECORD_ATTRS and key not in log_entry:
                log_entry[key] = value

        return json.dumps(log_entry, default=str)


def setup_logging(level: str = "INFO", stream: TextIO | None = None) -> None:
    """Configure root logger to output structured JSON logs."""
    root_logger = logging.getLogger()
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    root_logger.setLevel(numeric_level)

    # Remove existing handlers to prevent duplicate or conflicting log outputs
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(stream or sys.stdout)
    handler.setFormatter(JSONFormatter())
    root_logger.addHandler(handler)
