from __future__ import annotations

import structlog
from fastapi import APIRouter
from sqlalchemy import desc, func, select

from app.database import AsyncSessionLocal
from app.models.content_run import ContentRun
from app.models.keyword import Keyword

log = structlog.get_logger()
router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/run")
async def run(posts: int | None = None):
    """Trigger one content cycle now (generate + QA + publish)."""
    from app.orchestrator.pipeline import run_cycle

    return await run_cycle(posts)


@router.post("/research")
async def research(target: int | None = None):
    """Refresh the problem-based keyword queue now."""
    from app.modules.keywords.research import research_and_queue

    return await research_and_queue(target)


@router.post("/announce")
async def announce(slug: str):
    """Send a single post to the email list now (test / re-send)."""
    from app.modules.email.mailerlite import announce_post
    from app.modules.publisher.supabase_client import fetch_post

    post = await fetch_post(slug)
    if not post:
        return {"sent": False, "reason": f"post not found: {slug}"}
    return await announce_post(post)


@router.post("/weekly")
async def weekly():
    """Run the weekly digest now: pick the best post of the week + email the list."""
    from app.modules.email.weekly import run_weekly_digest

    return await run_weekly_digest()


@router.get("/dashboard")
async def dashboard():
    async with AsyncSessionLocal() as db:
        queued = await db.scalar(
            select(func.count()).select_from(Keyword).where(Keyword.status == "queued")
        )
        published = await db.scalar(
            select(func.count()).select_from(Keyword).where(Keyword.status == "published")
        )
        recent_runs = (
            await db.execute(select(ContentRun).order_by(desc(ContentRun.created_at)).limit(15))
        ).scalars().all()
        upcoming = (
            await db.execute(
                select(Keyword)
                .where(Keyword.status == "queued")
                .order_by(Keyword.priority.desc())
                .limit(10)
            )
        ).scalars().all()

    return {
        "keywords": {"queued": queued, "published": published},
        "upcoming": [{"keyword": k.keyword, "category": k.category, "priority": k.priority} for k in upcoming],
        "recent_runs": [
            {
                "keyword": r.keyword,
                "slug": r.slug,
                "status": r.status,
                "qa_passed": r.qa_passed,
                "qa_issues": r.qa_issues,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in recent_runs
        ],
    }
