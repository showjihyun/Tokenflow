from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from tokenflow.adapters.coach.client import (
    MODEL_SONNET_4_6,
    CoachAuthError,
    CoachClientUnavailableError,
    CoachRateLimitError,
    CoachUpstreamError,
    chat_sonnet,
)
from tokenflow.adapters.persistence.repository import Repository
from tokenflow.adapters.web.deps import get_bus, get_repo
from tokenflow.adapters.web.pubsub import EventBus
from tokenflow.adapters.web.rate_limit import coach_limiter, make_dependency

router = APIRouter(tags=["coach"])


COACH_SYSTEM_PROMPT = (
    "You are TokenFlow Coach. You analyze the user's Claude Code usage data (tokens, cost, models, waste patterns)"
    " and give concrete, concise advice on how to use Claude Code more efficiently.\n"
    "Rules:\n"
    "- Be direct. Use bullet lists when listing actions.\n"
    "- Refer to specific data points from the injected context (token counts, costs, model shares, waste kinds).\n"
    "- Do not ask the user to paste their file contents — you already have aggregate stats.\n"
    "- Respond in the user's language (Korean if the user writes Korean, English otherwise)."
)

COACH_SUGGESTIONS = [
    "오늘 가장 낭비된 세션 분석해줘",
    "이 질문 더 효율적으로 바꾸면?",
    "Opus 를 꼭 써야 할 때는?",
    "컨텍스트 압축 언제 해야 해?",
    "예산 초과 막으려면?",
]


class CreateThreadBody(BaseModel):
    title: str | None = Field(default=None, max_length=200)


class SendMessageBody(BaseModel):
    # 20k chars is well above a reasonable user query and well below LLM token cost explosion.
    content: str = Field(min_length=1, max_length=20_000)


class QueryQualityBody(BaseModel):
    query: str = Field(min_length=1, max_length=20_000)
    context: dict[str, Any] = Field(default_factory=dict)


_coach_rate_limit = make_dependency(coach_limiter)


def _mk_id(prefix: str, seed: str) -> str:
    return f"{prefix}_{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:16]}"


def _build_context_snapshot(repo: Repository) -> dict[str, Any]:
    """Privacy-preserving context: counts/costs/models only. No query text, no file content."""
    models = repo.models_today()
    budget = repo.budget()
    current = repo.get_current_session()
    wastes = repo.list_wastes(status="active")
    return {
        "models_today": [
            {"key": m["key"], "tokens": m["tokens"], "cost": m["cost"], "share": m["share"]}
            for m in models
        ],
        "budget": {
            "monthly_limit": budget["month"],
            "spent": budget["spent"],
            "forecast": budget["forecast"],
            "opus_share": budget["opusShare"],
        },
        "current_session": None
        if not current or not current.get("id")
        else {
            "project": current["project"],
            "model": current["model"],
            "input_tokens": current["tokens"]["input"],
            "output_tokens": current["tokens"]["output"],
            "cache_read": current["tokens"]["cacheRead"],
            "context_used": current["contextUsed"],
            "context_window": current["contextWindow"],
            "cost_usd": current["costUSD"],
        },
        "waste_summary": [
            {"kind": w["kind"], "severity": w["severity"], "save_usd": w["save_usd"]}
            for w in wastes[:10]
        ],
    }


def _score_query_quality(query: str, context: dict[str, Any]) -> dict[str, Any]:
    words = [w for w in query.strip().split() if w]
    lowered = query.lower()
    verbs = ("fix", "add", "update", "refactor", "explain", "test", "implement", "debug", "write", "review")
    has_file_ref = any(token in lowered for token in (".py", ".ts", ".tsx", ".js", ".jsx", ".md", "function", "class", "line"))
    has_context = has_file_ref or bool(context.get("file") or context.get("function") or context.get("project"))
    has_model_hint = any(token in lowered for token in ("haiku", "sonnet", "opus", "simple", "complex", "cheap", "fast"))
    has_output_scope = any(token in lowered for token in ("json", "table", "bullet", "diff", "patch", "only", "format", "summary"))

    signals = {
        "specificity": 25 if len(words) >= 12 and any(v in lowered for v in verbs) else 12 if len(words) >= 6 else 0,
        "has_context": 25 if has_context else 0,
        "model_match": 25 if has_model_hint else 12,
        "scope_bounded": 25 if has_output_scope else 0,
    }
    score = sum(signals.values())
    if score >= 85:
        grade = "A"
    elif score >= 70:
        grade = "B"
    elif score >= 55:
        grade = "C"
    else:
        grade = "D"
    return {"grade": grade, "score": score, "signals": signals}


def _publish_api_error(bus: EventBus, *, source: str, status: str) -> None:
    bus.publish({"kind": "api-error", "source": source, "status": status})


@router.get("/coach/threads")
async def list_threads(repo: Repository = Depends(get_repo)) -> list[dict[str, Any]]:
    return repo.list_coach_threads()


@router.post("/coach/threads")
async def create_thread(body: CreateThreadBody, repo: Repository = Depends(get_repo)) -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    thread_id = _mk_id("th", f"{now.isoformat()}-{body.title}")
    return repo.create_coach_thread(thread_id, title=body.title or "New thread")


@router.get("/coach/threads/{thread_id}/messages")
async def list_messages(thread_id: str, repo: Repository = Depends(get_repo)) -> list[dict[str, Any]]:
    return repo.list_coach_messages(thread_id)


@router.post(
    "/coach/threads/{thread_id}/messages",
    dependencies=[Depends(make_dependency(coach_limiter))],
)
async def send_message(
    thread_id: str,
    body: SendMessageBody,
    repo: Repository = Depends(get_repo),
    bus: EventBus = Depends(get_bus),
) -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    user_id = _mk_id("msg", f"{thread_id}-{now.isoformat()}-user")
    repo.insert_coach_message(
        message_id=user_id, thread_id=thread_id, role="me",
        content=body.content, ts=now,
    )

    # Build context + call LLM (respect the user-chosen model from tf_config).
    snapshot = _build_context_snapshot(repo)
    history = repo.list_coach_messages(thread_id)
    messages = [{"role": "assistant" if m["role"] == "ai" else "user", "content": m["content"]} for m in history]
    chosen_model = str(repo.get_config().get("llm_model") or "") or None
    try:
        resp = chat_sonnet(
            system_prompt=COACH_SYSTEM_PROMPT + "\n\nLive data: " + str(snapshot),
            messages=messages,
            max_tokens=800,
            temperature=0.3,
            model=chosen_model,
        )
    except CoachClientUnavailableError as e:
        _publish_api_error(bus, source="AI Coach", status="unavailable")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except CoachAuthError as e:
        _publish_api_error(bus, source="AI Coach", status="auth rejected")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except CoachRateLimitError as e:
        _publish_api_error(bus, source="AI Coach", status="rate limited")
        raise HTTPException(status_code=429, detail=str(e), headers={"Retry-After": "30"}) from e
    except CoachUpstreamError as e:
        _publish_api_error(bus, source="AI Coach", status="upstream error")
        raise HTTPException(status_code=502, detail=str(e)) from e

    usage = resp["usage"]
    pricing = repo.pricing_for(resp.get("model") or MODEL_SONNET_4_6) or (3.0, 15.0, 3.75, 0.3)
    cost = (
        (usage["input_tokens"] / 1e6) * pricing[0]
        + (usage["output_tokens"] / 1e6) * pricing[1]
        + (usage["cache_creation_input_tokens"] / 1e6) * pricing[2]
        + (usage["cache_read_input_tokens"] / 1e6) * pricing[3]
    )
    ai_now = datetime.now(tz=UTC)
    ai_id = _mk_id("msg", f"{thread_id}-{ai_now.isoformat()}-ai")
    repo.insert_coach_message(
        message_id=ai_id, thread_id=thread_id, role="ai",
        content=resp["text"], ts=ai_now,
        input_tokens=usage["input_tokens"], output_tokens=usage["output_tokens"],
        cost_usd=cost,
        context_snapshot=snapshot,
    )
    return {
        "id": ai_id,
        "role": "ai",
        "content": resp["text"],
        "input_tokens": usage["input_tokens"],
        "output_tokens": usage["output_tokens"],
        "cost_usd": round(cost, 4),
    }


@router.get("/coach/suggestions")
async def suggestions() -> list[str]:
    return COACH_SUGGESTIONS


@router.post("/coach/query-quality")
async def query_quality(body: QueryQualityBody) -> dict[str, Any]:
    return _score_query_quality(body.query, body.context)
