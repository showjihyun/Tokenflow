"""Waste-pattern detectors. Pure domain logic, no I/O.

Each detector takes a typed record of session-scoped data and returns a list of
:class:`WasteCandidate` dicts; the adapter layer persists/dedupes them.
"""
from __future__ import annotations

import difflib
import hashlib
import html
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal

WasteKind = Literal["big-file-load", "repeat-question", "wrong-model", "context-bloat", "tool-loop"]
Severity = Literal["high", "med", "low"]


@dataclass(frozen=True)
class MessageRow:
    session_id: str
    ts: datetime
    role: str
    model: str | None
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    content_preview: str | None


@dataclass(frozen=True)
class EventRow:
    session_id: str
    ts: datetime
    event_type: str
    tool_name: str | None
    file_path: str | None
    error_hash: str | None


@dataclass(frozen=True)
class WasteCandidate:
    kind: WasteKind
    severity: Severity
    session_id: str
    title: str
    meta: str
    body_html: str
    save_tokens: int
    save_usd: float
    sessions: int
    context: dict[str, Any]
    # Deterministic natural key for dedup — hash of kind + session + discriminator
    dedup_key: str


def _stable_id(kind: str, session_id: str, discriminator: str) -> str:
    raw = f"{kind}|{session_id}|{discriminator}".encode()
    return hashlib.sha256(raw).hexdigest()[:24]


# ---------- big-file-load ----------

def detect_big_file_load(
    events: list[EventRow], price_per_1k_sonnet: float = 0.003
) -> list[WasteCandidate]:
    """A file read 2+ times within the same session, each time more than roughly 10 KB of tokens."""
    per_session_file: dict[tuple[str, str], int] = {}
    for e in events:
        if e.event_type != "PostToolUse" or e.tool_name != "Read" or not e.file_path:
            continue
        per_session_file[(e.session_id, e.file_path)] = per_session_file.get((e.session_id, e.file_path), 0) + 1

    out: list[WasteCandidate] = []
    for (sid, fp), n in per_session_file.items():
        if n < 2:
            continue
        # heuristic: each full read ~= 10k tokens
        est_tokens = n * 10_000
        sev: Severity = "high" if est_tokens >= 100_000 else "med" if est_tokens >= 30_000 else "low"
        fp_safe = html.escape(fp)
        out.append(
            WasteCandidate(
                kind="big-file-load",
                severity=sev,
                session_id=sid,
                title="큰 파일이 반복해서 컨텍스트에 로드됨",
                meta=f"{fp} · {n}회",
                body_html=(
                    f"<code>{fp_safe}</code> 파일이 같은 세션에서 {n}회 전체 로드되었습니다."
                    " grep/글롭으로 부분 검색하면 토큰을 크게 줄일 수 있습니다."
                ),
                save_tokens=est_tokens - 10_000,
                save_usd=round((est_tokens - 10_000) / 1000.0 * price_per_1k_sonnet, 2),
                sessions=1,
                context={"file_path": fp, "count": n},
                dedup_key=_stable_id("big-file-load", sid, fp),
            )
        )
    return out


# ---------- repeat-question ----------

def detect_repeat_question(
    messages: list[MessageRow], *, window_minutes: int = 30, similarity: float = 0.9, min_count: int = 3
) -> list[WasteCandidate]:
    """User messages with pairwise similarity >= threshold, 3+ times inside the window.

    Fast path: length-ratio reject + SequenceMatcher.quick_ratio() prefilter cut the
    expensive ratio() call by roughly 5-10x on realistic traffic.
    """
    users = [m for m in messages if m.role == "user" and m.content_preview]
    users.sort(key=lambda m: m.ts)
    window = timedelta(minutes=window_minutes)
    reject_ratio = 1 - similarity

    groups: list[list[MessageRow]] = []
    for m in users:
        mp = (m.content_preview or "").lower()
        m_len = len(mp)
        attached = False
        for g in groups:
            if (m.ts - g[0].ts) > window:
                continue
            gp = (g[0].content_preview or "").lower()
            g_len = len(gp)
            # Cheap length-ratio reject: if texts differ by more than (1 - threshold)
            # of their max length, they can't hit the threshold. Skip SequenceMatcher.
            max_len = max(m_len, g_len)
            if max_len and abs(m_len - g_len) / max_len > reject_ratio:
                continue
            sm = difflib.SequenceMatcher(a=mp, b=gp)
            # quick_ratio is an upper bound; only pay for ratio() when it can pass.
            if sm.quick_ratio() < similarity:
                continue
            if sm.ratio() >= similarity:
                g.append(m)
                attached = True
                break
        if not attached:
            groups.append([m])

    out: list[WasteCandidate] = []
    for g in groups:
        if len(g) < min_count:
            continue
        sid = g[0].session_id
        sev: Severity = "high" if len(g) >= 5 else "med"
        out.append(
            WasteCandidate(
                kind="repeat-question",
                severity=sev,
                session_id=sid,
                title="반복 질문 패턴 감지",
                meta=f"유사도 ≥{int(similarity*100)}% · {len(g)}회 in {window_minutes}m",
                body_html=(
                    f"최근 {window_minutes}분 동안 유사한 질문이 {len(g)}번 반복되었습니다."
                    " CLAUDE.md 에 답변을 저장하고 참조하세요."
                ),
                save_tokens=(len(g) - 1) * 3_000,
                save_usd=round((len(g) - 1) * 3_000 / 1000.0 * 0.015, 2),
                sessions=1,
                context={"preview": (g[0].content_preview or "")[:120], "count": len(g)},
                dedup_key=_stable_id("repeat-question", sid, (g[0].content_preview or "")[:64]),
            )
        )
    return out


def _similar(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(a=a.lower(), b=b.lower()).ratio()


# ---------- wrong-model ----------

def detect_wrong_model(messages: list[MessageRow]) -> list[WasteCandidate]:
    """Opus used for work small enough that Sonnet/Haiku would do. Per-message fire."""
    out: list[WasteCandidate] = []
    for m in messages:
        if m.role != "assistant" or not m.model:
            continue
        if "opus" not in m.model.lower():
            continue
        # SPEC §5.2 heuristic: simple if output_tokens < 2000 AND input_tokens < 5000
        if m.output_tokens >= 2000 or m.input_tokens >= 5000:
            continue
        save_tokens = m.input_tokens + m.output_tokens
        save_usd = round((m.input_tokens * 12.0 + m.output_tokens * 60.0) / 1_000_000.0, 2)
        sev: Severity = "med" if save_usd >= 0.05 else "low"
        out.append(
            WasteCandidate(
                kind="wrong-model",
                severity=sev,
                session_id=m.session_id,
                title="단순 작업에 Opus 사용",
                meta=f"{m.model} · in {m.input_tokens} / out {m.output_tokens}",
                body_html=(
                    "이 호출은 입력과 출력이 모두 작아 Sonnet 또는 Haiku 로 충분합니다."
                    " 자동 라우팅 규칙을 제안할 수 있어요."
                ),
                save_tokens=save_tokens,
                save_usd=save_usd,
                sessions=1,
                context={"model": m.model, "in": m.input_tokens, "out": m.output_tokens},
                dedup_key=_stable_id("wrong-model", m.session_id, f"{m.ts.isoformat()}|{m.input_tokens}|{m.output_tokens}"),
            )
        )
    return out


# ---------- context-bloat ----------

def detect_context_bloat(
    messages: list[MessageRow], *, context_window: int = 200_000, threshold: float = 0.7
) -> list[WasteCandidate]:
    """Session whose peak (input + cache_read) crosses threshold of the context window."""
    per_sid_peak: dict[str, int] = {}
    for m in messages:
        if m.role != "assistant":
            continue
        used = m.input_tokens + m.cache_read_tokens
        if used > per_sid_peak.get(m.session_id, 0):
            per_sid_peak[m.session_id] = used

    out: list[WasteCandidate] = []
    for sid, peak in per_sid_peak.items():
        pct = peak / max(1, context_window)
        if pct < threshold:
            continue
        sev: Severity = "high" if pct >= 0.85 else "med"
        out.append(
            WasteCandidate(
                kind="context-bloat",
                severity=sev,
                session_id=sid,
                title="컨텍스트 윈도우 포화",
                meta=f"peak {int(pct*100)}% · {peak:,} / {context_window:,} tokens",
                body_html=(
                    "세션의 컨텍스트 사용률이 권장치(70%) 를 초과했습니다."
                    " <code>/compact</code> 실행 또는 새 세션 분기를 추천합니다."
                ),
                save_tokens=max(0, peak - int(context_window * threshold)),
                save_usd=0.0,
                sessions=1,
                context={"peak": peak, "pct": round(pct, 2)},
                dedup_key=_stable_id("context-bloat", sid, str(peak // 1000)),
            )
        )
    return out


# ---------- tool-loop ----------

def detect_tool_loop(events: list[EventRow], *, min_count: int = 5) -> list[WasteCandidate]:
    """Same tool_name repeated N+ times in a session (proxy for failing loop without tool_response data)."""
    counts: dict[tuple[str, str], int] = {}
    for e in events:
        if e.event_type != "PostToolUse" or not e.tool_name:
            continue
        key = (e.session_id, e.tool_name)
        counts[key] = counts.get(key, 0) + 1

    out: list[WasteCandidate] = []
    for (sid, tool), n in counts.items():
        if n < min_count:
            continue
        sev: Severity = "med" if n >= 10 else "low"
        tool_safe = html.escape(tool)
        out.append(
            WasteCandidate(
                kind="tool-loop",
                severity=sev,
                session_id=sid,
                title=f"툴 반복 호출 감지: {tool}",
                meta=f"{tool} · {n} 회 호출",
                body_html=(
                    f"<code>{tool_safe}</code> 이 {n}회 반복 호출되었습니다."
                    " 동일 에러 루프인지 확인하고 CLAUDE.md 에 에러 핸들링 규칙을 추가하세요."
                ),
                save_tokens=(n - min_count) * 500,
                save_usd=0.0,
                sessions=1,
                context={"tool": tool, "count": n},
                dedup_key=_stable_id("tool-loop", sid, tool),
            )
        )
    return out


# ---------- opus overuse (budget-wide, not per-session) ----------

# SPEC §11 #15 — Opus 월 비용 점유율 임계값.
# 15% 권장 한계, 25% 알림 발사.
OPUS_OVERUSE_WARN_SHARE: float = 0.15
OPUS_OVERUSE_ALERT_SHARE: float = 0.25


def evaluate_opus_overuse(
    *,
    opus_cost_usd: float,
    total_cost_usd: float,
    warn_share: float = OPUS_OVERUSE_WARN_SHARE,
    alert_share: float = OPUS_OVERUSE_ALERT_SHARE,
) -> tuple[float, Severity] | None:
    """Return ``(share, severity)`` when Opus cost share crosses the warn
    threshold, otherwise ``None``.

    Pure policy function: caller is responsible for aggregating costs over
    the observation window (typically the current calendar month) and
    feeding totals in. The separation keeps the detector testable without
    touching DuckDB and lets the scheduler/publisher decide *when* to run
    this check (SessionEnd, hourly sweep, SSE event publisher — tracked in
    §12 ``System notifications``).
    """
    if total_cost_usd <= 0 or opus_cost_usd < 0:
        return None
    share = opus_cost_usd / total_cost_usd
    if share >= alert_share:
        return share, "high"
    if share >= warn_share:
        return share, "med"
    return None
