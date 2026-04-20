from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tokenflow.adapters.hook import receiver
from tokenflow.adapters.hook.event_tailer import EventTailer, apply_event
from tokenflow.adapters.persistence import migrations, paths
from tokenflow.adapters.persistence.repository import Repository
from tokenflow.adapters.transcript.parser import compute_cost, parse_line
from tokenflow.adapters.transcript.tailer import TranscriptTailer


def _init_db() -> Repository:
    migrations.run_migrations()
    return Repository()


def test_hook_receiver_appends_ndjson() -> None:
    receiver.append_event(json.dumps({"hook_event_name": "SessionStart", "session_id": "s1"}))
    receiver.append_event(json.dumps({"hook_event_name": "PostToolUse", "session_id": "s1", "tool_name": "Read"}))
    lines = paths.events_ndjson_path().read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["session_id"] == "s1"
    assert "_received_at" in json.loads(lines[0])


def test_apply_event_creates_session_and_event() -> None:
    repo = _init_db()
    ts = datetime.now(tz=UTC)
    apply_event(repo, {
        "hook_event_name": "SessionStart",
        "session_id": "s1",
        "cwd": "/tmp/test-project",
        "_received_at": ts.timestamp(),
        "model": "claude-sonnet-4-6",
    })
    session = repo.get_current_session()
    assert session is not None
    assert session["id"] == "s1"
    assert session["project"] == "test-project"


def test_apply_event_deduplicates() -> None:
    repo = _init_db()
    payload = {"hook_event_name": "PostToolUse", "session_id": "s1", "tool_name": "Read", "_received_at": 1.0}
    first = apply_event(repo, payload)
    second = apply_event(repo, payload)
    assert first is not None
    assert second is None  # duplicate


def test_parse_line_extracts_usage() -> None:
    raw = json.dumps({
        "type": "assistant",
        "session_id": "s1",
        "timestamp": "2026-04-20T10:00:00Z",
        "message": {
            "model": "claude-sonnet-4-6",
            "usage": {
                "input_tokens": 100,
                "output_tokens": 250,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 1000,
            },
            "content": [{"type": "text", "text": "Hello, here is my answer."}],
        },
    })
    parsed = parse_line(raw)
    assert parsed is not None
    assert parsed["session_id"] == "s1"
    assert parsed["role"] == "assistant"
    assert parsed["input_tokens"] == 100
    assert parsed["output_tokens"] == 250
    assert parsed["cache_read_tokens"] == 1000
    assert parsed["content_preview"].startswith("Hello")


def test_parse_line_skips_unknown_shape() -> None:
    assert parse_line('{"foo": "bar"}') is None
    assert parse_line("not json") is None


def test_compute_cost() -> None:
    # Sonnet pricing: $3/Mtok in, $15/Mtok out
    price = (3.0, 15.0, 3.75, 0.30)
    cost = compute_cost(price, 1_000_000, 0, 0, 0)
    assert cost == pytest.approx(3.0)
    cost = compute_cost(price, 0, 1_000_000, 0, 0)
    assert cost == pytest.approx(15.0)
    cost = compute_cost(None, 1_000_000, 1_000_000, 0, 0)
    assert cost == 0.0


def test_event_tailer_processes_ndjson(tmp_path: Path) -> None:
    ndjson = paths.events_ndjson_path()
    ndjson.parent.mkdir(parents=True, exist_ok=True)
    ndjson.write_text(
        json.dumps({
            "hook_event_name": "SessionStart",
            "session_id": "s_tailer",
            "cwd": str(tmp_path),
            "model": "claude-sonnet-4-6",
            "_received_at": 1.0,
        }) + "\n",
        encoding="utf-8",
    )
    repo = _init_db()
    events: list[dict[str, object]] = []
    tailer = EventTailer(repo, publish=events.append, poll_interval=0.05)

    async def drive() -> None:
        task = asyncio.create_task(tailer.run())
        await asyncio.sleep(0.3)
        tailer.stop()
        await task

    asyncio.run(drive())
    assert repo.get_current_session() is not None
    assert any(e.get("hook_event_name") == "SessionStart" for e in events)


def test_transcript_tailer_reads_jsonl(tmp_path: Path) -> None:
    repo = _init_db()
    tpath = tmp_path / "transcript.jsonl"
    tpath.write_text(
        json.dumps({
            "type": "assistant",
            "session_id": "s_tx",
            "timestamp": "2026-04-20T10:00:00Z",
            "message": {
                "model": "claude-sonnet-4-6",
                "usage": {"input_tokens": 200, "output_tokens": 800,
                          "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0},
                "content": [{"type": "text", "text": "done"}],
            },
        }) + "\n",
        encoding="utf-8",
    )
    repo.upsert_session_started("s_tx", "demo-proj", "claude-sonnet-4-6", datetime.now(tz=UTC))

    tailer = TranscriptTailer(repo, poll_interval=0.05)
    tailer.set_source(str(tpath), "s_tx")

    async def drive() -> None:
        task = asyncio.create_task(tailer.run())
        await asyncio.sleep(0.3)
        tailer.stop()
        await task

    asyncio.run(drive())
    # Check a message landed and session totals updated
    session = repo.get_current_session()
    assert session is not None
    assert session["tokens"]["output"] == 800
    assert session["costUSD"] > 0
