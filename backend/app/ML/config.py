"""Centralized project configuration constants."""

import os
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

# --- Localisation (Valeurs par défaut = point zéro ou générique pour GitHub) ---
# Les VRAIES valeurs doivent être uniquement dans le fichier .env
LATITUDE: float = float(os.environ.get("PV_LATITUDE", "46.8"))   # Anonymisé (arrondi)
LONGITUDE: float = float(os.environ.get("PV_LONGITUDE", "6.6"))  # Anonymisé (arrondi)
ALTITUDE_M: float = float(os.environ.get("PV_ALTITUDE_M", "500.0"))

# --- Solar Panel Configuration ---
PANEL_ANGLE: float = float(os.environ.get("PV_PANEL_ANGLE", "30.0"))
PANEL_ORIENTATION: float = float(os.environ.get("PV_PANEL_ORIENTATION", "180.0")) # Remis au Sud par défaut
PANEL_MANUFACTURER: str = os.environ.get("PV_PANEL_MANUFACTURER", "Generic Manufacturer") # Anonymisé
PANEL_MODEL: str = os.environ.get("PV_PANEL_MODEL", "Generic 300W") # Anonymisé
PANEL_COUNT: int = int(os.environ.get("PV_PANEL_COUNT", "29"))
PANEL_AREA_M2: float = float(os.environ.get("PV_PANEL_AREA_M2", "52.5"))
PANEL_RATED_POWER_W: float = float(os.environ.get("PV_PANEL_RATED_POWER_W", "375.0"))

# --- Météo ---
INTERNAL_WEATHER_COLUMNS: list[str] = [
    "temperature_2m",
    "shortwave_radiation",
    "diffuse_radiation",
    "precipitation",
    "windspeed_10m",
    "cloudcover_high",
    "cloudcover_medium",
    "cloudcover_low",
]

# Mapping de la nouvelle API MétéoSuisse (ogd-local-forecasting)
METEOSWISS_COLUMNS_MAPPING: dict[str, str] = {
    "tre200h0": "temperature_2m",
    "gre000h0": "shortwave_radiation",
    "ods000h0": "diffuse_radiation",
    "rre150h0": "precipitation",
    "fu3010h0": "windspeed_10m",
    "nprohihs": "cloudcover_high",
    "npromths": "cloudcover_medium",
    "nprolohs": "cloudcover_low",
}

# --- Nouvelles URLs Open Data ---
METEOSWISS_STAC_URL: str = "https://data.geo.admin.ch/api/stac/v1/collections/ch.meteoschweiz.ogd-local-forecasting/items"

# Typiquement : 1000 avec type 2 = Code postal de Lausanne
# Point valide (type 2) proche des coordonnees de la maison de reference.
# A surcharger en prod via .env
METEOSWISS_POINT_ID: str = os.environ.get("PV_METEOSWISS_POINT_ID", "144100")
METEOSWISS_POINT_TYPE_ID: int = int(os.environ.get("PV_METEOSWISS_POINT_TYPE_ID", "2"))

# --- Model Configuration ---
MODELS_DIR: str = os.environ.get("PV_MODELS_DIR", "app/artifacts")
HORIZON: int = int(os.environ.get("PV_HORIZON", "288")) # 3 days in 15-minute steps

# --- Remote production ingestion (friend server -> local DB) ---
REMOTE_ENABLED: bool = os.environ.get("PV_REMOTE_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
REMOTE_BASE_URL: str = os.environ.get("PV_REMOTE_BASE_URL", "")
REMOTE_TOKEN: str = os.environ.get("PV_REMOTE_TOKEN", "")
REMOTE_AUTH_SCHEME: str = os.environ.get("PV_REMOTE_AUTH_SCHEME", "Bearer")
REMOTE_LOGIN_PATH: str = os.environ.get("PV_REMOTE_LOGIN_PATH", "/auth/login")
REMOTE_USERNAME: str = os.environ.get("PV_REMOTE_USERNAME", "")
REMOTE_PASSWORD: str = os.environ.get("PV_REMOTE_PASSWORD", "")
REMOTE_MEASURES_PATH: str = os.environ.get("PV_REMOTE_MEASURES_PATH", "/api/measurements")
REMOTE_TIMEOUT_S: int = int(os.environ.get("PV_REMOTE_TIMEOUT_S", "30"))
REMOTE_WINDOW_MINUTES: int = int(os.environ.get("PV_REMOTE_WINDOW_MINUTES", "180"))
REMOTE_INSTALLATION_ID: int = int(os.environ.get("PV_REMOTE_INSTALLATION_ID", "1"))
