from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from tokenflow.adapters.hook.installer import detect_hook, install_hook
from tokenflow.adapters.persistence import secret_store
from tokenflow.adapters.persistence.repository import Repository
from tokenflow.adapters.web.deps import get_repo

router = APIRouter(tags=["onboarding"])


@router.get("/onboarding/status")
def status(repo: Repository = Depends(get_repo)) -> dict[str, Any]:
    hook = detect_hook()
    api_key = secret_store.status()
    # ccprophet lives under the user's home, regardless of where TOKENFLOW_HOME points.
    ccprophet_candidate = (Path.home() / ".claude-prophet" / "events.duckdb").resolve()
    return {
        "onboarded": repo.is_onboarded(),
        "hook": hook,
        "api_key_configured": bool(api_key["configured"]),
        "api_key": api_key,
        "ccprophet": {
            "candidate_path": str(ccprophet_candidate),
            "exists": ccprophet_candidate.exists(),
        },
    }


@router.post("/onboarding/install-hook")
def post_install_hook(dry_run: bool = False) -> dict[str, Any]:
    try:
        return install_hook(dry_run=dry_run)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/onboarding/complete")
def complete(repo: Repository = Depends(get_repo)) -> dict[str, bool]:
    repo.mark_onboarded()
    return {"onboarded": True}
