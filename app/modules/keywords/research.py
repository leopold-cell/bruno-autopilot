"""Problem-based keyword research for the USA mindfulness market.

Strategy for a brand-new domain (no Search Console history yet): use Claude to
ideate clusters of *problem-based* queries — the things people actually type
when they're struggling ("how to stop overthinking at night", "why do I feel
anxious for no reason") — optionally widened with Google Autocomplete. Once the
domain accrues impressions, the GSC client (app/modules/gsc) layers in real
"page 2-3" opportunities.
"""

from __future__ import annotations

import httpx
import structlog
from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal
from app.llm import CATEGORIES, cached_system, client, extract_json
from app.models.keyword import Keyword
from app.modules.publisher.supabase_client import fetch_published_slugs

log = structlog.get_logger()

_SYSTEM = (
    "You are an SEO strategist for {brand}, a CBT-trained AI mental-health coach app "
    "(anxiety, overthinking, low mood, sleep). Target market: {market}. You find "
    "PROBLEM-BASED keywords: the exact phrases distressed people search, with clear "
    "informational intent and low-to-moderate competition (long-tail, question-style). "
    "Avoid branded or commercial terms. Each keyword must map to one category from this "
    "exact list: {cats}. Return ONLY JSON: an array of objects with keys "
    "{{keyword, category, intent, problem, priority}} where priority is 1-100 (higher = "
    "bigger opportunity / clearer pain). No prose."
)


async def generate_keyword_ideas(existing: set[str], n: int) -> list[dict]:
    avoid = ", ".join(sorted(existing)) if existing else "(none yet)"
    system = _SYSTEM.format(brand=settings.brand_name, market=settings.target_market, cats=CATEGORIES)
    msg = (
        f"Seed themes: {', '.join(settings.seed_themes)}.\n"
        f"Generate {n} NEW problem-based keywords. Do NOT repeat any of these already-covered "
        f"topics: {avoid}.\nReturn JSON array only."
    )
    resp = await client().messages.create(
        model=settings.anthropic_model,
        max_tokens=2048,
        system=cached_system(system),
        messages=[{"role": "user", "content": msg}],
    )
    data = extract_json(resp.content[0].text)
    out: list[dict] = []
    for item in data if isinstance(data, list) else []:
        kw = str(item.get("keyword", "")).strip().lower()
        cat = str(item.get("category", "")).strip()
        if not kw or cat not in CATEGORIES:
            continue
        out.append(
            {
                "keyword": kw,
                "category": cat,
                "intent": str(item.get("intent", "informational"))[:80],
                "problem": str(item.get("problem", ""))[:500],
                "priority": max(1, min(100, int(item.get("priority", 50)))),
            }
        )
    return out


async def expand_with_autocomplete(seed: str, limit: int = 8) -> list[str]:
    """Best-effort Google Autocomplete expansion (no API key). Never raises."""
    try:
        async with httpx.AsyncClient(timeout=8) as http:
            r = await http.get(
                "https://suggestqueries.google.com/complete/search",
                params={"client": "firefox", "q": seed, "hl": "en", "gl": "us"},
            )
            r.raise_for_status()
            suggestions = r.json()[1]
            return [s.strip().lower() for s in suggestions][:limit]
    except Exception as e:  # noqa: BLE001
        log.warning("keywords.autocomplete_failed", seed=seed, error=str(e))
        return []


async def research_and_queue(target: int | None = None) -> dict:
    """Generate fresh keyword ideas and persist any that are new."""
    target = target or max(settings.min_queued_keywords, 12)
    async with AsyncSessionLocal() as db:
        existing_kw = set((await db.execute(select(Keyword.keyword))).scalars().all())
    covered_slugs = await fetch_published_slugs()
    # Slugs are a rough proxy for covered keywords; fold them into the avoid set.
    avoid = existing_kw | {s.replace("-", " ") for s in covered_slugs}

    # Prefer real DataForSEO keyword data (volume + difficulty) when configured;
    # otherwise fall back to Claude ideation.
    source = "ideation"
    ideas: list[dict] = []
    if settings.dataforseo_login and settings.dataforseo_password:
        from app.modules.keywords.dataforseo import fetch_keywords as dfs_fetch

        ideas = await dfs_fetch(avoid)
        source = "dataforseo"
    if not ideas:
        ideas = await generate_keyword_ideas(avoid, target)
        source = "ideation"

    inserted = 0
    async with AsyncSessionLocal() as db:
        for idea in ideas:
            if idea["keyword"] in existing_kw:
                continue
            db.add(Keyword(source=source, **idea))
            existing_kw.add(idea["keyword"])
            inserted += 1
        await db.commit()

    log.info("keywords.research_done", source=source, generated=len(ideas), inserted=inserted)
    return {"source": source, "generated": len(ideas), "inserted": inserted}
