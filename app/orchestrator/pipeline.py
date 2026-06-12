"""The content pipeline: pick a problem-keyword, write the article, QA it, and
publish it to the live site. Runs daily via the scheduler (or POST /run).
"""

from __future__ import annotations

import structlog
from sqlalchemy import func, select

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.content_run import ContentRun
from app.models.keyword import Keyword
from app.modules.content.generator import generate_article
from app.modules.content.quality import review
from app.modules.keywords.research import research_and_queue
from app.modules.publisher.supabase_client import publish_post

log = structlog.get_logger()

MAX_CANDIDATES_PER_POST = 3  # try up to N keywords until one passes QA


async def _queued_count(db) -> int:
    return await db.scalar(
        select(func.count()).select_from(Keyword).where(Keyword.status == "queued")
    )


async def _next_keyword(db) -> Keyword | None:
    return await db.scalar(
        select(Keyword)
        .where(Keyword.status == "queued")
        .order_by(Keyword.priority.desc(), Keyword.created_at.asc())
        .limit(1)
    )


async def _publish_one() -> dict:
    """Produce and publish a single article, trying successive keywords on QA failure."""
    for _ in range(MAX_CANDIDATES_PER_POST):
        async with AsyncSessionLocal() as db:
            kw = await _next_keyword(db)
            if kw is None:
                return {"status": "skipped", "reason": "no queued keywords"}
            kw_data = {
                "id": kw.id,
                "keyword": kw.keyword,
                "category": kw.category,
                "problem": kw.problem,
            }
            # Claim it so concurrent runs don't double-pick.
            kw.status = "in_progress"
            await db.commit()

        run = ContentRun(keyword_id=kw_data["id"], keyword=kw_data["keyword"])
        try:
            post, tokens = await generate_article(kw_data)
            run.tokens = tokens
            run.slug = post["slug"]
        except Exception as e:  # noqa: BLE001
            log.error("pipeline.generation_failed", keyword=kw_data["keyword"], error=str(e))
            await _finish(kw_data["id"], "failed", str(e)[:500], run, "failed_generation")
            continue

        passed, issues = await review(post)
        run.qa_passed = passed
        run.qa_issues = issues or None
        if not passed:
            log.warning("pipeline.qa_failed", keyword=kw_data["keyword"], issues=issues)
            await _finish(kw_data["id"], "failed", "; ".join(issues)[:500], run, "failed_qa")
            continue

        try:
            await publish_post(post)
        except Exception as e:  # noqa: BLE001
            log.error("pipeline.publish_failed", slug=post["slug"], error=str(e))
            await _finish(kw_data["id"], "queued", str(e)[:500], run, "failed_publish")
            return {"status": "error", "reason": "publish failed", "slug": post["slug"]}

        await _finish(kw_data["id"], "published", None, run, "success", slug=post["slug"])
        return {"status": "published", "slug": post["slug"], "keyword": kw_data["keyword"]}

    return {"status": "skipped", "reason": f"no keyword passed QA in {MAX_CANDIDATES_PER_POST} tries"}


async def _finish(
    keyword_id: str, kw_status: str, reason: str | None, run: ContentRun, run_status: str, slug: str | None = None
) -> None:
    run.status = run_status
    run.error = reason if run_status.startswith("failed") else None
    async with AsyncSessionLocal() as db:
        kw = await db.get(Keyword, keyword_id)
        if kw:
            kw.status = kw_status
            kw.reason = reason
            if slug:
                kw.slug = slug
        db.add(run)
        await db.commit()


async def run_cycle(posts: int | None = None) -> dict:
    posts = posts or settings.posts_per_run

    # Top up the keyword queue if it's running low.
    async with AsyncSessionLocal() as db:
        queued = await _queued_count(db)
    if queued < settings.min_queued_keywords:
        await research_and_queue()

    results = []
    for _ in range(posts):
        results.append(await _publish_one())
    published = [r for r in results if r.get("status") == "published"]
    log.info("pipeline.cycle_done", requested=posts, published=len(published))
    return {"published": len(published), "results": results}
