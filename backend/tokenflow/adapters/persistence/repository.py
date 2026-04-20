"""Composed Repository facade — the one class external code imports.

The actual query methods live in mixins split by concern:
- _sessions.py  : session lifecycle + messages + events + pricing
- _wastes.py    : waste patterns + routing rules + notifications
- _coach_replay.py : coach threads/messages + better-prompt cache + session replay
- _analytics.py : KPI/budget/flow/projects/analytics + config + tailer offsets

All mixins inherit from _BaseRepo so `self._q` / `self._exec` are typed uniformly;
Python's MRO dedupes _BaseRepo and runs its __init__ once.
"""
from __future__ import annotations

from tokenflow.adapters.persistence._analytics import _AnalyticsMixin
from tokenflow.adapters.persistence._base import MODEL_COLOR, _BaseRepo, _model_key
from tokenflow.adapters.persistence._coach_replay import _CoachReplayMixin
from tokenflow.adapters.persistence._sessions import _SessionMixin
from tokenflow.adapters.persistence._wastes import _WasteMixin


class Repository(
    _SessionMixin,
    _WasteMixin,
    _CoachReplayMixin,
    _AnalyticsMixin,
    _BaseRepo,
):
    """Thin composition of concern-specific mixins. See module docstring."""


__all__ = ["MODEL_COLOR", "Repository", "_model_key"]
