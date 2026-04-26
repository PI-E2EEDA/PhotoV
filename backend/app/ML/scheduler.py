from __future__ import annotations

from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .data_pipeline import fetch_and_store_weather, fetch_and_store_weather_forecast
from .inference import refresh_predictions_task
from .remote_production_ingestion import pull_remote_production_into_db
from ..db import async_session_maker

SCHEDULER = AsyncIOScheduler(timezone="UTC")


async def _run_async_db_task():
    async with async_session_maker() as session:
        await pull_remote_production_into_db(session)
        await fetch_and_store_weather(session)
        await fetch_and_store_weather_forecast(session)


def get_scheduler_health() -> dict:
    jobs = []
    for job in SCHEDULER.get_jobs():
        jobs.append(
            {
                "id": job.id,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
            }
        )

    return {
        "running": bool(SCHEDULER.running),
        "timezone": "UTC",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "jobs": jobs,
    }


def start_scheduler() -> None:
    if SCHEDULER.running:
        return

    SCHEDULER.add_job(
        refresh_predictions_task,
        trigger="cron",
        minute=5,
        id="hourly_refresh_predictions",
        replace_existing=True,
    )

    SCHEDULER.add_job(
        _run_async_db_task,
        trigger="cron",
        minute="0",
        id="hourly_weather_history",
        replace_existing=True,
    )
    SCHEDULER.start()


def stop_scheduler() -> None:
    if SCHEDULER.running:
        SCHEDULER.shutdown(wait=False)