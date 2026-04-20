from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from tokenflow.adapters.persistence.repository import Repository
from tokenflow.adapters.transcript.parser import compute_cost, parse_line

logger = logging.getLogger(__name__)


class TranscriptTailer:
    """Watches a dynamic set of transcript JSONL files and appends parsed messages to the DB.

    The set of active transcripts is driven by hook events; ``update_sources`` refreshes it.
    Poll-based (not watchdog) — simpler and adequate for Phase C.
    """

    def __init__(
        self,
        repo: Repository,
        publish: Callable[[dict[str, object]], None] | None = None,
        is_paused: Callable[[], bool] | None = None,
        poll_interval: float = 1.5,
    ):
        self.repo = repo
        self.publish = publish or (lambda _e: None)
        self.is_paused = is_paused or (lambda: False)
        self.poll_interval = poll_interval
        self._stop = asyncio.Event()
        self._notified: set[str] = set()
        # path -> session_id
        self._sources: dict[str, str] = {}

    def stop(self) -> None:
        self._stop.set()

    def set_source(self, path: str, session_id: str) -> None:
        if not path:
            return
        self._sources[path] = session_id

    def drop_source(self, path: str) -> None:
        self._sources.pop(path, None)

    async def run(self) -> None:
        logger.info("TranscriptTailer: running")
        while not self._stop.is_set():
            self._refresh_sources_from_db()
            for path, sid in list(self._sources.items()):
                try:
                    self._process_file(Path(path), sid)
                except FileNotFoundError:
                    self.drop_source(path)
                except Exception:
                    logger.exception("TranscriptTailer: error processing %s", path)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.poll_interval)
            except TimeoutError:
                continue

    def _refresh_sources_from_db(self) -> None:
        # pick up transcripts discovered via hook events
        for path, sid in self.repo.active_transcript_paths():
            if path and path not in self._sources:
                self._sources[path] = sid

    def _process_file(self, path: Path, session_id: str) -> None:
        if not path.exists():
            raise FileNotFoundError(str(path))
        offset = self.repo.get_transcript_offset(str(path))
        size = path.stat().st_size
        if size < offset:
            offset = 0
        if size == offset:
            return
        with path.open("rb") as f:
            f.seek(offset)
            chunk = f.read(size - offset)
        last_nl = chunk.rfind(b"\n")
        if last_nl == -1:
            return
        processed = chunk[: last_nl + 1]
        new_offset = offset + len(processed)
        new_rows = 0
        for raw_line in processed.decode("utf-8", errors="replace").splitlines():
            if not raw_line.strip():
                continue
            parsed = parse_line(raw_line, session_id_hint=session_id)
            if not parsed:
                continue
            paused = self.is_paused()
            pricing = self.repo.pricing_for(parsed["model"] or "claude-sonnet-4-6") if parsed["model"] else None
            cost = compute_cost(
                pricing,
                parsed["input_tokens"],
                parsed["output_tokens"],
                parsed["cache_creation_tokens"],
                parsed["cache_read_tokens"],
            )
            inserted = self.repo.insert_message(
                parsed["message_id"],
                parsed["session_id"],
                parsed["ts"],
                parsed["role"],
                parsed["model"],
                parsed["input_tokens"],
                parsed["output_tokens"],
                parsed["cache_creation_tokens"],
                parsed["cache_read_tokens"],
                cost,
                parsed["content_preview"],
                paused,
            )
            if inserted:
                new_rows += 1
                if paused:
                    continue
                self.publish({
                    "kind": "message",
                    "session_id": parsed["session_id"],
                    "role": parsed["role"],
                    "model": parsed["model"],
                    "tokens_in": parsed["input_tokens"],
                    "tokens_out": parsed["output_tokens"],
                    "cost_usd": round(cost, 4),
                    "ts": parsed["ts"].isoformat(),
                })

        if new_rows:
            self.repo.update_session_totals_from_messages(session_id)
            self._publish_usage_notifications(session_id)
        # Only write offset when it actually moved — prevents idle DB churn every poll.
        if new_offset != offset:
            self.repo.set_transcript_offset(str(path), session_id, new_offset)

    def _publish_usage_notifications(self, session_id: str) -> None:
        current = self.repo.get_current_session()
        if current and current.get("id") == session_id:
            context_window = int(current.get("contextWindow") or 0)
            context_used = int(current.get("contextUsed") or 0)
            saturation = (context_used / context_window) if context_window > 0 else 0
            key = f"context:{session_id}:85"
            if saturation >= 0.85 and key not in self._notified:
                self._notified.add(key)
                self.publish({
                    "kind": "context-saturation",
                    "session_id": session_id,
                    "pct": round(saturation, 4),
                    "context_used": context_used,
                    "context_window": context_window,
                })

        budget = self.repo.budget()
        month = float(budget.get("month") or 0)
        spent = float(budget.get("spent") or 0)
        if month > 0:
            pct = (spent / month) * 100
            thresholds = _budget_thresholds(self.repo.get_config().get("alert_thresholds_pct"))
            month_key = datetime.now(tz=UTC).strftime("%Y-%m")
            for threshold in thresholds:
                key = f"budget:{month_key}:{threshold}"
                if pct >= threshold and key not in self._notified:
                    self._notified.add(key)
                    self.publish({
                        "kind": "budget-threshold",
                        "threshold_pct": threshold,
                        "spent": round(spent, 2),
                        "budget": round(month, 2),
                    })

        opus_share = float(budget.get("opusShare") or 0)
        day_key = datetime.now(tz=UTC).strftime("%Y-%m-%d")
        key = f"opus:{day_key}:25"
        if opus_share >= 0.25 and key not in self._notified:
            self._notified.add(key)
            self.publish({
                "kind": "opus-overuse",
                "share": round(opus_share, 4),
            })


def _budget_thresholds(raw: object) -> list[int]:
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = [50, 75, 90]
    else:
        parsed = raw
    if not isinstance(parsed, list):
        return [50, 75, 90]
    return sorted({int(v) for v in parsed if isinstance(v, int | float) and v > 0})
