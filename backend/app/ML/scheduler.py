from __future__ import annotations

from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .data_pipeline import (
    ensure_weather_history_recent,
    fetch_and_store_weather_history_open_meteo,
    fetch_and_store_weather_forecast,
)
from .inference import predict_and_store, reload_models
from .remote_production_ingestion import (
    ensure_production_history_recent,
    pull_remote_production_into_db,
)
from .train_from_db import run_training_from_db
from ..db import async_session_maker
import logging

LOGGER = logging.getLogger("pv_api")

SCHEDULER = AsyncIOScheduler(timezone="UTC")


async def _hourly_db_task():
    async with async_session_maker() as session:
        await pull_remote_production_into_db(session)
        await fetch_and_store_weather_forecast(session)
        await predict_and_store(session)

async def _startup_backfill():
    """Runs once at startup: fills weather history and production gaps up to 60 days."""
    async with async_session_maker() as session:
        await ensure_weather_history_recent(session, max_days_back=60)
        await ensure_production_history_recent(session, max_days_back=60)


async def _daily_db_task():
    async with async_session_maker() as session:
        # Keep a 14-day rolling window to catch any missed days
        await fetch_and_store_weather_history_open_meteo(session, days_back=14)


async def _weekly_training_task():
    try:
        LOGGER.info("Starting weekly scheduled model retraining...")
        # L'historique api et meteo est deja tire par les autres tasks (backfill_rows=0)
        await run_training_from_db(
            installation_id=1,
            backfill_rows=0,
            optimize=False,
            optuna_trials=20
        )
        reload_models()
        LOGGER.info("Weekly model retraining and reloading finished.")
    except Exception as e:
        LOGGER.exception(f"Weekly training skipped or failed: {e}")


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

    # One-shot job: runs immediately at startup to fill any data gaps
    SCHEDULER.add_job(
        _startup_backfill,
        trigger="date",
        id="startup_backfill",
        replace_existing=True,
    )

    SCHEDULER.add_job(
        _hourly_db_task,
        trigger="cron",
        minute="5",
        id="hourly_forecast_and_predict",
        replace_existing=True,
    )

    SCHEDULER.add_job(
        _daily_db_task,
        trigger="cron",
        hour="2", # Tourne au milieu de la nuit
        minute="0",
        id="daily_weather_history",
        replace_existing=True,
    )

    SCHEDULER.add_job(
        _weekly_training_task,
        trigger="cron",
        day_of_week="sun",
        hour="3", # Tourne le dimanche tard dans la nuit
        minute="0",
        id="weekly_model_training",
        replace_existing=True,
    )
    SCHEDULER.start()


def stop_scheduler() -> None:
    if SCHEDULER.running:
        SCHEDULER.shutdown(wait=False)