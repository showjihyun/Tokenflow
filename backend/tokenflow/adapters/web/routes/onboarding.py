from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from tokenflow.adapters.hook.installer import detect_hook, install_hook
from tokenflow.adapters.persistence import paths
from tokenflow.adapters.persistence.repository import Repository
from tokenflow.adapters.web.deps import get_repo

router = APIRouter(tags=["onboarding"])


@router.get("/onboarding/status")
async def status(repo: Repository = Depends(get_repo)) -> dict[str, Any]:
    hook = detect_hook()
    # ccprophet lives under the user's home, regardless of where TOKENFLOW_HOME points.
    ccprophet_candidate = (Path.home() / ".claude-prophet" / "events.duckdb").resolve()
    return {
        "onboarded": repo.is_onboarded(),
        "hook": hook,
        "api_key_configured": paths.secret_path().exists(),
        "ccprophet": {
            "candidate_path": str(ccprophet_candidate),
            "exists": ccprophet_candidate.exists(),
        },
    }


@router.post("/onboarding/install-hook")
async def post_install_hook(dry_run: bool = False) -> dict[str, Any]:
    try:
        return install_hook(dry_run=dry_run)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/onboarding/complete")
async def complete(repo: Repository = Depends(get_repo)) -> dict[str, bool]:
    repo.mark_onboarded()
    return {"onboarded": True}
