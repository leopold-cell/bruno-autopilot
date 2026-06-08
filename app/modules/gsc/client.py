"""Google Search Console client — LATER PHASE.

Once the Bruno domain accrues impressions, this mines real "page 2-3" problem
keywords (positions 11-30, high impressions) to feed the content pipeline,
exactly like the Velluto autopilot. Until GOOGLE_SERVICE_ACCOUNT_JSON +
GSC_SITE_URL are set, it is not instantiated.

To enable: set the env vars, then add a job in app/orchestrator/scheduler.py
that calls get_opportunities() and queues the top queries as Keyword rows.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import structlog

from app.config import settings

log = structlog.get_logger()

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]


class GSCClient:
    def __init__(self) -> None:
        if not settings.google_service_account_json or not settings.gsc_site_url:
            raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON and GSC_SITE_URL not configured")
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        credentials = service_account.Credentials.from_service_account_file(
            settings.google_service_account_json, scopes=SCOPES
        )
        self._service = build("searchconsole", "v1", credentials=credentials, cache_discovery=False)
        self.site_url = settings.gsc_site_url

    def _date(self, days_ago: int) -> str:
        return (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%d")

    def _query(self, request: dict) -> dict:
        return self._service.searchanalytics().query(siteUrl=self.site_url, body=request).execute()

    async def get_opportunities(self) -> dict[str, Any]:
        """Keywords ranking 11-30 with high impressions — page 2-3 opportunities."""
        try:
            data = self._query(
                {
                    "startDate": self._date(28),
                    "endDate": self._date(1),
                    "dimensions": ["query"],
                    "rowLimit": 500,
                }
            )
            opps = [
                {
                    "query": r["keys"][0],
                    "position": round(r.get("position", 0), 1),
                    "impressions": r.get("impressions", 0),
                    "clicks": r.get("clicks", 0),
                }
                for r in data.get("rows", [])
                if 10 < r.get("position", 0) <= 30 and r.get("impressions", 0) > 100
            ]
            opps.sort(key=lambda x: x["impressions"], reverse=True)
            return {"opportunities": opps[:20], "total_found": len(opps)}
        except Exception as e:  # noqa: BLE001
            log.warning("gsc.opportunities_failed", error=str(e))
            return {"opportunities": [], "error": str(e)}
