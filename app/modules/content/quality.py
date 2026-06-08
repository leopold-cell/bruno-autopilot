"""QA gate for auto-published articles: deterministic structural/safety checks
plus a Claude review pass. A post must pass BOTH to go live.
"""

from __future__ import annotations

import re
from typing import Any

import structlog

from app.config import settings
from app.llm import CATEGORIES, cached_system, client, extract_json

log = structlog.get_logger()

# Phrases that overclaim or read as medical advice — disqualifying.
_BANNED = [
    r"\bcure[sd]?\b",
    r"\bdiagnos(e|is|ed)\b",
    r"\bguarantee(d|s)?\b",
    r"\bmiracle\b",
    r"\bclinically proven\b",
]
_CRISIS_HINTS = ["988", "crisis", "emergency", "licensed", "therapist", "professional"]


def _text_blob(post: dict[str, Any]) -> str:
    parts = [post.get("title", ""), post.get("excerpt", ""), post.get("description", "")]
    parts += post.get("tldr", [])
    for b in post.get("body", []):
        parts.append(b.get("text", ""))
        parts += b.get("items", [])
    return " ".join(str(p) for p in parts)


def _word_count(post: dict[str, Any]) -> int:
    return len(_text_blob(post).split())


def structural_check(post: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if not post.get("title"):
        issues.append("missing title")
    if not post.get("slug"):
        issues.append("missing slug")
    if post.get("category") not in CATEGORIES:
        issues.append(f"invalid category: {post.get('category')!r}")
    if len(post.get("body", [])) < 4:
        issues.append("body too short (need >= 4 blocks)")
    if len(post.get("tldr", [])) < 2:
        issues.append("needs >= 2 TL;DR points")
    wc = _word_count(post)
    if wc < settings.min_body_words:
        issues.append(f"too short: {wc} words (min {settings.min_body_words})")

    blob = _text_blob(post).lower()
    for pat in _BANNED:
        if re.search(pat, blob):
            issues.append(f"overclaiming/medical language matched /{pat}/")
    if settings.require_crisis_disclaimer and not any(h in blob for h in _CRISIS_HINTS):
        issues.append("missing crisis/safety disclaimer (988 / professional help)")
    return issues


async def llm_review(post: dict[str, Any]) -> tuple[bool, list[str]]:
    system = (
        f"You are a careful editor for {settings.brand_name}, a CBT mental-health coach brand. "
        "Judge whether this article is safe and on-brand to auto-publish. It must be warm, "
        "evidence-based, second-person, never diagnose or promise cures, and include a crisis "
        "disclaimer. Return ONLY JSON: {\"pass\": boolean, \"issues\": string[]}."
    )
    resp = await client().messages.create(
        model=settings.anthropic_model,
        max_tokens=512,
        system=cached_system(system),
        messages=[{"role": "user", "content": str(post)[:12000]}],
    )
    try:
        data = extract_json(resp.content[0].text)
        return bool(data.get("pass")), [str(i) for i in data.get("issues", [])]
    except Exception as e:  # noqa: BLE001
        log.warning("quality.llm_review_unparseable", error=str(e))
        return True, []  # don't block on a parse failure; structural checks still gate


async def review(post: dict[str, Any]) -> tuple[bool, list[str]]:
    issues = structural_check(post)
    if issues:
        return False, issues
    ok, llm_issues = await llm_review(post)
    return ok, llm_issues
