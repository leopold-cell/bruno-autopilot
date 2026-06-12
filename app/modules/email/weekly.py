"""Weekly digest: pick the strongest post of the week and email the list once.

Claude chooses which of the week's posts is most likely to earn the click and
writes a curiosity-driven subject line + a short teaser. Then we send a single
MailerLite campaign featuring that post.
"""

from __future__ import annotations

import structlog

from app.llm import cached_system, client, extract_json
from app.config import settings
from app.modules.email.mailerlite import build_email_html, send_campaign
from app.modules.publisher.supabase_client import fetch_recent_posts

log = structlog.get_logger()

_SYSTEM = (
    "You are the email editor for {brand}, a warm CBT mental-health coach brand. "
    "From a list of this week's articles, choose the ONE most likely to earn an open "
    "and a click from people struggling with anxiety, sleep, low mood, or overthinking. "
    "Write a curiosity-driven, non-clickbait subject line (<= 55 chars, no emoji) and a "
    "2-sentence teaser that makes them want the full article. Return ONLY JSON: "
    '{{"index": <int>, "subject": <str>, "teaser": <str>}}.'
)


async def _pick_best(posts: list[dict]) -> dict:
    listing = "\n".join(
        f"{i}. [{p.get('category')}] {p.get('title')} — {p.get('excerpt', '')}"
        for i, p in enumerate(posts)
    )
    resp = await client().messages.create(
        model=settings.anthropic_model,
        max_tokens=512,
        system=cached_system(_SYSTEM.format(brand=settings.brand_name)),
        messages=[{"role": "user", "content": f"This week's articles:\n{listing}\n\nReturn JSON only."}],
    )
    data = extract_json(resp.content[0].text)
    idx = int(data.get("index", 0))
    if idx < 0 or idx >= len(posts):
        idx = 0
    return {
        "index": idx,
        "subject": str(data.get("subject") or posts[idx].get("title", ""))[:120],
        "teaser": str(data.get("teaser") or posts[idx].get("excerpt", "")),
    }


async def run_weekly_digest() -> dict:
    posts = await fetch_recent_posts(7)
    if not posts:
        log.info("weekly.skipped", reason="no posts this week")
        return {"sent": False, "reason": "no posts this week"}

    pick = await _pick_best(posts)
    post = posts[pick["index"]]
    html = build_email_html(post, teaser=pick["teaser"])
    result = await send_campaign(pick["subject"], html, name=f"Weekly digest · {post['slug']}")
    log.info("weekly.done", featured=post["slug"], candidates=len(posts), sent=result.get("sent"))
    return {**result, "featured": post["slug"], "candidates": len(posts), "subject": pick["subject"]}
