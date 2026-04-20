"""Tolerant parser for Claude Code transcript JSONL lines.

We don't assume an exact schema — only try known shapes and skip what we don't understand.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


def _parse_ts(raw: Any) -> datetime:
    if isinstance(raw, (int, float)):
        return datetime.fromtimestamp(float(raw), tz=UTC)
    if isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(tz=UTC)


def _first_text_chunk(content: Any) -> str:
    """Content in Anthropic messages is a list of blocks: [{type:'text', text:'...'}, ...]."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text" and isinstance(block.get("text"), str):
                    return str(block["text"])
                if isinstance(block.get("input"), dict) and isinstance(block["input"].get("query"), str):
                    return str(block["input"]["query"])
    return ""


def parse_line(
    raw_line: str, *, session_id_hint: str | None = None
) -> dict[str, Any] | None:
    """Parse one JSONL line. Return a message record dict, or None to skip."""
    try:
        obj = json.loads(raw_line)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None

    # Look for a message sub-object; fall back to the root.
    nested = obj.get("message")
    msg: dict[str, Any] = nested if isinstance(nested, dict) else obj

    role = obj.get("type") or obj.get("role") or msg.get("role")
    if role not in ("user", "assistant", "system", "tool"):
        return None
    role = "assistant" if role == "assistant" else str(role)

    ts = _parse_ts(obj.get("timestamp") or obj.get("ts") or msg.get("timestamp"))
    model = msg.get("model") or obj.get("model")

    raw_usage = msg.get("usage") or obj.get("usage") or {}
    usage: dict[str, Any] = raw_usage if isinstance(raw_usage, dict) else {}
    input_tokens = int(usage.get("input_tokens", 0) or 0)
    output_tokens = int(usage.get("output_tokens", 0) or 0)
    cache_creation = int(usage.get("cache_creation_input_tokens", 0) or 0)
    cache_read = int(usage.get("cache_read_input_tokens", 0) or 0)

    content = msg.get("content") if isinstance(msg, dict) else None
    text = _first_text_chunk(content)
    preview = text[:200] if text else None

    sid = obj.get("session_id") or session_id_hint or "unknown"

    # Stable dedup id: hash of session + ts + role + usage + first 64 chars of text.
    key = f"{sid}|{ts.isoformat()}|{role}|{input_tokens}|{output_tokens}|{(text or '')[:64]}"
    message_id = hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]

    return {
        "message_id": message_id,
        "session_id": sid,
        "ts": ts,
        "role": role,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_creation_tokens": cache_creation,
        "cache_read_tokens": cache_read,
        "content_preview": preview,
    }


def compute_cost(
    pricing: tuple[float, float, float, float] | None,
    input_tokens: int,
    output_tokens: int,
    cache_creation: int,
    cache_read: int,
) -> float:
    if pricing is None:
        return 0.0
    inp, out, cw, cr = pricing
    return (
        (input_tokens / 1_000_000.0) * inp
        + (output_tokens / 1_000_000.0) * out
        + (cache_creation / 1_000_000.0) * cw
        + (cache_read / 1_000_000.0) * cr
    )
