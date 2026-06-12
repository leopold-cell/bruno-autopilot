"""MailerLite campaigns for the email list.

Strategy: instead of emailing on every publish (too frequent — the autopilot
posts daily), a weekly job picks the strongest post of the week and sends one
campaign. Best-effort throughout — failures never break publishing.
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


def build_email_html(post: dict[str, Any], teaser: str | None = None) -> str:
    url = _post_url(post["slug"])
    title = html.escape(post.get("title", ""))
    teaser_txt = html.escape(teaser or post.get("excerpt", ""))
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
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;">{teaser_txt}</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f7f5ee;">
    <tr><td align="center" style="padding:32px 16px;">
      <table role="presentation" width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;background-color:#ffffff;border:1px solid #e7e3d6;border-radius:20px;">
        <tr><td style="padding:28px 36px 0 36px;">
          <span style="font-family:Georgia,'Times New Roman',serif;font-size:22px;font-weight:700;color:#23302a;">bruno</span>
        </td></tr>
        <tr><td style="padding:14px 36px 0 36px;">
          <p style="margin:0;font-size:12px;font-weight:600;letter-spacing:0.12em;text-transform:uppercase;color:#5b6b60;">This week from the Bruno Journal · {category}</p>
          <h1 style="margin:10px 0 0 0;font-family:Georgia,'Times New Roman',serif;font-size:27px;line-height:1.25;font-weight:700;color:#23302a;">{title}</h1>
          <p style="margin:16px 0 0 0;font-size:16px;line-height:1.6;color:#3f4a44;">{teaser_txt}</p>
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


async def send_campaign(subject: str, content_html: str, name: str) -> dict[str, Any]:
    """Create + instantly send a MailerLite campaign to the waitlist group."""
    key = settings.mailerlite_api_key
    group = settings.mailerlite_group_id
    if not key or not group:
        return {"sent": False, "reason": "mailerlite not configured"}

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {
        "name": name,
        "type": "regular",
        "emails": [
            {
                "subject": subject,
                "from_name": settings.mailerlite_from_name,
                "from": settings.mailerlite_from_email,
                "content": content_html,
            }
        ],
        "groups": [group],
    }
    try:
        async with httpx.AsyncClient(timeout=30) as http:
            r = await http.post(f"{API}/campaigns", headers=headers, json=payload)
            if r.status_code not in (200, 201):
                log.error("email.create_failed", status=r.status_code, body=r.text[:300])
                return {"sent": False, "status": r.status_code}
            cid = r.json()["data"]["id"]
            s = await http.post(
                f"{API}/campaigns/{cid}/schedule", headers=headers, json={"delivery": "instant"}
            )
            if s.status_code not in (200, 201):
                log.error("email.schedule_failed", status=s.status_code, body=s.text[:300])
                return {"sent": False, "campaign": cid, "status": s.status_code}
        log.info("email.campaign_sent", campaign=cid, subject=subject)
        return {"sent": True, "campaign": cid}
    except Exception as e:  # noqa: BLE001
        log.error("email.error", error=str(e))
        return {"sent": False, "error": str(e)}


async def announce_post(post: dict[str, Any]) -> dict[str, Any]:
    """Send a single post to the list now (used by the /announce test endpoint)."""
    return await send_campaign(
        subject=post.get("title", "A new note from Bruno"),
        content_html=build_email_html(post),
        name=f"Post · {post['slug']}",
    )
