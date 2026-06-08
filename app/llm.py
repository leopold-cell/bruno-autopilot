from __future__ import annotations

import json
import re
from typing import Any

import anthropic

from app.config import settings

# Categories must match the website's BlogPost["category"] union exactly.
CATEGORIES = ["Anxiety", "Depression", "CBT", "Sleep", "Self-check"]


def client() -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)


def cached_system(text: str) -> list[dict[str, Any]]:
    """System block with 5-min ephemeral prompt caching (same idiom as Velluto)."""
    return [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]


def extract_json(text: str) -> Any:
    """Parse JSON from a model response, tolerating ```json fences and prose."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Fall back to the first {...} or [...] block.
        for opener, closer in (("{", "}"), ("[", "]")):
            start, end = text.find(opener), text.rfind(closer)
            if start != -1 and end > start:
                return json.loads(text[start : end + 1])
        raise
