from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from tokenflow.adapters.persistence import paths as paths_mod


@pytest.fixture(autouse=True)
def _isolated_tokenflow_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Every test gets its own ~/.tokenflow so state never leaks."""
    home = tmp_path / "tokenflow_home"
    home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("TOKENFLOW_HOME", str(home))
    paths_mod.tokenflow_dir.cache_clear()
    yield home
    paths_mod.tokenflow_dir.cache_clear()
