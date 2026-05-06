"""Remote PV production ingestion service (pull model).

This module pulls real production values from a remote API and upserts them
into the local `measure` table as `type=power` rows.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from typing import Any

import httpx
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Measure, MeasureType

from .config import (
    LOCAL_TIMEZONE,
    REMOTE_AUTH_SCHEME,
    REMOTE_BASE_URL,
    REMOTE_ENABLED,
    REMOTE_INSTALLATION_ID,
    REMOTE_LOGIN_PATH,
    REMOTE_MEASURES_PATH,
    REMOTE_PASSWORD,
    REMOTE_TIMEOUT_S,
    REMOTE_TOKEN,
    REMOTE_USERNAME,
    REMOTE_WINDOW_MINUTES,
)

LOGGER = logging.getLogger(__name__)

_LAST_REMOTE_INGESTION: dict[str, Any] = {
    "enabled": REMOTE_ENABLED,
    "status": "idle",
    "last_run_at": None,
    "inserted_or_updated": 0,
    "error": None,
}


def get_remote_ingestion_health() -> dict[str, Any]:
    return dict(_LAST_REMOTE_INGESTION)


def _set_health(status: str, inserted_or_updated: int = 0, error: str | None = None) -> None:
    _LAST_REMOTE_INGESTION.update(
        {
            "enabled": REMOTE_ENABLED,
            "status": status,
            "last_run_at": datetime.now(timezone.utc).isoformat(),
            "inserted_or_updated": inserted_or_updated,
            "error": error,
        }
    )


def _parse_timestamp_local(raw: Any) -> datetime:
    """Parse a remote timestamp and return a naive datetime in the local installation timezone.

    The remote PhotoV API returns SolarEdge measures whose .time is naive local time.
    If the remote sends a tz-aware value (e.g. Z suffix), convert it to local timezone
    first so that it is consistent with how measures are stored in Measure.time.
    """
    from zoneinfo import ZoneInfo
    local_tz = ZoneInfo(LOCAL_TIMEZONE)

    if isinstance(raw, datetime):
        dt = raw
    elif isinstance(raw, str):
        clean = raw.strip()
        if clean.endswith("Z"):
            clean = clean[:-1] + "+00:00"
        dt = datetime.fromisoformat(clean)
    else:
        raise ValueError(f"Unsupported timestamp format: {type(raw)}")

    if dt.tzinfo is None:
        # Naive → assume already local time, keep as-is
        return dt
    # Tz-aware → convert to local timezone, then strip tz
    return dt.astimezone(local_tz).replace(tzinfo=None)


def _iter_records(payload: Any) -> list[dict[str, Any]]:
    # Supported payloads:
    # 1) [ {timestamp_utc, pv_power_w, ...}, ... ]
    # 2) {"data": [ ... ]}
    # 3) {"measurements": [ ... ]}
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("data", "measurements", "items", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
    return []


def _extract_power_w(row: dict[str, Any]) -> float:
    # Accept several field names to avoid tight coupling with the remote API.
    for key in (
        "pv_power_w",
        "solar_production_w",
        "solar_production",
        "production_w",
        "power_w",
        "value",
    ):
        if key in row and row[key] is not None:
            return float(row[key])
    return 0.0





async def _resolve_auth_header(client: httpx.AsyncClient, base: str) -> dict[str, str]:
    if REMOTE_TOKEN:
        return {"Authorization": f"{REMOTE_AUTH_SCHEME} {REMOTE_TOKEN}"}

    if not (REMOTE_USERNAME and REMOTE_PASSWORD):
        raise RuntimeError("Remote auth missing: set PV_REMOTE_TOKEN or PV_REMOTE_USERNAME/PV_REMOTE_PASSWORD")

    login_path = REMOTE_LOGIN_PATH if REMOTE_LOGIN_PATH.startswith("/") else f"/{REMOTE_LOGIN_PATH}"
    login_url = f"{base}{login_path}"
    login_response = await client.post(
        login_url,
        data={"username": REMOTE_USERNAME, "password": REMOTE_PASSWORD},
    )
    login_response.raise_for_status()
    payload = login_response.json()
    token = payload.get("access_token")
    if not token:
        raise RuntimeError("Remote login succeeded but no access_token found")
    token_type = payload.get("token_type", REMOTE_AUTH_SCHEME)
    return {"Authorization": f"{token_type.capitalize()} {token}"}


def _extract_timestamp(row: dict[str, Any]) -> datetime:
    for key in ("timestamp_utc", "timestamp", "time", "datetime"):
        if key in row and row[key] is not None:
            return _parse_timestamp_local(row[key])
    raise ValueError("Missing timestamp field in remote record")


async def _fetch_remote_payload(
    start_utc: datetime,
    end_utc: datetime,
    *,
    limit: int | None = None,
    offset: int = 0,
) -> Any:
    if not REMOTE_BASE_URL:
        raise RuntimeError("PV_REMOTE_BASE_URL is empty")

    base = REMOTE_BASE_URL.rstrip("/")
    path = REMOTE_MEASURES_PATH if REMOTE_MEASURES_PATH.startswith("/") else f"/{REMOTE_MEASURES_PATH}"
    url = f"{base}{path}"
    effective_limit = limit if limit is not None else max(1, min(2000, REMOTE_WINDOW_MINUTES // 15 + 8))
    params = {
        "ascending": "false",
        "limit": int(effective_limit),
        "offset": int(offset),
        "from": start_utc.isoformat(),
        "to": end_utc.isoformat(),
        "installation_id": REMOTE_INSTALLATION_ID,
    }

    timeout = httpx.Timeout(REMOTE_TIMEOUT_S)
    async with httpx.AsyncClient(timeout=timeout) as client:
        headers = await _resolve_auth_header(client=client, base=base)
        response = await client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()


async def pull_remote_production_into_db(session: AsyncSession) -> int:
    if not REMOTE_ENABLED:
        _set_health(status="disabled", inserted_or_updated=0, error=None)
        return 0

    end_utc = datetime.now(timezone.utc)
    start_utc = end_utc - timedelta(minutes=REMOTE_WINDOW_MINUTES)

    try:
        payload = await _fetch_remote_payload(start_utc=start_utc, end_utc=end_utc)
        rows = _iter_records(payload)
        records = _build_measure_records(rows)

        if not records:
            _set_health(status="ok", inserted_or_updated=0, error=None)
            return 0

        stmt = insert(Measure).values(records)
        stmt = stmt.on_conflict_do_update(
            constraint="measure_type_time_installation_id_key",
            set_={
                "solar_production": stmt.excluded.solar_production,
                "solar_consumption": stmt.excluded.solar_consumption,
                "grid_consumption": stmt.excluded.grid_consumption,
            },
        )
        await session.execute(stmt)
        await session.commit()

        _set_health(status="ok", inserted_or_updated=len(records), error=None)
        LOGGER.info("Remote production ingestion finished: %s rows upserted.", len(records))
        return len(records)
    except Exception as exc:
        _set_health(status="error", inserted_or_updated=0, error=str(exc))
        LOGGER.exception("Remote production ingestion failed")
        return 0


def _build_measure_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build measure records from SolarEdge API response rows.
    
    Expected fields from SolarEdge API:
    - pv_power_w (or similar): production in watts
    - solar_consumption (or solar_consumption_w): consumption from solar
    - grid_consumption (or grid_consumption_w): consumption from grid
    - timestamp_utc: ISO timestamp
    """
    records: list[dict[str, Any]] = []
    for row in rows:
        try:
            ts = _extract_timestamp(row)
            power_w = max(0.0, _extract_power_w(row))
            # SolarEdge returns these directly; fallback to 0.0 if missing
            solar_consumption = float(row.get("solar_consumption", row.get("solar_consumption_w", 0.0)))
            grid_consumption = float(row.get("grid_consumption", row.get("grid_consumption_w", 0.0)))
            
            records.append(
                {
                    "type": MeasureType.power,
                    "time": ts,
                    "installation_id": REMOTE_INSTALLATION_ID,
                    "solar_production": power_w,
                    "solar_consumption": max(0.0, solar_consumption),
                    "grid_consumption": max(0.0, grid_consumption),
                }
            )
        except Exception:
            LOGGER.exception("Skipping invalid remote record: %s", row)
    return records


async def backfill_remote_production_into_db(
    session: AsyncSession,
    total_rows: int = 1500,
    page_size: int = 200,
) -> int:
    """Backfill older remote power measures using offset pagination."""
    if not REMOTE_ENABLED:
        _set_health(status="disabled", inserted_or_updated=0, error=None)
        return 0

    if total_rows <= 0:
        return 0

    page_size = max(1, min(page_size, 1000))
    end_utc = datetime.now(timezone.utc)
    start_utc = end_utc - timedelta(days=3650)

    inserted_total = 0
    for offset in range(0, total_rows, page_size):
        payload = await _fetch_remote_payload(
            start_utc=start_utc,
            end_utc=end_utc,
            limit=min(page_size, total_rows - offset),
            offset=offset,
        )
        rows = _iter_records(payload)
        if not rows:
            break

        records = _build_measure_records(rows)
        if not records:
            break

        stmt = insert(Measure).values(records)
        stmt = stmt.on_conflict_do_update(
            constraint="measure_type_time_installation_id_key",
            set_={
                "solar_production": stmt.excluded.solar_production,
                "solar_consumption": stmt.excluded.solar_consumption,
                "grid_consumption": stmt.excluded.grid_consumption,
            },
        )
        await session.execute(stmt)
        await session.commit()
        inserted_total += len(records)

        if len(rows) < min(page_size, total_rows - offset):
            break

    _set_health(status="ok", inserted_or_updated=inserted_total, error=None)
    LOGGER.info("Remote production backfill finished: %s rows upserted.", inserted_total)
    return inserted_total


async def ensure_production_history_recent(session: AsyncSession, max_days_back: int = 60) -> int:
    """Backfill production measures if the last entry is older than 1 day or missing.

    Checks the most recent Measure.time for the configured installation, then fetches
    only the missing rows (up to max_days_back × 96 rows at 15-min resolution).
    """
    if not REMOTE_ENABLED:
        LOGGER.info("Remote ingestion disabled, skipping production backfill.")
        return 0

    from sqlalchemy import func
    from app.models import MeasureType

    result = await session.execute(
        select(func.max(Measure.time)).where(
            Measure.installation_id == REMOTE_INSTALLATION_ID,
            Measure.type == MeasureType.power,
        )
    )
    last_time = result.scalar()
    if last_time is not None and last_time.tzinfo is not None:
        last_time = last_time.replace(tzinfo=None)

    now_naive = datetime.now().replace(second=0, microsecond=0)

    if last_time is None:
        days_back = max_days_back
        LOGGER.info("No production measures in DB, backfilling %d days.", days_back)
    else:
        gap_days = (now_naive - last_time).days
        if gap_days < 1:
            LOGGER.info("Production measures are up to date (last: %s).", last_time)
            return 0
        days_back = min(gap_days + 1, max_days_back)
        LOGGER.info("Production gap of %d days, backfilling %d days.", gap_days, days_back)

    total_rows = days_back * 96  # 96 quarter-hours per day
    return await backfill_remote_production_into_db(session, total_rows=total_rows)

