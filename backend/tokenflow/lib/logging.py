"""Structured logging for Token Flow.

Two output shapes:
- **prod**: one JSON object per line on stderr (machine-parseable, ingests
  cleanly into any log aggregator). Chosen when `--dev` is NOT passed to
  `tokenflow serve`.
- **dev**: human-readable `LEVEL NAME [request_id] message` — terminal-friendly
  during local development.

Every record carries the current-request's `request_id` (empty for background
threads like the event/transcript tailers). Level is configurable via
`TOKENFLOW_LOG_LEVEL` (default `INFO`).

The config returned by :func:`build_log_config` is uvicorn-compatible so that
uvicorn.access and uvicorn.error flow through the same formatter — one dial
controls the whole app's log format.
"""

from __future__ import annotations

import json
import logging
import os
from contextvars import ContextVar
from typing import Any

# Empty string, not None, so format strings don't render the literal "None".
# Background threads (tailers, retention jobs) see the default.
request_id_var: ContextVar[str] = ContextVar("tokenflow_request_id", default="")


def current_request_id() -> str:
    return request_id_var.get()


class _RequestIdFilter(logging.Filter):
    """Inject ``request_id`` onto every LogRecord."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = current_request_id()
        return True


class _JsonFormatter(logging.Formatter):
    """One-line JSON record. Includes exception info if present."""

    _STANDARD = frozenset(
        {
            "name",
            "msg",
            "args",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "exc_info",
            "exc_text",
            "stack_info",
            "lineno",
            "funcName",
            "created",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
            "message",
            "asctime",
            "taskName",
            "request_id",
        }
    )

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": getattr(record, "request_id", ""),
        }
        # Surface any ad-hoc keys a caller attached via `logger.info(..., extra={...})`
        # without leaking the logging module's internal attributes.
        for key, value in record.__dict__.items():
            if key in self._STANDARD or key.startswith("_"):
                continue
            payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


def _resolve_level() -> str:
    """TOKENFLOW_LOG_LEVEL, normalized. Unknown → INFO (with a one-time warning)."""
    raw = os.environ.get("TOKENFLOW_LOG_LEVEL", "INFO").upper()
    if raw not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        logging.getLogger(__name__).warning(
            "unknown TOKENFLOW_LOG_LEVEL=%r, falling back to INFO", raw
        )
        return "INFO"
    return raw


def build_log_config(*, dev: bool) -> dict[str, Any]:
    """Return a uvicorn-compatible logging dict.

    ``dev=True`` → human-readable single-line output (no JSON noise locally).
    ``dev=False`` → JSON lines, one per record (prod / CI / container).

    Applied to the root logger and uvicorn's own ``uvicorn``/``uvicorn.access``
    /``uvicorn.error`` loggers so every request and every background emit share
    one shape.
    """
    level = _resolve_level()
    formatter_key = "dev" if dev else "json"
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "request_id": {"()": "tokenflow.lib.logging._RequestIdFilter"},
        },
        "formatters": {
            "json": {"()": "tokenflow.lib.logging._JsonFormatter"},
            "dev": {
                "format": "%(levelname)-7s %(name)s [%(request_id)s] %(message)s",
            },
        },
        "handlers": {
            "default": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
                "formatter": formatter_key,
                "filters": ["request_id"],
            },
        },
        "loggers": {
            # Everything shares one handler — including uvicorn — so the format
            # gate (JSON vs dev) covers request access logs too.
            "": {"handlers": ["default"], "level": level, "propagate": False},
            "uvicorn": {"handlers": ["default"], "level": level, "propagate": False},
            "uvicorn.error": {"handlers": ["default"], "level": level, "propagate": False},
            "uvicorn.access": {"handlers": ["default"], "level": level, "propagate": False},
        },
    }


def configure_logging(*, dev: bool) -> None:
    """Apply :func:`build_log_config` to the running process."""
    import logging.config

    logging.config.dictConfig(build_log_config(dev=dev))
