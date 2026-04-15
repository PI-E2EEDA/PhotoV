"""Data ingestion and preprocessing pipeline for PV forecasting using MeteoSwiss OGD."""

from __future__ import annotations

import asyncio
import io
import logging

import aiohttp
import pandas as pd
import requests

from .config import (
    METEOSWISS_STAC_URL,
    METEOSWISS_POINT_ID,
    METEOSWISS_COLUMNS_MAPPING,
    INTERNAL_WEATHER_COLUMNS
)

LOGGER = logging.getLogger(__name__)


async def _fetch_single_param_csv(session: aiohttp.ClientSession, url: str, param_id: str,
                                  point_id: str) -> pd.DataFrame:
    """Télécharge un CSV de paramètre de manière asynchrone et filtre pour le point_id."""
    try:
        async with session.get(url) as response:
            response.raise_for_status()
            csv_text = await response.text(encoding='iso-8859-1')  # La doc précise Latin1 !

            # Lecture rapide en mémoire avec Pandas
            df = pd.read_csv(io.StringIO(csv_text), sep=';')

            # NOTE: Ajuste les noms exacts des colonnes ('reference_ts', 'point_id', 'value')
            # en fonction du header exact du CSV MétéoSuisse s'ils diffèrent.
            # Hypothèse OGD standard :
            col_time = 'reference_ts'
            col_point = 'point_id'
            col_value = 'value'

            # Filtrer pour la maison de ton pote
            df_filtered = df[df[col_point] == int(point_id)].copy()

            # Nettoyage et renommage selon notre config
            internal_name = METEOSWISS_COLUMNS_MAPPING.get(param_id)
            df_filtered = df_filtered.rename(columns={col_time: 'timestamp', col_value: internal_name})

            return df_filtered[['timestamp', internal_name]]

    except Exception as e:
        LOGGER.error(f"Erreur lors du téléchargement de {param_id}: {e}")
        return pd.DataFrame(columns=['timestamp'])


async def _fetch_all_meteoswiss_data_async(point_id: str) -> pd.DataFrame:
    """Orchestre le téléchargement parallèle des 8 paramètres météo."""
    # 1. Obtenir les URLs des fichiers depuis le STAC (Synchrone car très rapide)
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
                task = _fetch_single_param_csv(session, csv_url, param_id, point_id)
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

    df_hourly = loop.run_until_complete(_fetch_all_meteoswiss_data_async(METEOSWISS_POINT_ID))

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
    """Wrapper de compatibilité pour inference.py"""
    if source == "realtime":
        return build_realtime_dataset()
    elif source == "historical":
        # Ton ancien code pour fetch_local_meter_data
        pass
    else:
        raise ValueError(f"Source inconnue: {source}")