"""Better-prompt suggestion engine — static templates (v1) + LLM rewrite (v1)."""
from __future__ import annotations

import os
from typing import Literal

BetterPromptMode = Literal["static", "llm"]


STATIC_TEMPLATES: dict[str, str] = {
    "big-file-load": "grep <pattern> in <basename> — don't load the full file",
    "repeat-question": "Save the answer to CLAUDE.md: <topic>",
    "wrong-model": "Use /model haiku — this is a simple edit",
    "context-bloat": "Run /compact or branch a new session",
    "tool-loop": "Add to CLAUDE.md: error <X> -> fix <Y>",
}


DEFAULT_TEMPLATE = "Be more specific: state the goal + expected output format + the files involved."


def static_suggestion(waste_kind: str | None, *, file_path: str | None = None) -> tuple[str, int]:
    base = STATIC_TEMPLATES.get(waste_kind or "", DEFAULT_TEMPLATE)
    if file_path:
        base = base.replace("<basename>", os.path.basename(file_path)).replace("<pattern>", "<pattern>")
    return base, 3000  # arbitrary est savings for static case


LLM_SYSTEM_PROMPT = """You are a Claude Code usage coach. Rewrite the user's query to be more efficient.
Rules:
- Max 3 lines
- Suggest tool usage (grep/glob) when full-file reads are wasteful
- Recommend a smaller model if appropriate
- Never suggest running bash commands
Output: a rewritten query only, no explanation."""


def llm_user_prompt(
    *,
    query: str,
    tokens_in: int,
    tokens_out: int,
    model: str | None,
    waste_reason: str | None,
) -> str:
    return (
        f"waste_reason: {waste_reason or 'none'}\n"
        f"tokens_used: {tokens_in} in / {tokens_out} out\n"
        f"model_used: {model or 'unknown'}\n"
        f"original_query: {query}"
    )
