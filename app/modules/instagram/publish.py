"""Publish a Reel to Instagram via the official Graph API.

Flow (Instagram Content Publishing API):
  1. POST /{ig_user_id}/media   media_type=REELS, video_url=<public mp4>, caption
     -> returns a creation_id (container)
  2. poll GET /{creation_id}?fields=status_code until FINISHED
  3. POST /{ig_user_id}/media_publish  creation_id  -> live Reel

Requires: an Instagram Business/Creator account linked to a Facebook Page, and a
long-lived access token with instagram_content_publish (+ pages) permissions.
The video must be reachable at a public URL (we host the mp4 in Supabase storage).
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import structlog

from app.config import settings

log = structlog.get_logger()


def _base() -> str:
    return f"https://graph.facebook.com/{settings.meta_graph_version}"


async def publish_reel(video_url: str, caption: str) -> dict[str, Any]:
    """Publish a Reel. Returns {published: bool, media_id?, error?}."""
    if not settings.instagram_publish_enabled:
        return {"published": False, "reason": "instagram publishing disabled"}
    token = settings.meta_graph_token
    ig = settings.ig_user_id
    if not token or not ig:
        return {"published": False, "reason": "IG_USER_ID / META_GRAPH_TOKEN not configured"}

    try:
        async with httpx.AsyncClient(timeout=60) as http:
            # 1) create the media container
            r = await http.post(
                f"{_base()}/{ig}/media",
                data={
                    "media_type": "REELS",
                    "video_url": video_url,
                    "caption": caption,
                    "access_token": token,
                },
            )
            if r.status_code != 200:
                log.error("ig.container_failed", status=r.status_code, body=r.text[:400])
                return {"published": False, "error": f"container {r.status_code}: {r.text[:200]}"}
            creation_id = r.json()["id"]

            # 2) poll until the upload is processed (REELS need a moment)
            for _ in range(30):
                await asyncio.sleep(5)
                s = await http.get(
                    f"{_base()}/{creation_id}",
                    params={"fields": "status_code", "access_token": token},
                )
                status = s.json().get("status_code")
                if status == "FINISHED":
                    break
                if status == "ERROR":
                    return {"published": False, "error": "media processing ERROR", "creation_id": creation_id}
            else:
                return {"published": False, "error": "processing timeout", "creation_id": creation_id}

            # 3) publish
            p = await http.post(
                f"{_base()}/{ig}/media_publish",
                data={"creation_id": creation_id, "access_token": token},
            )
            if p.status_code != 200:
                log.error("ig.publish_failed", status=p.status_code, body=p.text[:400])
                return {"published": False, "error": f"publish {p.status_code}: {p.text[:200]}"}
            media_id = p.json().get("id")
            log.info("ig.published", media_id=media_id)
            return {"published": True, "media_id": media_id}
    except Exception as e:  # noqa: BLE001
        log.error("ig.error", error=str(e))
        return {"published": False, "error": str(e)}
