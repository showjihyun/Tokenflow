from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tokenflow.adapters.persistence import paths
from tokenflow.adapters.persistence.repository import Repository

logger = logging.getLogger(__name__)


_SLUG_CACHE: dict[str, str] = {}
_SLUG_MAX_DEPTH = 12


def _project_slug_from_cwd(cwd: str | None) -> str:
    if not cwd:
        return "unknown"
    cached = _SLUG_CACHE.get(cwd)
    if cached is not None:
        return cached
    try:
        p = Path(cwd)
        git_root = p
        depth = 0
        # Bound the walk — deep paths on slow network mounts (UNC) can otherwise stall
        # the asyncio loop while EventTailer handles a single event.
        while git_root != git_root.parent and depth < _SLUG_MAX_DEPTH:
            if (git_root / ".git").exists():
                slug = git_root.name
                _SLUG_CACHE[cwd] = slug
                return slug
            git_root = git_root.parent
            depth += 1
        slug = p.name or "unknown"
        _SLUG_CACHE[cwd] = slug
        return slug
    except Exception:
        _SLUG_CACHE[cwd] = "unknown"
        return "unknown"


def _parse_ts(raw: Any) -> datetime:
    if isinstance(raw, (int, float)):
        return datetime.fromtimestamp(float(raw), tz=UTC)
    if isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(tz=UTC)


def _hash_payload(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def apply_event(repo: Repository, payload: dict[str, Any]) -> str | None:
    """Apply one parsed event to the repository. Returns event_id if inserted, None if duplicate."""
    event_name = payload.get("hook_event_name") or payload.get("event") or "unknown"
    session_id = payload.get("session_id") or "unknown"
    ts = _parse_ts(payload.get("_received_at") or payload.get("timestamp"))
    raw_hash = _hash_payload(payload)
    event_id = raw_hash[:16]

    # Session lifecycle
    if event_name == "SessionStart":
        project_slug = _project_slug_from_cwd(payload.get("cwd"))
        model = payload.get("model") or "claude-sonnet-4-6"
        repo.upsert_session_started(session_id, project_slug, model, ts)
    elif event_name == "SessionEnd":
        repo.mark_session_ended(session_id, ts)
    elif event_name in ("PreCompact", "PostCompact"):
        if event_name == "PostCompact":
            repo.mark_session_compacted(session_id, ts)

    # Always record the event (dedup by raw_hash unique index)
    inserted = repo.insert_event(event_id, session_id, event_name, ts, payload, raw_hash)
    return event_id if inserted else None


class EventTailer:
    """Tails events.ndjson, persists to repository, notifies subscribers.

    Uses byte-offset tracking so restarts don't replay events.
    """

    def __init__(
        self,
        repo: Repository,
        publish: Callable[[dict[str, Any]], None] | None = None,
        poll_interval: float = 1.0,
    ):
        self.repo = repo
        self.publish = publish or (lambda _e: None)
        self.poll_interval = poll_interval
        self._stop = asyncio.Event()
        self._ndjson_path = paths.events_ndjson_path()

    def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        self._ndjson_path.parent.mkdir(parents=True, exist_ok=True)
        self._ndjson_path.touch(exist_ok=True)
        offset = self.repo.get_hook_offset()
        logger.info("EventTailer: starting at offset %d (%s)", offset, self._ndjson_path)

        while not self._stop.is_set():
            try:
                offset = await self._process_new(offset)
            except Exception:
                logger.exception("EventTailer: unexpected error")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.poll_interval)
            except TimeoutError:
                continue

    async def _process_new(self, offset: int) -> int:
        try:
            size = self._ndjson_path.stat().st_size
        except FileNotFoundError:
            return offset
        rotated = size < offset
        if rotated:
            logger.warning("EventTailer: ndjson shrank (rotation) — resetting offset")
            offset = 0
        if size == offset:
            return offset
        with self._ndjson_path.open("rb") as f:
            f.seek(offset)
            chunk = f.read(size - offset)
        # only process whole lines — last partial line stays for next poll
        last_nl = chunk.rfind(b"\n")
        if last_nl == -1:
            return offset
        processed = chunk[: last_nl + 1]
        new_offset = offset + len(processed)

        for raw_line in processed.decode("utf-8", errors="replace").splitlines():
            if not raw_line.strip():
                continue
            try:
                payload = json.loads(raw_line)
            except json.JSONDecodeError:
                logger.debug("EventTailer: malformed line, skipping")
                continue
            if not isinstance(payload, dict):
                continue
            try:
                evt_id = apply_event(self.repo, payload)
                # Suppress SSE publish when reprocessing after rotation —
                # callers don't want the ticker to replay ancient events.
                if evt_id and not rotated:
                    self.publish({
                        "hook_event_name": payload.get("hook_event_name"),
                        "session_id": payload.get("session_id"),
                        "transcript_path": payload.get("transcript_path"),
                        "tool_name": payload.get("tool_name"),
                    })
            except Exception:
                logger.exception("EventTailer: apply_event failed")

        self.repo.set_hook_offset(new_offset)
        return new_offset
