"""DataForSEO keyword research — real search volume + difficulty for the USA market.

Pulls long-tail suggestions per seed, keeps the problem/question-based ones, and
scores priority from volume (higher = better) and difficulty (lower = better).
Falls back to Claude ideation if not configured (see research.py).
"""

from __future__ import annotations

import httpx
import structlog

from app.config import settings

log = structlog.get_logger()

BASE = "https://api.dataforseo.com/v3"
US_LOCATION = 2840  # United States
LANG = "en"

# (query seed, category) — categories must match the website's allowed set.
DFS_SEEDS: list[tuple[str, str]] = [
    ("anxiety", "Anxiety"),
    ("overthinking", "Anxiety"),
    ("panic attack", "Anxiety"),
    ("stress", "Anxiety"),
    ("depression", "Depression"),
    ("low mood", "Depression"),
    ("insomnia", "Sleep"),
    ("can't sleep", "Sleep"),
    ("intrusive thoughts", "CBT"),
    ("negative thinking", "CBT"),
]

# Keep informational / problem-intent phrases; skip branded/commercial terms.
PROBLEM_MARKERS = (
    "how", "why", "what", "when", "can ", "stop", "deal", "cope", "help",
    "night", "without", "feel", "calm", "reduce", "ways to", "tips",
)


def _priority(volume: int, difficulty: int) -> int:
    vol_score = min(55.0, (volume or 0) ** 0.5)          # diminishing returns on volume
    ease_score = (100 - (difficulty if difficulty is not None else 50)) * 0.45
    return max(5, min(100, round(vol_score + ease_score)))


def _is_problem_based(kw: str) -> bool:
    k = kw.lower()
    return any(m in k for m in PROBLEM_MARKERS)


async def _suggestions(seed: str, limit: int) -> list[dict]:
    auth = (settings.dataforseo_login, settings.dataforseo_password)
    body = [
        {
            "keyword": seed,
            "location_code": US_LOCATION,
            "language_code": LANG,
            "limit": limit,
            "filters": [["keyword_info.search_volume", ">", 80]],
            "order_by": ["keyword_info.search_volume,desc"],
        }
    ]
    async with httpx.AsyncClient(timeout=45) as http:
        r = await http.post(
            f"{BASE}/dataforseo_labs/google/keyword_suggestions/live", json=body, auth=auth
        )
        r.raise_for_status()
        data = r.json()

    tasks = data.get("tasks") or []
    if not tasks or not (tasks[0].get("result")):
        return []
    items = (tasks[0]["result"][0] or {}).get("items") or []
    out = []
    for it in items:
        kw = (it.get("keyword") or "").strip().lower()
        info = it.get("keyword_info") or {}
        props = it.get("keyword_properties") or {}
        out.append(
            {
                "keyword": kw,
                "volume": int(info.get("search_volume") or 0),
                "difficulty": int(props.get("keyword_difficulty") or 50),
            }
        )
    return out


async def fetch_keywords(avoid: set[str], per_seed: int = 40, cap: int = 40) -> list[dict]:
    """Real keyword ideas framed for our Keyword schema, sorted by priority."""
    results: list[dict] = []
    seen: set[str] = set()
    for seed, category in DFS_SEEDS:
        try:
            items = await _suggestions(seed, per_seed)
        except Exception as e:  # noqa: BLE001
            log.warning("dataforseo.suggestions_failed", seed=seed, error=str(e))
            continue
        for it in items:
            kw = it["keyword"]
            if not kw or kw in seen or kw in avoid or not _is_problem_based(kw):
                continue
            seen.add(kw)
            results.append(
                {
                    "keyword": kw,
                    "category": category,
                    "intent": "informational",
                    "problem": f"Real searches for: {kw}",
                    "priority": _priority(it["volume"], it["difficulty"]),
                }
            )
    results.sort(key=lambda x: x["priority"], reverse=True)
    log.info("dataforseo.fetched", total=len(results))
    return results[:cap]
