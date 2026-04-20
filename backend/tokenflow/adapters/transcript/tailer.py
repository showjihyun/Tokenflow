from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
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
        poll_interval: float = 1.5,
    ):
        self.repo = repo
        self.publish = publish or (lambda _e: None)
        self.poll_interval = poll_interval
        self._stop = asyncio.Event()
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
            )
            if inserted:
                new_rows += 1
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
        self.repo.set_transcript_offset(str(path), session_id, new_offset)
