"""Database services for saving automated data."""

import logging
import pandas as pd
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.exc import IntegrityError

from ..ml.config import METEOSWISS_POINT_ID
from ..ml.data_pipeline import build_realtime_dataset
from ..models import WeatherHistory

LOGGER = logging.getLogger(__name__)


async def save_current_weather(session: AsyncSession) -> None:
    """Récupère la météo actuelle et la stocke en BDD pour l'historique ML."""
    try:
        import asyncio
        loop = asyncio.get_running_loop()

        # On télécharge la météo (exécuté dans un thread pour ne pas bloquer)
        df_meteo = await loop.run_in_executor(None, build_realtime_dataset)

        if df_meteo.empty:
            LOGGER.error("Impossible de sauvegarder l'historique: DataFrame vide.")
            return

        # On prend la ligne correspondante à "MAINTENANT" (arrondi à 15min)
        now_utc = pd.Timestamp.now(tz="UTC").floor("15min")

        if now_utc in df_meteo.index:
            current_weather = df_meteo.loc[now_utc]
        else:
            current_weather = df_meteo.iloc[0]
            now_utc = current_weather.name

        # Création de l'entrée pour la base de données
        history_entry = WeatherHistory(
            time=now_utc.to_pydatetime(),
            point_id=METEOSWISS_POINT_ID,
            temperature_2m=float(current_weather["temperature_2m"]),
            shortwave_radiation=float(current_weather["shortwave_radiation"]),
            diffuse_radiation=float(current_weather["diffuse_radiation"]),
            precipitation=float(current_weather["precipitation"]),
            windspeed_10m=float(current_weather["windspeed_10m"]),
            cloudcover_high=float(current_weather["cloudcover_high"]),
            cloudcover_medium=float(current_weather["cloudcover_medium"]),
            cloudcover_low=float(current_weather["cloudcover_low"])
        )

        # Sauvegarde
        session.add(history_entry)
        await session.commit()
        LOGGER.info(f"Historique météo enregistré avec succès pour {now_utc}")

    except IntegrityError:
        # La météo de cette heure est déjà enregistrée, on annule proprement
        await session.rollback()
    except Exception as e:
        LOGGER.error(f"Erreur lors de la sauvegarde météo : {e}")