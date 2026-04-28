"""Data ingestion and preprocessing pipeline for PV forecasting using MeteoSwiss OGD."""

from __future__ import annotations

import asyncio
import io
import logging
import math

import aiohttp
import pandas as pd
import requests
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from .config import (
    METEOSWISS_STAC_URL,
    METEOSWISS_POINT_ID,
    METEOSWISS_POINT_TYPE_ID,
    METEOSWISS_COLUMNS_MAPPING,
    INTERNAL_WEATHER_COLUMNS
)
from app.models import WeatherHistory

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
    # 1. Obtenir les URLs des fichiers depuis le STAC (Synchrone car très rapide)
    LOGGER.info(f"Appel du STAC URL : {METEOSWISS_STAC_URL}")
    response = requests.get(METEOSWISS_STAC_URL, timeout=10)
    response.raise_for_status()
    latest_item = response.json()['features'][0]  # Le run le plus récent
    assets = latest_item['assets']

    tasks = []
    # 2. Préparer les requêtes asynchrones pour les paramètres qu'on veut
    async with aiohttp.ClientSession() as session:
        for param_id in METEOSWISS_COLUMNS_MAPPING.keys():
            # Chercher l'asset qui correspond au paramètre
            # Le nom de l'asset dans le STAC contient généralement l'ID du paramètre
            asset_key = next((key for key in assets.keys() if param_id in key), None)

            if asset_key:
                csv_url = assets[asset_key]['href']
                task = _fetch_single_param_csv(session, csv_url, param_id, point_id, point_type_id)
                tasks.append(task)
            else:
                LOGGER.warning(f"Paramètre {param_id} introuvable dans le run STAC actuel.")

        # 3. Exécuter tout en parallèle !
        results_dfs = await asyncio.gather(*tasks)

    # 4. Fusionner tous les DataFrames sur le timestamp
    if not results_dfs:
        raise ValueError("Aucune donnée météo n'a pu être récupérée.")

    # On initialise un DataFrame vide sur lequel faire les jointures
    merged_df = results_dfs[0]
    for df in results_dfs[1:]:
        if not df.empty:
            merged_df = pd.merge(merged_df, df, on='timestamp', how='outer')

    # Formatage final du timestamp
    # MétéoSuisse OGD : YYYYMMDDHHMM en UTC
    merged_df['timestamp'] = pd.to_datetime(merged_df['timestamp'], format='%Y%m%d%H%M', utc=True)
    merged_df = merged_df.set_index('timestamp').sort_index()

    return merged_df


def build_realtime_dataset() -> pd.DataFrame:
    """Point d'entrée principal pour construire les prévisions à 15 min."""
    # Lancer la boucle asynchrone (FastAPI gère ça bien, mais dans un thread séparé il faut créer la boucle)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

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
    """Wrapper de compatibilit pour inference.py"""
    if source == "realtime":
        return build_realtime_dataset()
    elif source == "historical":
        # Ton ancien code pour fetch_local_meter_data
        pass
    else:
        raise ValueError(f"Source inconnue: {source}")

async def fetch_and_store_weather(session: AsyncSession):
    """Fetches meteoswiss data and stores it in Postgres for the point ID (HISTORICAL data only, <= now)."""
    from datetime import datetime, timezone
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
