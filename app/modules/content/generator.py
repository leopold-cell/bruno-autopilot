"""Generates a complete blog article as JSON that matches the website's
BlogPost / BlogBlock schema (see bruno-ai/src/lib/blog.types.ts).
"""

from __future__ import annotations

import math
from typing import Any

import structlog
from slugify import slugify

from app.config import settings
from app.llm import CATEGORIES, cached_system, client, extract_json

log = structlog.get_logger()

_BLOCK_TYPES = {"h2", "p", "ul", "ol", "quote"}

_SYSTEM = """You are the lead writer for {brand}, a CBT-trained AI mental-health coach.
Write evidence-based, plain-English articles for people in the {market} who are struggling
with anxiety, overthinking, low mood, or sleep. Voice: warm, second-person, practical,
never clinical or preachy. Ground advice in Cognitive Behavioral Therapy.

GEO + SEO rules (you are writing to rank in Google AND be cited by AI engines):
- Answer the search intent in the FIRST paragraph (answer-first).
- Use clear H2 sections, short paragraphs, and at least one list.
- Be specific and actionable; include concrete techniques the reader can try now.

SAFETY (non-negotiable):
- You are a coach, not a therapist. Never diagnose, never promise cures or guaranteed results.
- Include a short, calm paragraph telling readers in crisis to contact {crisis} (US) or local
  emergency services, and to see a licensed professional for ongoing struggles.

Return ONLY valid JSON with this exact shape (no prose, no markdown fences):
{{
  "title": string,                      // compelling, <= 70 chars, includes the core keyword
  "excerpt": string,                    // 1-2 sentence hook
  "description": string,                // <= 160 chars meta description
  "category": one of {cats},
  "tldr": string[],                     // 3-4 punchy takeaways
  "body": BlogBlock[]                   // blocks: {{"type":"h2","text"}} | {{"type":"p","text"}}
                                        //   | {{"type":"ul","items":[]}} | {{"type":"ol","items":[]}}
                                        //   | {{"type":"quote","text"}}
}}
Body must be >= {min_words} words total and feel complete."""


def _word_count(body: list[dict]) -> int:
    words = 0
    for b in body:
        if b.get("type") in ("h2", "p", "quote"):
            words += len(str(b.get("text", "")).split())
        elif b.get("type") in ("ul", "ol"):
            words += sum(len(str(i).split()) for i in b.get("items", []))
    return words


async def generate_article(keyword: dict[str, Any]) -> tuple[dict[str, Any], int]:
    system = _SYSTEM.format(
        brand=settings.brand_name,
        market=settings.target_market,
        crisis=settings.crisis_line_us,
        cats=CATEGORIES,
        min_words=settings.min_body_words,
    )
    user = (
        f"Target keyword: \"{keyword['keyword']}\"\n"
        f"Suggested category: {keyword.get('category')}\n"
        f"Reader's underlying problem: {keyword.get('problem') or 'unspecified'}\n\n"
        "Write the article. JSON only."
    )
    resp = await client().messages.create(
        model=settings.anthropic_model,
        max_tokens=settings.anthropic_max_tokens,
        system=cached_system(system),
        messages=[{"role": "user", "content": user}],
    )
    tokens = resp.usage.input_tokens + resp.usage.output_tokens
    data = extract_json(resp.content[0].text)

    body = [b for b in data.get("body", []) if isinstance(b, dict) and b.get("type") in _BLOCK_TYPES]
    category = data.get("category") if data.get("category") in CATEGORIES else keyword.get("category")
    title = str(data.get("title", "")).strip()

    post = {
        "title": title,
        "slug": slugify(title)[:200],
        "excerpt": str(data.get("excerpt", "")).strip(),
        "description": str(data.get("description", "")).strip()[:200],
        "category": category,
        "reading_minutes": max(1, math.ceil(_word_count(body) / 200)),
        "tldr": [str(t).strip() for t in data.get("tldr", []) if str(t).strip()][:4],
        "body": body,
        "keyword": keyword["keyword"],
    }
    log.info("content.generated", slug=post["slug"], words=_word_count(body), tokens=tokens)
    return post, tokens
