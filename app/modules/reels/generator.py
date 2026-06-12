"""Short-form video (Reels/TikTok) creative generator for Bruno.

Turns a topic/keyword into a ready-to-shoot FACELESS reel package, built on the
patterns that go viral under #anxiety: a scroll-stopping first-frame hook, a
warm CBT-grounded voiceover, synced on-screen captions, calm faceless b-roll
prompts (for Higgsfield), a save-bait + question caption, and hashtags.

This is the "creative brain" — it produces everything needed to render + post a
reel. Rendering (b-roll + captions + VO -> mp4) and publishing are later stages.
"""

from __future__ import annotations

import structlog

from app.config import settings
from app.llm import CATEGORIES, cached_system, client, extract_json

log = structlog.get_logger()

# Disqualifying / overclaiming language (same safety bar as the blog).
_BANNED = ("cure", "diagnos", "guarantee", "miracle", "clinically proven")

_SYSTEM = """You are the short-form video producer for {brand}, a CBT mental-health coach brand.
You make FACELESS vertical (9:16) videos for TikTok / Instagram Reels about anxiety,
overthinking, sleep, and low mood — calm b-roll + on-screen text + a voiceover. No talking head.

You have studied what goes viral under #anxiety. Use these proven formats (pick the best fit):
- REFRAME: bust a myth / reframe ("Anxiety isn't a flaw — it's your nervous system doing its job").
- TIPS: numbered instant fix ("3 ways to calm a 3am spiral in 60 seconds") — these earn SAVES.
- RELATABLE_LIST: "Things people with high-functioning anxiety do without realizing".
- SOLIDARITY: vulnerable, "you're not alone", ends on a question.
- NIGHT: the 2:47am angle ("If your mind won't shut off tonight, try this").

Non-negotiable craft:
- HOOK: a punchy first-frame text overlay (<= 60 chars) that stops the scroll.
- VOICEOVER: 20-40 seconds, warm, second-person, grounded in real CBT. Never diagnose, never
  promise cures or guaranteed results. If the topic is crisis-adjacent, include one calm line
  pointing to {crisis} (US).
- CAPTIONS: 4-7 short on-screen lines that track the voiceover beats.
- B-ROLL: 3-4 faceless, cinematic, vertical scene prompts (e.g. rain on a dark window, a single
  lamp at 3am, hands around a warm mug, slow breathing chest, soft morning light, sky). Calm,
  muted, premium — never stocky or clinical.
- CAPTION: an IG/TikTok caption that includes a "Save this for when..." line, a QUESTION to drive
  comments, and a soft "Bruno — a pocket CBT coach (link in bio)" nudge.
- HASHTAGS: 8-12 relevant, mixing big (#anxiety #mentalhealth) and niche (#nervoussystem #cbt).

Return ONLY JSON:
{{"format": str, "hook": str, "voiceover": str, "captions": [str], "broll_prompts": [str],
  "ig_caption": str, "hashtags": [str], "save_bait": str, "category": one of {cats}}}"""


def _qa(pkg: dict) -> list[str]:
    issues = []
    for k in ("hook", "voiceover", "ig_caption"):
        if not str(pkg.get(k, "")).strip():
            issues.append(f"missing {k}")
    if pkg.get("category") not in CATEGORIES:
        issues.append(f"invalid category: {pkg.get('category')!r}")
    if len(pkg.get("broll_prompts") or []) < 2:
        issues.append("need >= 2 b-roll prompts")
    if len(pkg.get("captions") or []) < 3:
        issues.append("need >= 3 caption lines")
    blob = " ".join(
        [str(pkg.get("hook", "")), str(pkg.get("voiceover", "")), str(pkg.get("ig_caption", ""))]
    ).lower()
    for b in _BANNED:
        if b in blob:
            issues.append(f"overclaiming language: {b}")
    return issues


async def generate_reel(topic: str) -> tuple[dict, list[str]]:
    """Generate one reel package for a topic/keyword. Returns (package, qa_issues)."""
    system = _SYSTEM.format(
        brand=settings.brand_name, crisis=settings.crisis_line_us, cats=CATEGORIES
    )
    resp = await client().messages.create(
        model=settings.anthropic_model,
        max_tokens=2048,
        system=cached_system(system),
        messages=[{"role": "user", "content": f"Topic/keyword: \"{topic}\". Make one reel package. JSON only."}],
    )
    pkg = extract_json(resp.content[0].text)
    # normalize
    pkg["hashtags"] = [h if h.startswith("#") else f"#{h}" for h in (pkg.get("hashtags") or [])][:12]
    pkg["topic"] = topic
    issues = _qa(pkg)
    log.info("reels.generated", topic=topic, fmt=pkg.get("format"), qa_ok=not issues)
    return pkg, issues
