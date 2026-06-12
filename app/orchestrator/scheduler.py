"""APScheduler — drives the Bruno content autopilot.

Jobs:
  - Daily at PUBLISH_TIME (PUBLISH_TIMEZONE): write + QA + publish posts_per_run articles.
  - Weekly (Mon 04:00): refresh the problem-based keyword queue.
"""

from __future__ import annotations

import asyncio
import signal

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings

log = structlog.get_logger()


async def job_publish():
    from app.orchestrator.pipeline import run_cycle

    log.info("scheduler.job_start", job="publish")
    try:
        result = await run_cycle()
        log.info("scheduler.job_done", job="publish", published=result.get("published"))
    except Exception as e:  # noqa: BLE001
        log.error("scheduler.job_failed", job="publish", error=str(e))


async def job_keyword_refresh():
    from app.modules.keywords.research import research_and_queue

    log.info("scheduler.job_start", job="keyword_refresh")
    try:
        result = await research_and_queue()
        log.info("scheduler.job_done", job="keyword_refresh", inserted=result.get("inserted"))
    except Exception as e:  # noqa: BLE001
        log.error("scheduler.job_failed", job="keyword_refresh", error=str(e))


async def job_weekly_digest():
    from app.modules.email.weekly import run_weekly_digest

    log.info("scheduler.job_start", job="weekly_digest")
    try:
        result = await run_weekly_digest()
        log.info("scheduler.job_done", job="weekly_digest", featured=result.get("featured"), sent=result.get("sent"))
    except Exception as e:  # noqa: BLE001
        log.error("scheduler.job_failed", job="weekly_digest", error=str(e))


def build_scheduler() -> AsyncIOScheduler:
    tz = settings.publish_timezone
    hour, minute = settings.publish_time.split(":")

    scheduler = AsyncIOScheduler(timezone=tz)
    scheduler.add_job(
        job_publish,
        CronTrigger(hour=int(hour), minute=int(minute), timezone=tz),
        id="daily_publish",
    )
    scheduler.add_job(
        job_keyword_refresh,
        CronTrigger(day_of_week="mon", hour=4, minute=0, timezone=tz),
        id="weekly_keyword_refresh",
    )
    if settings.weekly_digest_enabled:
        wh, wm = settings.weekly_digest_time.split(":")
        scheduler.add_job(
            job_weekly_digest,
            CronTrigger(day_of_week=settings.weekly_digest_day, hour=int(wh), minute=int(wm), timezone=tz),
            id="weekly_digest",
        )
    return scheduler


async def main():
    scheduler = build_scheduler()
    scheduler.start()
    log.info("scheduler.started", jobs=[j.id for j in scheduler.get_jobs()], tz=settings.publish_timezone)

    loop = asyncio.get_running_loop()
    stop = asyncio.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    await stop.wait()
    scheduler.shutdown()
    log.info("scheduler.stopped")


if __name__ == "__main__":
    asyncio.run(main())
