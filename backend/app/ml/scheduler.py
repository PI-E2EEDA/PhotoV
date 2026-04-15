from __future__ import annotations

import asyncio
from apscheduler.schedulers.background import BackgroundScheduler

from ..core.db_services import save_current_weather
from .inference import refresh_predictions_task

from ..db import get_session

SCHEDULER = BackgroundScheduler(timezone="UTC")

def _run_async_db_task():
    async def _do_work():
        async for session in get_session():
            await save_current_weather(session)
            break
    asyncio.run(_do_work())

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
        minute=10,
        id="hourly_weather_history",
        replace_existing=True,
    )
    SCHEDULER.start()

def stop_scheduler() -> None:
    if SCHEDULER.running:
        SCHEDULER.shutdown(wait=False)