"""Secret storage — OS keyring when available, plaintext file as fallback.

Keyring has a Windows Credential Manager backend, macOS Keychain backend, and
Secret Service / KWallet on Linux. On headless Linux in CI where no backend
exists, we transparently fall back to the legacy secret.json file.

Migration: `get_api_key()` reads keyring first; if empty but a legacy secret.json
exists, it migrates once (copies into keyring, then deletes the file) and returns.
"""
from __future__ import annotations

import contextlib
import json
import logging
import os
import stat
from typing import Literal

from tokenflow.adapters.persistence import paths

logger = logging.getLogger(__name__)

SERVICE = "tokenflow"
USERNAME = "anthropic_api_key"


def _keyring_available() -> bool:
    try:
        import keyring
        import keyring.errors
    except ImportError:
        return False
    backend = keyring.get_keyring()
    # keyring.backends.fail.Keyring is the "no backend found" sentinel.
    return "fail" not in type(backend).__module__.lower()


def _migrate_legacy() -> str | None:
    """If a plaintext secret.json exists, move its key into the keyring, then delete."""
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
    if not isinstance(key, str) or not key.strip():
        return None
    # Copy to keyring, then drop the plaintext file.
    if _keyring_available():
        import keyring

        try:
            keyring.set_password(SERVICE, USERNAME, key)
            secret.unlink(missing_ok=True)
            logger.info("migrated API key from secret.json to OS keyring")
        except Exception:
            logger.exception("keyring migration failed; leaving secret.json in place")
            return key
    return key


def get_api_key() -> str | None:
    """Return the stored API key, or None if nothing configured.

    Resolution order: keyring → legacy secret.json (also auto-migrates).
    """
    if _keyring_available():
        import keyring

        try:
            value = keyring.get_password(SERVICE, USERNAME)
            if value:
                return value
        except Exception:
            logger.exception("keyring read failed; falling back to legacy file")
        # Maybe the user used a previous plaintext version — migrate & return.
        legacy = _migrate_legacy()
        if legacy:
            return legacy
        return None
    # No keyring backend — use the legacy file.
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


def set_api_key(key: str) -> Literal["keyring", "file"]:
    """Store the key. Returns which backend was used so callers can surface it."""
    key = key.strip()
    if not key:
        raise ValueError("empty API key")
    if _keyring_available():
        import keyring

        keyring.set_password(SERVICE, USERNAME, key)
        # Remove any lingering plaintext file so the legacy path doesn't override.
        with contextlib.suppress(OSError):
            paths.secret_path().unlink(missing_ok=True)
        return "keyring"
    # Fallback: plaintext file with 0600 best-effort.
    secret = paths.secret_path()
    secret.parent.mkdir(parents=True, exist_ok=True)
    secret.write_text(json.dumps({"anthropic_api_key": key}), encoding="utf-8")
    with contextlib.suppress(OSError):
        os.chmod(secret, stat.S_IRUSR | stat.S_IWUSR)
    return "file"


def delete_api_key() -> None:
    """Remove the key from whichever backend holds it."""
    if _keyring_available():
        import keyring

        with contextlib.suppress(Exception):
            keyring.delete_password(SERVICE, USERNAME)
    secret = paths.secret_path()
    if secret.exists():
        with contextlib.suppress(OSError):
            secret.unlink()


def status() -> dict[str, object]:
    """Report backend + validity without leaking the key value."""
    backend: str = "keyring" if _keyring_available() else "file"
    key = get_api_key()
    if key is None:
        return {"configured": False, "valid": False, "backend": backend}
    return {"configured": True, "valid": True, "backend": backend}
