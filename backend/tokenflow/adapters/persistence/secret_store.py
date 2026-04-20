"""Secret storage — plaintext file at ~/.tokenflow/secret.json with 0600 perms (best-effort)."""
from __future__ import annotations

import contextlib
import json
import logging
import os
import stat

from tokenflow.adapters.persistence import paths

logger = logging.getLogger(__name__)


def get_api_key() -> str | None:
    """Return the stored API key, or None if nothing configured."""
    secret = paths.secret_path()
    if not secret.exists():
        return None
    try:
        payload = json.loads(secret.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    key = payload.get("anthropic_api_key")
    return key if isinstance(key, str) and key.strip() else None


def set_api_key(key: str) -> None:
    """Store the key in ~/.tokenflow/secret.json with 0600 perms (best-effort)."""
    key = key.strip()
    if not key:
        raise ValueError("empty API key")
    secret = paths.secret_path()
    secret.parent.mkdir(parents=True, exist_ok=True)
    secret.write_text(json.dumps({"anthropic_api_key": key}), encoding="utf-8")
    with contextlib.suppress(OSError):
        os.chmod(secret, stat.S_IRUSR | stat.S_IWUSR)


def delete_api_key() -> None:
    """Remove the stored key file, if present."""
    secret = paths.secret_path()
    if secret.exists():
        with contextlib.suppress(OSError):
            secret.unlink()


def status() -> dict[str, object]:
    """Report presence + validity without leaking the key value."""
    key = get_api_key()
    if key is None:
        return {"configured": False, "valid": False}
    return {"configured": True, "valid": True}
