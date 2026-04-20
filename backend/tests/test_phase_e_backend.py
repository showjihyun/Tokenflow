from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from tokenflow.adapters.persistence.repository import Repository
from tokenflow.adapters.web.app import create_app
from tokenflow.domain.waste import (
    OPUS_OVERUSE_ALERT_SHARE,
    OPUS_OVERUSE_WARN_SHARE,
    EventRow,
    MessageRow,
    detect_big_file_load,
    detect_context_bloat,
    detect_repeat_question,
    detect_tool_loop,
    detect_wrong_model,
    evaluate_opus_overuse,
)
from tokenflow.use_cases.detect_waste import run_detectors

# ---------- Pure domain detectors ----------

def test_detect_big_file_load_fires_on_repeat_reads() -> None:
    now = datetime.now(tz=UTC)
    events = [
        EventRow("s1", now, "PostToolUse", "Read", "/a/big.ts", None),
        EventRow("s1", now, "PostToolUse", "Read", "/a/big.ts", None),
        EventRow("s1", now, "PostToolUse", "Read", "/a/small.ts", None),  # only once — ignored
    ]
    out = detect_big_file_load(events)
    assert len(out) == 1
    assert out[0].kind == "big-file-load"
    assert "big.ts" in out[0].meta


def test_detect_repeat_question_fires_above_threshold() -> None:
    base = datetime(2026, 4, 20, 10, tzinfo=UTC)
    q = "explain the authentication middleware in detail please"
    msgs = [
        MessageRow("s1", base, "user", None, 0, 0, 0, q),
        MessageRow("s1", base + timedelta(minutes=2), "user", None, 0, 0, 0, q + "?"),
        MessageRow("s1", base + timedelta(minutes=5), "user", None, 0, 0, 0, q + "."),
    ]
    out = detect_repeat_question(msgs, similarity=0.85)
    assert len(out) == 1
    assert out[0].kind == "repeat-question"


def test_detect_repeat_question_ignores_below_threshold() -> None:
    base = datetime(2026, 4, 20, 10, tzinfo=UTC)
    msgs = [
        MessageRow("s1", base, "user", None, 0, 0, 0, "foo"),
        MessageRow("s1", base + timedelta(minutes=60), "user", None, 0, 0, 0, "foo again"),  # outside window
    ]
    assert detect_repeat_question(msgs) == []


def test_detect_wrong_model_flags_opus_small_output() -> None:
    now = datetime.now(tz=UTC)
    msgs = [
        MessageRow("s1", now, "assistant", "claude-opus-4", 100, 300, 0, "short reply"),
        MessageRow("s1", now, "assistant", "claude-sonnet-4-6", 100, 300, 0, "sonnet is fine"),
    ]
    out = detect_wrong_model(msgs)
    assert len(out) == 1
    assert "opus" in (out[0].context.get("model") or "").lower()


def test_detect_context_bloat_above_70pct() -> None:
    now = datetime.now(tz=UTC)
    msgs = [
        MessageRow("s1", now, "assistant", "claude-sonnet-4-6", 150_000, 0, 0, None),
    ]
    out = detect_context_bloat(msgs)
    assert len(out) == 1
    assert out[0].severity in ("med", "high")


def test_detect_tool_loop_fires_on_5_repeats() -> None:
    now = datetime.now(tz=UTC)
    events = [EventRow("s1", now, "PostToolUse", "Read", None, None) for _ in range(5)]
    out = detect_tool_loop(events)
    assert len(out) == 1
    assert out[0].kind == "tool-loop"


# ---------- Opus overuse (SPEC §11 #15) ----------

def test_evaluate_opus_overuse_below_warn_returns_none() -> None:
    # 14% share → no signal
    assert evaluate_opus_overuse(opus_cost_usd=14.0, total_cost_usd=100.0) is None


def test_evaluate_opus_overuse_between_warn_and_alert_is_med() -> None:
    # 20% share → warn band
    result = evaluate_opus_overuse(opus_cost_usd=20.0, total_cost_usd=100.0)
    assert result is not None
    share, severity = result
    assert severity == "med"
    assert OPUS_OVERUSE_WARN_SHARE <= share < OPUS_OVERUSE_ALERT_SHARE


def test_evaluate_opus_overuse_at_or_above_alert_is_high() -> None:
    # 25% share boundary → high
    result = evaluate_opus_overuse(opus_cost_usd=25.0, total_cost_usd=100.0)
    assert result is not None
    _, severity = result
    assert severity == "high"


def test_evaluate_opus_overuse_guards_zero_total() -> None:
    # Don't divide by zero when no cost has accrued yet (e.g. fresh install).
    assert evaluate_opus_overuse(opus_cost_usd=0.0, total_cost_usd=0.0) is None
    assert evaluate_opus_overuse(opus_cost_usd=5.0, total_cost_usd=0.0) is None


def test_evaluate_opus_overuse_rejects_negative_opus_cost() -> None:
    # Defensive: negative cost is an upstream bug; refuse to emit a signal.
    assert evaluate_opus_overuse(opus_cost_usd=-1.0, total_cost_usd=100.0) is None


# ---------- Persistence + end-to-end dedup ----------

def test_run_detectors_persists_and_dedups() -> None:
    with TestClient(create_app()) as c:
        repo: Repository = c.app.state.repo  # type: ignore[attr-defined]
        now = datetime.now(tz=UTC)
        repo.upsert_session_started("s1", "proj", "claude-sonnet-4-6", now - timedelta(minutes=30))
        # Seed two assistant messages with opus-small-output → should trigger wrong-model twice
        for i, toks in enumerate([(100, 300), (200, 400)]):
            repo.insert_message(
                message_id=f"m{i}", session_id="s1", ts=now - timedelta(minutes=20 - i),
                role="assistant", model="claude-opus-4",
                input_tokens=toks[0], output_tokens=toks[1],
                cache_creation_tokens=0, cache_read_tokens=0, cost_usd=0.01,
                content_preview="brief fix",
            )
        new_ids = run_detectors(repo, session_id="s1")
        assert len(new_ids) == 2

        # Re-running must not insert dupes
        new_ids2 = run_detectors(repo, session_id="s1")
        assert new_ids2 == []


# ---------- HTTP routes ----------

def test_wastes_list_empty() -> None:
    with TestClient(create_app()) as c:
        assert c.get("/api/wastes").json() == []


def test_wastes_dismiss_flow() -> None:
    with TestClient(create_app()) as c:
        repo: Repository = c.app.state.repo  # type: ignore[attr-defined]
        now = datetime.now(tz=UTC)
        repo.upsert_session_started("s1", "demo", "claude-sonnet-4-6", now)
        repo.insert_waste_pattern(
            id="w1", kind="wrong-model", severity="med", title="t", meta="m",
            body_html="b", save_tokens=100, save_usd=0.01, sessions=1,
            session_id="s1", context="{}", detected_at=now,
        )
        assert len(c.get("/api/wastes").json()) == 1

        r = c.post("/api/wastes/w1/dismiss")
        assert r.status_code == 200
        assert c.get("/api/wastes").json() == []
        assert len(c.get("/api/wastes?status=dismissed").json()) == 1


def test_wastes_apply_wrong_model_creates_rule() -> None:
    with TestClient(create_app()) as c:
        repo: Repository = c.app.state.repo  # type: ignore[attr-defined]
        now = datetime.now(tz=UTC)
        repo.insert_waste_pattern(
            id="w2", kind="wrong-model", severity="med", title="t", meta="m",
            body_html="b", save_tokens=100, save_usd=0.01, sessions=1,
            session_id="s1", context="{}", detected_at=now,
        )
        r = c.post("/api/wastes/w2/apply")
        assert r.status_code == 200
        body = r.json()
        assert body["outcome"] == "routing-rule-added"
        rules = c.get("/api/settings/routing-rules").json()
        assert len(rules) == 1
        assert rules[0]["target_model"] == "claude-haiku-4-5"


def test_wastes_scan_fires_on_seeded_data() -> None:
    with TestClient(create_app()) as c:
        repo: Repository = c.app.state.repo  # type: ignore[attr-defined]
        now = datetime.now(tz=UTC)
        repo.upsert_session_started("s1", "demo", "claude-sonnet-4-6", now)
        repo.insert_message(
            message_id="m1", session_id="s1", ts=now,
            role="assistant", model="claude-opus-4",
            input_tokens=100, output_tokens=300,
            cache_creation_tokens=0, cache_read_tokens=0, cost_usd=0.02,
            content_preview="fix a typo",
        )
        r = c.post("/api/wastes/scan?session_id=s1")
        assert r.status_code == 200
        wastes = c.get("/api/wastes").json()
        kinds = {w["kind"] for w in wastes}
        assert "wrong-model" in kinds


def test_coach_threads_crud() -> None:
    with TestClient(create_app()) as c:
        assert c.get("/api/coach/threads").json() == []
        r = c.post("/api/coach/threads", json={"title": "first"})
        assert r.status_code == 200
        thread_id = r.json()["id"]
        threads = c.get("/api/coach/threads").json()
        assert len(threads) == 1
        # No API key configured → POST message should 400
        r = c.post(f"/api/coach/threads/{thread_id}/messages", json={"content": "hi"})
        assert r.status_code == 400
        assert "API key" in r.json()["detail"] or "anthropic" in r.json()["detail"].lower()


def test_better_prompt_static_mode() -> None:
    with TestClient(create_app()) as c:
        repo: Repository = c.app.state.repo  # type: ignore[attr-defined]
        now = datetime.now(tz=UTC)
        repo.upsert_session_started("s1", "demo", "claude-sonnet-4-6", now)
        repo.insert_message(
            message_id="m0", session_id="s1", ts=now,
            role="user", model=None, input_tokens=0, output_tokens=0,
            cache_creation_tokens=0, cache_read_tokens=0, cost_usd=0.0,
            content_preview="show me the schema",
        )
        r = c.post("/api/sessions/s1/messages/0/better-prompt?mode=static&waste_reason=big-file-load")
        assert r.status_code == 200
        body = r.json()
        assert body["mode"] == "static"
        assert "grep" in body["suggested_text"].lower()

        # second call is cached (same response)
        r2 = c.post("/api/sessions/s1/messages/0/better-prompt?mode=static&waste_reason=big-file-load")
        assert r2.status_code == 200
        assert r2.json()["cached"] is True


def test_sessions_replay_and_list() -> None:
    with TestClient(create_app()) as c:
        repo: Repository = c.app.state.repo  # type: ignore[attr-defined]
        now = datetime.now(tz=UTC)
        repo.upsert_session_started("s1", "p", "claude-sonnet-4-6", now - timedelta(minutes=20))
        for i in range(3):
            repo.insert_message(
                message_id=f"m{i}", session_id="s1",
                ts=now - timedelta(minutes=15 - i),
                role="user" if i % 2 == 0 else "assistant",
                model="claude-sonnet-4-6" if i % 2 else None,
                input_tokens=100 * i, output_tokens=200 * i,
                cache_creation_tokens=0, cache_read_tokens=0, cost_usd=0.001 * i,
                content_preview=f"message {i}",
            )
        repo.insert_message(
            message_id="paused-m", session_id="s1",
            ts=now - timedelta(minutes=10),
            role="assistant",
            model="claude-sonnet-4-6",
            input_tokens=999, output_tokens=999,
            cache_creation_tokens=0, cache_read_tokens=0, cost_usd=9.99,
            content_preview="paused message",
            paused=True,
        )
        sessions = c.get("/api/sessions").json()
        assert len(sessions) == 1
        assert sessions[0]["messages"] == 3
        assert sessions[0]["tokens"] == sum((100 * i) + (200 * i) for i in range(3))

        replay = c.get("/api/sessions/s1/replay").json()
        assert len(replay["events"]) == 3
        assert replay["summary"]["messages"] == 3
        assert all(e["id"] != "paused-m" for e in replay["events"])

        replay_with_paused = c.get("/api/sessions/s1/replay?include_paused=true").json()
        assert len(replay_with_paused["events"]) == 4
        assert any(e["id"] == "paused-m" for e in replay_with_paused["events"])

        exported = c.get("/api/sessions/s1/export").json()
        assert len(exported["events"]) == 3
        exported_with_paused = c.get("/api/sessions/s1/export?include_paused=true").json()
        assert len(exported_with_paused["events"]) == 4


def test_routing_rules_crud() -> None:
    with TestClient(create_app()) as c:
        # create
        r = c.post("/api/settings/routing-rules", json={
            "condition_pattern": "simple edits", "target_model": "claude-haiku-4-5",
            "enabled": True, "priority": 50,
        })
        assert r.status_code == 200
        rule_id = r.json()["id"]

        rules = c.get("/api/settings/routing-rules").json()
        assert len(rules) == 1

        # update
        r = c.patch(f"/api/settings/routing-rules/{rule_id}", json={
            "condition_pattern": "simple edits v2", "target_model": "claude-haiku-4-5",
            "enabled": False, "priority": 60,
        })
        assert r.status_code == 200
        assert r.json()["enabled"] is False

        # delete
        r = c.delete(f"/api/settings/routing-rules/{rule_id}")
        assert r.status_code == 200
        assert c.get("/api/settings/routing-rules").json() == []


def test_notifications_default_and_patch() -> None:
    with TestClient(create_app()) as c:
        prefs = c.get("/api/settings/notifications").json()
        assert len(prefs) == 8
        assert {p["key"] for p in prefs} >= {"api_error", "budget_threshold"}
        waste_high = next(p for p in prefs if p["key"] == "waste_high")
        assert waste_high["enabled"] is True

        r = c.patch("/api/settings/notifications/waste_high", json={"enabled": False})
        assert r.status_code == 200
        assert r.json()["enabled"] is False


def test_notification_events_persist_and_clear() -> None:
    with TestClient(create_app()) as c:
        c.patch("/api/settings/notifications/waste_high", json={"enabled": True, "channel": "in_app"})
        r = c.post(
            "/api/notifications",
            json={
                "id": "waste_high:evt-1",
                "prefKey": "waste_high",
                "title": "Waste detected",
                "body": "high context-bloat",
            },
        )
        assert r.status_code == 200
        assert r.json()["stored"] is True

        duplicate = c.post(
            "/api/notifications",
            json={
                "id": "waste_high:evt-1",
                "prefKey": "waste_high",
                "title": "Waste detected",
                "body": "high context-bloat",
            },
        )
        assert duplicate.status_code == 200
        assert duplicate.json()["stored"] is False

        events = c.get("/api/notifications").json()
        assert len(events) == 1
        assert events[0]["prefKey"] == "waste_high"
        assert events[0]["title"] == "Waste detected"
        assert events[0]["readAt"] is None
        assert c.get("/api/notifications/unread-count").json()["count"] == 1

        read = c.patch("/api/notifications/waste_high%3Aevt-1/read")
        assert read.status_code == 200
        assert read.json()["readAt"] is not None
        assert c.get("/api/notifications").json()[0]["readAt"] is not None
        assert c.get("/api/notifications/unread-count").json()["count"] == 0

        c.post(
            "/api/notifications",
            json={
                "id": "waste_high:evt-2",
                "prefKey": "waste_high",
                "title": "Waste detected",
                "body": "repeat-question",
            },
        )
        read_all = c.post("/api/notifications/read-all")
        assert read_all.status_code == 200
        assert read_all.json()["updated"] == 1
        assert all(e["readAt"] is not None for e in c.get("/api/notifications").json())
        assert c.get("/api/notifications/unread-count").json()["count"] == 0

        cleared = c.delete("/api/notifications")
        assert cleared.status_code == 200
        assert cleared.json()["deleted"] == 2
        assert c.get("/api/notifications").json() == []
