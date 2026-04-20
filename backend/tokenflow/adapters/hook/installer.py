"""Detect and install the tokenflow-hook in Claude Code's settings.json."""
from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

HOOK_COMMAND = "tokenflow-hook"
HOOK_EVENTS: tuple[str, ...] = ("SessionStart", "PostToolUse", "SessionEnd", "UserPromptSubmit")


def claude_settings_path() -> Path:
    """Locate Claude Code's user settings.json, platform-aware."""
    # macOS/Linux
    xdg = os.environ.get("CLAUDE_CONFIG_DIR")
    if xdg:
        return Path(xdg) / "settings.json"
    return (Path.home() / ".claude" / "settings.json").expanduser()


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.warning("settings.json at %s is not valid JSON - preserving as-is", path)
        return {}
    return data if isinstance(data, dict) else {}


def _has_our_hook(hooks_for_event: list[dict[str, Any]]) -> bool:
    for bucket in hooks_for_event:
        for h in bucket.get("hooks", []) or []:
            if h.get("type") == "command" and HOOK_COMMAND in str(h.get("command", "")):
                return True
    return False


def detect_hook(settings_path: Path | None = None) -> dict[str, Any]:
    path = settings_path or claude_settings_path()
    data = _load(path)
    hooks = data.get("hooks", {}) if isinstance(data.get("hooks"), dict) else {}

    installed: list[str] = []
    missing: list[str] = []
    for ev in HOOK_EVENTS:
        buckets = hooks.get(ev, []) if isinstance(hooks.get(ev), list) else []
        if _has_our_hook(buckets):
            installed.append(ev)
        else:
            missing.append(ev)

    if not installed and missing == list(HOOK_EVENTS):
        status = "not_installed"
    elif installed and missing:
        status = "partial"
    elif not missing:
        status = "installed"
    else:
        status = "unknown"

    return {
        "status": status,
        "settings_path": str(path),
        "installed_events": installed,
        "missing_events": missing,
        "settings_exists": path.exists(),
    }


def install_hook(settings_path: Path | None = None, dry_run: bool = False) -> dict[str, Any]:
    """Add tokenflow-hook to SessionStart/PostToolUse/SessionEnd/UserPromptSubmit hook lists.

    Existing blocks are preserved; a timestamped .bak is created alongside settings.json.
    """
    path = settings_path or claude_settings_path()
    data = _load(path) if path.exists() else {}
    hooks = data.get("hooks", {})
    if not isinstance(hooks, dict):
        hooks = {}

    added: list[str] = []
    for ev in HOOK_EVENTS:
        buckets = hooks.get(ev, [])
        if not isinstance(buckets, list):
            buckets = []
        if _has_our_hook(buckets):
            continue
        buckets.append({
            "matcher": "" if ev != "PostToolUse" else ".*",
            "hooks": [{"type": "command", "command": HOOK_COMMAND}],
        })
        hooks[ev] = buckets
        added.append(ev)

    data["hooks"] = hooks

    if dry_run:
        return {"dry_run": True, "added_events": added, "settings_path": str(path), "preview": data}

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        # Millisecond + random suffix prevents same-second backup collisions
        # that would silently overwrite the only good pre-install snapshot.
        import secrets

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        bak = path.with_suffix(path.suffix + f".bak.{stamp}_{secrets.token_hex(3)}")
        if not bak.exists():
            shutil.copy2(path, bak)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"dry_run": False, "added_events": added, "settings_path": str(path)}
