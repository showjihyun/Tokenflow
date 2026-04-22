from __future__ import annotations

import json
import threading
import time
from datetime import UTC, datetime, timedelta
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


def test_inactive_session_is_marked_ended() -> None:
    repo = _init_db()
    old = datetime.now(tz=UTC) - timedelta(minutes=30)
    repo.upsert_session_started("stale_s1", "proj", "claude-sonnet-4-6", old)
    ended = repo.mark_inactive_sessions_ended(cutoff=datetime.now(tz=UTC) - timedelta(minutes=15))
    assert ended == 1
    assert repo.get_current_session() is None


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
            "_received_at": datetime.now(tz=UTC).timestamp(),
        }) + "\n",
        encoding="utf-8",
    )
    repo = _init_db()
    events: list[dict[str, object]] = []
    tailer = EventTailer(repo, publish=events.append, poll_interval=0.05)

    task = threading.Thread(target=tailer.run, name="test-event-tailer")
    task.start()
    time.sleep(0.3)
    tailer.stop()
    task.join(timeout=2)
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

    task = threading.Thread(target=tailer.run, name="test-transcript-tailer")
    task.start()
    time.sleep(0.3)
    tailer.stop()
    task.join(timeout=2)
    # Check a message landed and session totals updated
    session = repo.get_current_session()
    assert session is not None
    assert session["tokens"]["output"] == 800
    assert session["costUSD"] > 0


def _drain_events(published: list[dict[str, object]], kind: str) -> list[dict[str, object]]:
    return [e for e in published if e.get("kind") == kind]


def test_tailer_publishes_opus_warn_at_fifteen_percent(tmp_path: Path) -> None:
    """SPEC §11 #15 — Opus share in the warn band (15-25%) publishes severity='med'.

    Seeds one Sonnet session (85% of today's cost) + one Opus session (15%).
    The tailer's ``_publish_usage_notifications`` should fire a single
    ``opus-overuse`` event with ``severity='med'``.
    """
    repo = _init_db()
    published: list[dict[str, object]] = []
    tailer = TranscriptTailer(repo, publish=published.append)
    now = datetime.now(tz=UTC)

    repo.upsert_session_started("s_sonnet", "p", "claude-sonnet-4-6", now)
    repo.upsert_session_started("s_opus", "p", "claude-opus-4-7", now)
    repo.insert_message(
        "m_sonnet", "s_sonnet", now, "assistant", "claude-sonnet-4-6",
        1000, 1000, 0, 0, 0.85, "s", False,
    )
    repo.insert_message(
        "m_opus", "s_opus", now, "assistant", "claude-opus-4-7",
        500, 500, 0, 0, 0.15, "o", False,
    )

    tailer._publish_usage_notifications("s_opus")
    hits = _drain_events(published, "opus-overuse")
    assert len(hits) == 1, f"expected one opus-overuse event, got {hits}"
    assert hits[0]["severity"] == "med"
    share = hits[0]["share"]
    assert isinstance(share, (int, float)) and 0.14 <= float(share) <= 0.16


def test_tailer_publishes_opus_alert_at_thirty_percent(tmp_path: Path) -> None:
    """Opus share ≥25% triggers the alert band: severity='high'.

    Shares above the warn threshold must emit ``severity='high'`` and dedup
    per month-key so a single burst doesn't fire repeatedly on every poll
    (same bucket → no second event on a repeat call).
    """
    repo = _init_db()
    published: list[dict[str, object]] = []
    tailer = TranscriptTailer(repo, publish=published.append)
    now = datetime.now(tz=UTC)

    repo.upsert_session_started("s_sonnet", "p", "claude-sonnet-4-6", now)
    repo.upsert_session_started("s_opus", "p", "claude-opus-4-7", now)
    repo.insert_message(
        "m_sonnet", "s_sonnet", now, "assistant", "claude-sonnet-4-6",
        1000, 1000, 0, 0, 0.70, "s", False,
    )
    repo.insert_message(
        "m_opus", "s_opus", now, "assistant", "claude-opus-4-7",
        1000, 1000, 0, 0, 0.30, "o", False,
    )

    tailer._publish_usage_notifications("s_opus")
    hits = _drain_events(published, "opus-overuse")
    assert len(hits) == 1
    assert hits[0]["severity"] == "high"

    # Second call in the same month+severity bucket must not re-fire.
    tailer._publish_usage_notifications("s_opus")
    assert len(_drain_events(published, "opus-overuse")) == 1


def test_tailer_publishes_budget_exceeded_when_hard_block_and_over_budget(tmp_path: Path) -> None:
    """SPEC §11 #4 — hard_block=true + spent≥budget emits a distinct
    ``budget-exceeded`` event beside the threshold pings, so the UI can
    render a red banner. No proxy blocking here; that's v2.
    """
    repo = _init_db()
    published: list[dict[str, object]] = []
    tailer = TranscriptTailer(repo, publish=published.append)
    now = datetime.now(tz=UTC)

    repo.patch_config(monthly_budget_usd=10.0, hard_block=True, alert_thresholds_pct="[50,75,90]")
    repo.upsert_session_started("s_over", "p", "claude-opus-4-7", now)
    # Spend $12 — 120% of the $10 monthly budget.
    repo.insert_message(
        "m_over", "s_over", now, "assistant", "claude-opus-4-7",
        5000, 2000, 0, 0, 12.0, "o", False,
    )

    tailer._publish_usage_notifications("s_over")

    exceeded = _drain_events(published, "budget-exceeded")
    assert len(exceeded) == 1
    assert exceeded[0]["hard_block"] is True
    spent = exceeded[0]["spent"]
    assert isinstance(spent, (int, float)) and float(spent) >= 10.0
    # Threshold pings also fire alongside (50/75/90 all crossed at 120%).
    thresholds = _drain_events(published, "budget-threshold")
    thresh_pcts: set[int] = set()
    for e in thresholds:
        pct = e.get("threshold_pct")
        if isinstance(pct, (int, float)):
            thresh_pcts.add(int(pct))
    assert thresh_pcts >= {50, 75, 90}

    # Dedup: repeat call in the same month must not re-emit exceeded.
    tailer._publish_usage_notifications("s_over")
    assert len(_drain_events(published, "budget-exceeded")) == 1


def test_tailer_skips_budget_exceeded_when_hard_block_false(tmp_path: Path) -> None:
    """Over-budget without ``hard_block`` fires threshold pings only —
    the red-banner ``budget-exceeded`` event is gated on the toggle.
    """
    repo = _init_db()
    published: list[dict[str, object]] = []
    tailer = TranscriptTailer(repo, publish=published.append)
    now = datetime.now(tz=UTC)

    repo.patch_config(monthly_budget_usd=10.0, hard_block=False, alert_thresholds_pct="[50,75,90]")
    repo.upsert_session_started("s_soft", "p", "claude-sonnet-4-6", now)
    repo.insert_message(
        "m_soft", "s_soft", now, "assistant", "claude-sonnet-4-6",
        1000, 1000, 0, 0, 12.0, "s", False,
    )

    tailer._publish_usage_notifications("s_soft")

    assert _drain_events(published, "budget-exceeded") == []
    assert _drain_events(published, "budget-threshold") != []
