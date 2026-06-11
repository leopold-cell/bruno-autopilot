"""Announce each newly published post to the MailerLite email list as an
instant campaign: subject + teaser + CTA link to the full article.
Best-effort — a MailerLite failure never breaks publishing.
"""

from __future__ import annotations

import html
from typing import Any

import httpx
import structlog

from app.config import settings

log = structlog.get_logger()

API = "https://connect.mailerlite.com/api"


def _post_url(slug: str) -> str:
    return f"{settings.site_url.rstrip('/')}/blog/{slug}"


def build_email_html(post: dict[str, Any]) -> str:
    url = _post_url(post["slug"])
    title = html.escape(post.get("title", ""))
    excerpt = html.escape(post.get("excerpt", ""))
    category = html.escape(str(post.get("category", "")))
    bullets = "".join(
        f'<tr><td style="padding:5px 0;font-size:15px;line-height:1.5;color:#23302a;">— {html.escape(str(t))}</td></tr>'
        for t in (post.get("tldr") or [])[:3]
    )
    bullets_block = (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:16px 0 0 0;">{bullets}</table>'
        if bullets
        else ""
    )
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="margin:0;padding:0;background-color:#f7f5ee;font-family:Helvetica,Arial,sans-serif;color:#23302a;">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;">{excerpt}</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f7f5ee;">
    <tr><td align="center" style="padding:32px 16px;">
      <table role="presentation" width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;background-color:#ffffff;border:1px solid #e7e3d6;border-radius:20px;">
        <tr><td style="padding:28px 36px 0 36px;">
          <span style="font-family:Georgia,'Times New Roman',serif;font-size:22px;font-weight:700;color:#23302a;">bruno</span>
        </td></tr>
        <tr><td style="padding:14px 36px 0 36px;">
          <p style="margin:0;font-size:12px;font-weight:600;letter-spacing:0.12em;text-transform:uppercase;color:#5b6b60;">New from the Bruno Journal · {category}</p>
          <h1 style="margin:10px 0 0 0;font-family:Georgia,'Times New Roman',serif;font-size:27px;line-height:1.25;font-weight:700;color:#23302a;">{title}</h1>
          <p style="margin:16px 0 0 0;font-size:16px;line-height:1.6;color:#3f4a44;">{excerpt}</p>
          {bullets_block}
          <table role="presentation" cellpadding="0" cellspacing="0" style="margin:24px 0 6px 0;">
            <tr><td align="center" bgcolor="#2e5a40" style="border-radius:999px;">
              <a href="{url}" style="display:inline-block;padding:14px 30px;font-size:16px;font-weight:600;color:#ffffff;text-decoration:none;border-radius:999px;">Read the full article &rarr;</a>
            </td></tr>
          </table>
          <p style="margin:18px 0 0 0;font-size:15px;line-height:1.6;color:#3f4a44;">A few minutes for your mind. — The Bruno team</p>
        </td></tr>
        <tr><td style="padding:24px 36px 0 36px;"><div style="border-top:1px solid #e7e3d6;"></div></td></tr>
        <tr><td style="padding:16px 36px 30px 36px;">
          <p style="margin:0;font-size:13px;line-height:1.6;color:#8a938d;">Bruno is a coach, not a therapist or a crisis service. If you're in danger or thinking of self-harm, in the US call or text <strong>988</strong>.</p>
          <p style="margin:10px 0 0 0;font-size:13px;line-height:1.6;color:#8a938d;">brunomind.com</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""


async def announce_post(post: dict[str, Any]) -> dict[str, Any]:
    """Create + instantly send a MailerLite campaign for a new post."""
    key = settings.mailerlite_api_key
    group = settings.mailerlite_group_id
    if not settings.announce_new_posts or not key or not group:
        return {"sent": False, "reason": "announcements disabled or not configured"}

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {
        "name": f"New post · {post['slug']}",
        "type": "regular",
        "emails": [
            {
                "subject": post.get("title", "A new note from Bruno"),
                "from_name": settings.mailerlite_from_name,
                "from": settings.mailerlite_from_email,
                "content": build_email_html(post),
            }
        ],
        "groups": [group],
    }
    try:
        async with httpx.AsyncClient(timeout=30) as http:
            r = await http.post(f"{API}/campaigns", headers=headers, json=payload)
            if r.status_code not in (200, 201):
                log.error("announce.create_failed", status=r.status_code, body=r.text[:300])
                return {"sent": False, "status": r.status_code}
            cid = r.json()["data"]["id"]
            s = await http.post(
                f"{API}/campaigns/{cid}/schedule", headers=headers, json={"delivery": "instant"}
            )
            if s.status_code not in (200, 201):
                log.error("announce.schedule_failed", status=s.status_code, body=s.text[:300])
                return {"sent": False, "campaign": cid, "status": s.status_code}
        log.info("announce.sent", campaign=cid, slug=post["slug"])
        return {"sent": True, "campaign": cid}
    except Exception as e:  # noqa: BLE001
        log.error("announce.error", error=str(e))
        return {"sent": False, "error": str(e)}
