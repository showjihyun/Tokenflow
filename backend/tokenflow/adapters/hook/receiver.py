from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from tokenflow.adapters.persistence import paths


def append_event(raw: str) -> None:
    """Atomically append one event line to events.ndjson. Creates parent dir if missing."""
    ndjson = paths.events_ndjson_path()
    ndjson.parent.mkdir(parents=True, exist_ok=True)
    received_at = time.time()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = {"raw": raw, "parse_error": True}
    if isinstance(payload, dict):
        payload.setdefault("_received_at", received_at)
    line = json.dumps(payload, ensure_ascii=False)
    with ndjson.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def main() -> int:
    try:
        raw = sys.stdin.read()
    except KeyboardInterrupt:
        return 1
    if not raw.strip():
        return 0
    try:
        append_event(raw)
    except Exception as e:
        fallback_log = Path(paths.tokenflow_dir()) / "logs" / "hook_errors.log"
        fallback_log.parent.mkdir(parents=True, exist_ok=True)
        with fallback_log.open("a", encoding="utf-8") as f:
            f.write(f"{time.time()} {type(e).__name__}: {e}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
