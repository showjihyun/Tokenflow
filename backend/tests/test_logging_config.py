"""Tests for structured logging shape + env overrides."""

from __future__ import annotations

import io
import json
import logging
import logging.config
from contextlib import redirect_stderr
from typing import Any

import pytest

from tokenflow.lib import logging as tf_logging
from tokenflow.lib.logging import _JsonFormatter, build_log_config, request_id_var


def _emit_once(config: dict[str, Any], name: str, message: str) -> str:
    buf = io.StringIO()
    with redirect_stderr(buf):
        logging.config.dictConfig(config)
        logger = logging.getLogger(name)
        logger.info(message)
        for h in logger.handlers + logging.getLogger().handlers:
            h.flush()
    return buf.getvalue()


def test_prod_config_emits_json_lines() -> None:
    config = build_log_config(dev=False)
    out = _emit_once(config, "tokenflow.tests.prod", "hello world")
    line = out.strip().splitlines()[-1]
    payload = json.loads(line)
    assert payload["msg"] == "hello world"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "tokenflow.tests.prod"
    assert "request_id" in payload
    assert "ts" in payload


def test_dev_config_emits_plain_text_not_json() -> None:
    config = build_log_config(dev=True)
    out = _emit_once(config, "tokenflow.tests.dev", "hi there")
    line = out.strip().splitlines()[-1]
    # Dev format starts with the padded level name — JSON would start with `{`.
    assert line.startswith("INFO")
    assert "tokenflow.tests.dev" in line
    assert "hi there" in line
    with pytest.raises(json.JSONDecodeError):
        json.loads(line)


def test_json_format_includes_current_request_id() -> None:
    config = build_log_config(dev=False)
    token = request_id_var.set("req-xyz-42")
    try:
        out = _emit_once(config, "tokenflow.tests.req", "with rid")
    finally:
        request_id_var.reset(token)
    payload = json.loads(out.strip().splitlines()[-1])
    assert payload["request_id"] == "req-xyz-42"


def test_log_level_env_controls_verbosity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TOKENFLOW_LOG_LEVEL", "WARNING")
    config = build_log_config(dev=False)
    assert config["loggers"][""]["level"] == "WARNING"


def test_log_level_env_unknown_falls_back_to_info(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TOKENFLOW_LOG_LEVEL", "LOUD")
    config = build_log_config(dev=False)
    assert config["loggers"][""]["level"] == "INFO"


def test_json_formatter_escapes_newlines_in_messages() -> None:
    """A message containing a newline must still produce exactly one JSON line —
    otherwise log aggregators would split one event into two records."""
    record = logging.LogRecord(
        name="x", level=logging.INFO, pathname="", lineno=0,
        msg="line1\nline2", args=(), exc_info=None,
    )
    record.request_id = ""
    out = _JsonFormatter().format(record)
    assert "\n" not in out, "formatter must not emit raw newlines"
    payload = json.loads(out)
    assert payload["msg"] == "line1\nline2"


def test_current_request_id_default_is_empty_string() -> None:
    assert tf_logging.current_request_id() == ""
