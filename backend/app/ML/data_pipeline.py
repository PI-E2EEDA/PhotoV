"""Data ingestion and preprocessing pipeline for PV forecasting using MeteoSwiss OGD."""

from __future__ import annotations

import asyncio
import io
import logging
import math
from datetime import datetime, timezone, timedelta

import aiohttp
import pandas as pd
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from .config import (
    METEOSWISS_STAC_URL,
    METEOSWISS_POINT_ID,
    METEOSWISS_POINT_TYPE_ID,
    METEOSWISS_COLUMNS_MAPPING,
    INTERNAL_WEATHER_COLUMNS,
    LATITUDE,
    LONGITUDE
)
from app.models import WeatherHistory, Installation, WeatherForecast

LOGGER = logging.getLogger(__name__)


async def _fetch_single_param_csv(session: aiohttp.ClientSession, url: str, param_id: str,
                                  point_id: str, point_type_id: int) -> pd.DataFrame:
    """Télécharge un CSV de paramètre de manière asynchrone et filtre pour le point_id et type_id."""
    try:
        async with session.get(url) as response:
            response.raise_for_status()
            csv_text = await response.text(encoding='iso-8859-1')  # La doc précise Latin1 !

            # Lecture rapide en mémoire avec Pandas
            df = pd.read_csv(io.StringIO(csv_text), sep=';')
            df.columns = [str(c).strip() for c in df.columns]

            col_time = 'reference_ts' if 'reference_ts' in df.columns else 'Date'
            col_point = 'point_id'
            col_type = 'point_type_id'
            col_value = 'value' if 'value' in df.columns else param_id

            if col_point not in df.columns or col_time not in df.columns or col_value not in df.columns:
                LOGGER.error(
                    f"Colonnes attendues absentes pour {param_id}. Colonnes recues: {list(df.columns)}"
                )
                return pd.DataFrame(columns=['timestamp'])

            # Filtrer pour la maison (ID géographique ET Type d'ID), de façon robuste
            point_series = pd.to_numeric(df[col_point], errors='coerce')
            mask = point_series.eq(float(point_id))
            if col_type in df.columns:
                type_series = pd.to_numeric(df[col_type], errors='coerce')
                mask = mask & type_series.eq(float(point_type_id))

            df_filtered = df[mask].copy()

            if df_filtered.empty:
                LOGGER.warning(
                    f"Erreur logique: [{param_id}] Aucune donnée trouvée pour {point_id} (type {point_type_id})"
                )
                return pd.DataFrame(columns=['timestamp'])

            # Nettoyage et renommage selon notre config
            internal_name = METEOSWISS_COLUMNS_MAPPING.get(param_id)
            df_filtered = df_filtered.rename(columns={col_time: 'timestamp', col_value: internal_name})

            return df_filtered[['timestamp', internal_name]]

    except Exception as e:
        LOGGER.exception(f"Erreur lors du téléchargement de {param_id}: {repr(e)}")
        return pd.DataFrame(columns=['timestamp'])


async def _fetch_all_meteoswiss_data_async(point_id: str, point_type_id: int) -> pd.DataFrame:
    """Orchestre le téléchargement parallèle des 8 paramètres météo."""
    LOGGER.info(f"Appel du STAC URL : {METEOSWISS_STAC_URL}")

    async with aiohttp.ClientSession() as session:
        # 1. Obtenir les URLs des fichiers depuis le STAC (maintenant asynchrone)
        try:
            async with session.get(METEOSWISS_STAC_URL, timeout=10) as response:
                response.raise_for_status()
                stac_data = await response.json()
        except Exception as e:
            LOGGER.exception(f"Impossible de fetch le STAC URL: {e}")
            raise ValueError("Erreur critique: STAC inaccessible.") from e

        latest_item = stac_data['features'][0]
        assets = latest_item['assets']

        # 2. Préparer les requêtes asynchrones pour les paramètres
        tasks = []
        for param_id in METEOSWISS_COLUMNS_MAPPING.keys():
            asset_key = next((key for key in assets.keys() if param_id in key), None)
            if asset_key:
                csv_url = assets[asset_key]['href']
                task = _fetch_single_param_csv(session, csv_url, param_id, point_id, point_type_id)
                tasks.append(task)
            else:
                LOGGER.warning(f"Paramètre {param_id} introuvable dans le run STAC actuel.")

        # 3. Exécuter tout en parallèle
        if not tasks:
            raise ValueError("Aucun paramètre météo n'a pu être préparé pour le téléchargement.")
        
        results_dfs = await asyncio.gather(*tasks)

    # 4. Fusionner tous les DataFrames sur le timestamp
    valid_dfs = [df for df in results_dfs if not df.empty]
    if not valid_dfs:
        raise ValueError("Aucune donnée météo n'a pu être récupérée après téléchargement.")

    merged_df = valid_dfs[0]
    for df in valid_dfs[1:]:
        merged_df = pd.merge(merged_df, df, on='timestamp', how='outer')

    # Formatage final du timestamp
    # MétéoSuisse OGD : YYYYMMDDHHMM en UTC
    merged_df['timestamp'] = pd.to_datetime(merged_df['timestamp'], format='%Y%m%d%H%M', utc=True)
    merged_df = merged_df.set_index('timestamp').sort_index()

    # MeteoSwiss nprohihs/npromths/nprolohs sont en fraction 0–1 ; Open-Meteo est en % 0–100.
    # Conversion pour cohérence train/inférence.
    for col in ("cloudcover_high", "cloudcover_medium", "cloudcover_low"):
        if col in merged_df.columns:
            merged_df[col] = merged_df[col] * 100.0

    return merged_df


def build_realtime_dataset() -> pd.DataFrame:
    """Point d'entre principal pour construire les prvisions  15 min."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        import nest_asyncio
        nest_asyncio.apply()

    df_hourly = loop.run_until_complete(_fetch_all_meteoswiss_data_async(METEOSWISS_POINT_ID, METEOSWISS_POINT_TYPE_ID))

    # --- LA GESTION CRITIQUE DU TEMPS (1H -> 15 MIN) ---
    # On rééchantillonne à 15 minutes.
    df_15min = df_hourly.resample('15min').asfreq()

    # Interpolation linéaire pour les variables continues et douces (temp, vent, nuages)
    cols_to_interpolate = [c for c in df_15min.columns if 'radiation' not in c]
    df_15min[cols_to_interpolate] = df_15min[cols_to_interpolate].interpolate(method='time')

    # Pour la radiation, une simple interpolation linéaire est risquée à l'aube/crépuscule.
    # On fait une interpolation temporelle, MAIS on laissera feature_engineering.py
    # forcer la radiation à 0 la nuit en utilisant l'élévation solaire (pvlib).
    rad_cols = [c for c in df_15min.columns if 'radiation' in c]
    df_15min[rad_cols] = df_15min[rad_cols].interpolate(method='time').clip(lower=0.0)

    # Filtrer pour ne garder que l'horizon désiré (ex: les 72 prochaines heures)
    now = pd.Timestamp.now(tz="UTC").floor("15min")
    df_15min = df_15min[df_15min.index >= now].copy()

    return df_15min

def build_dataset(source: str = "realtime") -> pd.DataFrame:
    if source == "realtime":
        return build_realtime_dataset()
    raise NotImplementedError(f"Source '{source}' non implémentée. Utilise build_forecast_dataset_from_db pour le DB.")

async def fetch_and_store_weather(session: AsyncSession):
    """Fetches meteoswiss data and stores it in Postgres for the point ID (HISTORICAL data only, <= now)."""
    LOGGER.info(f"Début fetch_and_store_weather (History) pour ID {METEOSWISS_POINT_ID} type {METEOSWISS_POINT_TYPE_ID}")
    df = await _fetch_all_meteoswiss_data_async(METEOSWISS_POINT_ID, METEOSWISS_POINT_TYPE_ID)
    if df.empty:
        LOGGER.warning("Aucune donnée historique trouvée.")
        return

    # Filter to keep only past data (timestamp <= now)
    now = pd.Timestamp.now(tz="UTC")
    df = df[df.index <= now].copy()
    if df.empty:
        LOGGER.info("Aucune donnée historique après filtre (tout est du futur).")
        return
    
    df = df.reset_index()
    records = []
    
    for _, row in df.iterrows():
        ts = row["timestamp"].to_pydatetime()
        # Handle NA values and convert to dict
        record = {
            "time": ts,
            "point_id": METEOSWISS_POINT_ID,
            "temperature_2m": row.get("temperature_2m", 0.0),
            "shortwave_radiation": row.get("shortwave_radiation", 0.0),
            "diffuse_radiation": row.get("diffuse_radiation", 0.0),
            "precipitation": row.get("precipitation", 0.0),
            "windspeed_10m": row.get("windspeed_10m", 0.0),
            "cloudcover_high": row.get("cloudcover_high", 0.0),
            "cloudcover_medium": row.get("cloudcover_medium", 0.0),
            "cloudcover_low": row.get("cloudcover_low", 0.0),
        }
        for k, v in record.items():
            if isinstance(v, float) and math.isnan(v):
                record[k] = 0.0
        records.append(record)

    if records:
        stmt = insert(WeatherHistory).values(records)
        stmt = stmt.on_conflict_do_update(
            constraint="weatherhistory_time_point_id_key",
            set_={c.name: c for c in stmt.excluded if c.name not in ["id", "time", "point_id"]}
        )
        await session.execute(stmt)
        await session.commit()
        LOGGER.info(f"Fin fetch_and_store_weather (History): {len(records)} lignes traitées (historique uniquement).")

async def fetch_and_store_weather_history_open_meteo(session: AsyncSession, days_back: int = 7):
    """Fetches historical weather data from Open-Meteo and stores it in Postgres.
    Used for training the model with real observations.
    """
    # Grab the first installation to get true coordinates, otherwise fallback to config
    result = await session.execute(select(Installation).limit(1))
    inst = result.scalars().first()
    
    lat = inst.latitude if inst else LATITUDE
    lon = inst.longitude if inst else LONGITUDE

    LOGGER.info(f"Début fetch_and_store_weather_history_open_meteo (Historique) pour lat={lat}, lon={lon} (derniers {days_back} jours)...")
    
    end_date = datetime.now(timezone.utc).date() - timedelta(days=1)
    start_date = end_date - timedelta(days=days_back)
    
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "hourly": "temperature_2m,shortwave_radiation,diffuse_radiation,precipitation,wind_speed_10m,cloud_cover_low,cloud_cover_mid,cloud_cover_high",
        "wind_speed_unit": "ms", # Important : match MétéoSuisse (m/s)
        "timezone": "UTC"
    }
    
    async with aiohttp.ClientSession() as client:
        async with client.get(url, params=params) as resp:
            if resp.status != 200:
                LOGGER.error(f"Erreur API Open-Meteo: {resp.status} - {await resp.text()}")
                return
            data = await resp.json()
            
    if "hourly" not in data:
        LOGGER.warning("Aucune donnée horaire renvoyée par Open-Meteo.")
        return
        
    hourly = data["hourly"]
    df = pd.DataFrame({
        "timestamp": pd.to_datetime(hourly["time"], utc=True),
        "temperature_2m": hourly["temperature_2m"],
        "shortwave_radiation": hourly["shortwave_radiation"],
        "diffuse_radiation": hourly["diffuse_radiation"],
        "precipitation": hourly["precipitation"],
        "windspeed_10m": hourly["wind_speed_10m"],
        "cloudcover_low": hourly["cloud_cover_low"],
        "cloudcover_medium": hourly["cloud_cover_mid"], # Rename mid -> medium
        "cloudcover_high": hourly["cloud_cover_high"],
    })
    
    # 1. Rééchantillonner à 15 minutes (interpolation)
    df = df.set_index("timestamp").sort_index()
    df_15min = df.resample('15min').asfreq()
    
    cols_to_interpolate = [c for c in df_15min.columns if 'radiation' not in c]
    df_15min[cols_to_interpolate] = df_15min[cols_to_interpolate].interpolate(method='time')
    
    rad_cols = [c for c in df_15min.columns if 'radiation' in c]
    df_15min[rad_cols] = df_15min[rad_cols].interpolate(method='time').clip(lower=0.0)
    
    df_15min = df_15min.dropna().reset_index()
    records = []
    
    for _, row in df_15min.iterrows():
        ts = row["timestamp"].to_pydatetime()
        record = {
            "time": ts,
            "point_id": METEOSWISS_POINT_ID,
            "temperature_2m": row.get("temperature_2m", 0.0),
            "shortwave_radiation": row.get("shortwave_radiation", 0.0),
            "diffuse_radiation": row.get("diffuse_radiation", 0.0),
            "precipitation": row.get("precipitation", 0.0),
            "windspeed_10m": row.get("windspeed_10m", 0.0),
            "cloudcover_high": row.get("cloudcover_high", 0.0),
            "cloudcover_medium": row.get("cloudcover_medium", 0.0),
            "cloudcover_low": row.get("cloudcover_low", 0.0),
        }
        for k, v in record.items():
            if isinstance(v, float) and math.isnan(v):
                record[k] = 0.0
        records.append(record)

    if records:
        stmt = insert(WeatherHistory).values(records)
        stmt = stmt.on_conflict_do_nothing(index_elements=["time", "point_id"])
        await session.execute(stmt)
        await session.commit()
        LOGGER.info(f"Open-Meteo: {len(records)} observations insérées dans WeatherHistory.")

async def fetch_and_store_weather_forecast(session: AsyncSession):
    """Fetches meteoswiss data and stores it in Postgres as WeatherForecast for all installations (FUTURE data only, > now)."""
    from app.models import Installation, WeatherForecast
    from sqlalchemy import select
    from datetime import datetime, timezone

    # 1. Fetch all installations
    LOGGER.info("Début fetch_and_store_weather_forecast")
    result = await session.execute(select(Installation))
    installations = result.scalars().all()
    if not installations:
        LOGGER.warning("Aucune Installation en BDD ! Les prévisions PV ne peuvent pas être liées.")
        return

    reference_time = datetime.now(timezone.utc)

    # In a real scenario, we would use the installation's lat/lon to define the point_id.
    # For now, we use the default point_id.
    df = await _fetch_all_meteoswiss_data_async(METEOSWISS_POINT_ID, METEOSWISS_POINT_TYPE_ID)
    if df.empty:
        LOGGER.warning("Données prévisionnelles vides.")
        return

    # Filter to keep only future data (timestamp > now)
    now = pd.Timestamp.now(tz="UTC")
    df = df[df.index > now].copy()
    if df.empty:
        LOGGER.info("Aucune donnée prévisionnelle après filtre (tout est du passé).")
        return

    df = df.reset_index()
    records = []

    for inst in installations:
        for _, row in df.iterrows():
            target_time = row["timestamp"].to_pydatetime()
            record = {
                "target_time": target_time,
                "reference_time": reference_time,
                "installation_id": inst.id,
                "temperature_2m": row.get("temperature_2m"),
                "shortwave_radiation": row.get("shortwave_radiation"),
                "diffuse_radiation": row.get("diffuse_radiation"),
                "precipitation": row.get("precipitation"),
                "windspeed_10m": row.get("windspeed_10m"),
                "cloudcover_high": row.get("cloudcover_high"),
                "cloudcover_medium": row.get("cloudcover_medium"),
                "cloudcover_low": row.get("cloudcover_low"),
            }
            # Replace NaNs with 0.0
            for k, v in record.items():
                if isinstance(v, float) and math.isnan(v):
                    record[k] = 0.0
            records.append(record)

    if records:
        stmt = insert(WeatherForecast).values(records)
        # Upsert based on the unique constraint we added
        stmt = stmt.on_conflict_do_update(
            index_elements=["installation_id", "target_time", "reference_time"],
            set_={c.name: c for c in stmt.excluded if c.name not in ["id", "installation_id", "target_time", "reference_time"]}
        )
        await session.execute(stmt)
        await session.commit()
        LOGGER.info(f"Fin fetch_and_store_weather_forecast: {len(records)} prévisions insérées pour {len(installations)} installation(s) (futur uniquement).")


async def ensure_weather_history_recent(session: AsyncSession, max_days_back: int = 60) -> None:
    """Backfill weather history from Open-Meteo if DB is empty or has a gap.

    Computes the gap between the last stored entry and yesterday, then fetches only
    what is missing (capped at max_days_back). Safe to call at every startup.
    """
    result = await session.execute(
        select(func.max(WeatherHistory.time)).where(
            WeatherHistory.point_id == METEOSWISS_POINT_ID
        )
    )
    last_time = result.scalar()

    now_utc = datetime.now(timezone.utc)

    if last_time is None:
        days_back = max_days_back
        LOGGER.info("No weather history in DB, backfilling %d days from Open-Meteo.", days_back)
    else:
        if last_time.tzinfo is None:
            last_time = last_time.replace(tzinfo=timezone.utc)
        gap_days = (now_utc - last_time).days
        if gap_days < 1:
            LOGGER.info("Weather history up to date (last entry: %s), skipping backfill.", last_time.date())
            return
        # Fetch the gap + 1 extra day as buffer, capped at max_days_back
        days_back = min(gap_days + 1, max_days_back)
        LOGGER.info("Weather history gap of %d days, backfilling %d days.", gap_days, days_back)

    await fetch_and_store_weather_history_open_meteo(session, days_back=days_back)


async def build_realtime_dataset_async() -> pd.DataFrame:
    """Version async de build_realtime_dataset — pas de nest_asyncio requis."""
    df_hourly = await _fetch_all_meteoswiss_data_async(
        METEOSWISS_POINT_ID, METEOSWISS_POINT_TYPE_ID
    )
    df_15min = df_hourly.resample("15min").asfreq()
    cols_to_interpolate = [c for c in df_15min.columns if "radiation" not in c]
    df_15min[cols_to_interpolate] = df_15min[cols_to_interpolate].interpolate(method="time")
    rad_cols = [c for c in df_15min.columns if "radiation" in c]
    df_15min[rad_cols] = df_15min[rad_cols].interpolate(method="time").clip(lower=0.0)
    now = pd.Timestamp.now(tz="UTC").floor("15min")
    return df_15min[df_15min.index >= now].copy()


async def build_forecast_dataset_from_db(session: AsyncSession, installation_id: int) -> pd.DataFrame:
    """Lit les dernières prévisions météo depuis WeatherForecast en DB.

    Retourne un DataFrame 15-min UTC indexé avec les colonnes INTERNAL_WEATHER_COLUMNS,
    filtré sur l'heure courante et au-delà. Retourne un DataFrame vide si aucune donnée.
    """
    result = await session.execute(
        select(func.max(WeatherForecast.reference_time)).where(
            WeatherForecast.installation_id == installation_id
        )
    )
    latest_ref = result.scalar()
    if latest_ref is None:
        return pd.DataFrame()

    result = await session.execute(
        select(WeatherForecast)
        .where(WeatherForecast.installation_id == installation_id)
        .where(WeatherForecast.reference_time == latest_ref)
        .order_by(WeatherForecast.target_time.asc())
    )
    forecasts = result.scalars().all()
    if not forecasts:
        return pd.DataFrame()

    rows = [
        {
            "time": f.target_time,
            "temperature_2m": f.temperature_2m or 0.0,
            "shortwave_radiation": f.shortwave_radiation or 0.0,
            "diffuse_radiation": f.diffuse_radiation or 0.0,
            "precipitation": f.precipitation or 0.0,
            "windspeed_10m": f.windspeed_10m or 0.0,
            "cloudcover_high": f.cloudcover_high or 0.0,
            "cloudcover_medium": f.cloudcover_medium or 0.0,
            "cloudcover_low": f.cloudcover_low or 0.0,
        }
        for f in forecasts
    ]
    df = pd.DataFrame(rows)
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df = df.set_index("time").sort_index()

    now = pd.Timestamp.now(tz="UTC").floor("15min")
    return df[df.index >= now].copy()
