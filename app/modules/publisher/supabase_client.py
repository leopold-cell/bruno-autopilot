"""Publishes generated articles into the Bruno website's Supabase `blog_posts`
table via the PostgREST API, using the service-role key (bypasses RLS). The
website reads these rows instantly — no redeploy needed.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx
import structlog

from app.config import settings

log = structlog.get_logger()


def _base() -> str:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set to publish.")
    return settings.supabase_url.rstrip("/") + "/rest/v1"


def _headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    key = settings.supabase_service_role_key
    h = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if extra:
        h.update(extra)
    return h


async def fetch_published_slugs() -> set[str]:
    """All slugs already on the site (published or draft). Never raises."""
    try:
        async with httpx.AsyncClient(timeout=15) as http:
            r = await http.get(
                f"{_base()}/blog_posts",
                params={"select": "slug"},
                headers=_headers(),
            )
            r.raise_for_status()
            return {row["slug"] for row in r.json()}
    except Exception as e:  # noqa: BLE001
        log.warning("publisher.fetch_slugs_failed", error=str(e))
        return set()


async def fetch_post(slug: str) -> dict[str, Any] | None:
    """Fetch a single published post by slug (for re-announcing/testing)."""
    async with httpx.AsyncClient(timeout=15) as http:
        r = await http.get(
            f"{_base()}/blog_posts",
            params={
                "select": "slug,title,excerpt,category,tldr",
                "slug": f"eq.{slug}",
                "limit": "1",
            },
            headers=_headers(),
        )
        r.raise_for_status()
        rows = r.json()
        return rows[0] if rows else None


async def publish_post(post: dict[str, Any]) -> dict[str, Any]:
    """Upsert one post (idempotent on slug) and mark it published."""
    row = {
        "slug": post["slug"],
        "title": post["title"],
        "excerpt": post["excerpt"],
        "description": post["description"],
        "category": post["category"],
        "reading_minutes": post.get("reading_minutes", 5),
        "tldr": post.get("tldr", []),
        "body": post["body"],
        "status": "published",
        "source": "autopilot",
        "keyword": post.get("keyword"),
        "published_at": datetime.now(timezone.utc).isoformat(),
    }
    async with httpx.AsyncClient(timeout=30) as http:
        r = await http.post(
            f"{_base()}/blog_posts",
            params={"on_conflict": "slug"},
            headers=_headers({"Prefer": "resolution=merge-duplicates,return=representation"}),
            json=row,
        )
        r.raise_for_status()
        data = r.json()
    log.info("publisher.published", slug=row["slug"])
    return data[0] if isinstance(data, list) and data else row
