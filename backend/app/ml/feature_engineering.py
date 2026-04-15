"""Feature engineering utilities for 15-minute PV and household load forecasting."""

from __future__ import annotations

from typing import Iterable, Sequence, Optional

import numpy as np
import pandas as pd
from pvlib.solarposition import get_solarposition
from pvlib.irradiance import get_total_irradiance

from .config import (
    ALTITUDE_M, LATITUDE, LONGITUDE,
    INTERNAL_WEATHER_COLUMNS,
    PANEL_ANGLE, PANEL_ORIENTATION
)

EXPECTED_WEATHER_COLUMNS = INTERNAL_WEATHER_COLUMNS


def _validate_datetime_index(df: pd.DataFrame) -> None:
    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError("DataFrame index must be a pandas DatetimeIndex.")
    if df.index.tz is None:
        raise ValueError("DatetimeIndex must be timezone-aware in UTC.")
    if str(df.index.tz) != "UTC":
        raise ValueError(f"DatetimeIndex timezone must be UTC, got: {str(df.index.tz)}")


def _validate_columns(df: pd.DataFrame, columns: Iterable[str]) -> None:
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")


def add_lag_features(df: pd.DataFrame, columns: list[str], lags: list[int]) -> pd.DataFrame:
    _validate_datetime_index(df)
    _validate_columns(df, columns)

    out = df.copy()
    for col in columns:
        for lag in sorted(set(lags)):
            out[f"{col}_lag_{lag}"] = out[col].shift(lag)
    return out


def add_rolling_features(df: pd.DataFrame, columns: list[str], windows: list[int],
                         stats: Sequence[str] = ("mean", "std")) -> pd.DataFrame:
    _validate_datetime_index(df)
    _validate_columns(df, columns)

    out = df.copy()
    for col in columns:
        base = out[col].shift(1)
        for window in sorted(set(windows)):
            rolled = base.rolling(window=window, min_periods=window)
            for stat in stats:
                out[f"{col}_roll_{stat}_{window}"] = getattr(rolled, stat)()
    return out


def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    _validate_datetime_index(df)
    out = df.copy()
    idx = out.index

    out["hour"] = idx.hour
    out["minute"] = idx.minute
    out["day_of_week"] = idx.dayofweek
    out["day_of_year"] = idx.dayofyear
    out["month"] = idx.month
    out["is_weekend"] = (idx.dayofweek >= 5).astype(int)

    out["hour_sin"] = np.sin(2.0 * np.pi * idx.hour / 24.0)
    out["hour_cos"] = np.cos(2.0 * np.pi * idx.hour / 24.0)
    out["dow_sin"] = np.sin(2.0 * np.pi * idx.dayofweek / 7.0)
    out["dow_cos"] = np.cos(2.0 * np.pi * idx.dayofweek / 7.0)
    out["doy_sin"] = np.sin(2.0 * np.pi * idx.dayofyear / 366.0)
    out["doy_cos"] = np.cos(2.0 * np.pi * idx.dayofyear / 366.0)

    return out


def add_solar_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add solar-position and Plane of Array (POA) irradiance features."""
    _validate_datetime_index(df)
    out = df.copy()

    # 1. Position Solaire
    solar = get_solarposition(
        time=out.index,
        latitude=LATITUDE,
        longitude=LONGITUDE,
        altitude=ALTITUDE_M,
    )

    out["solar_apparent_zenith"] = solar["apparent_zenith"].to_numpy()
    out["solar_zenith"] = solar["zenith"].to_numpy()
    out["solar_elevation"] = 90.0 - out["solar_zenith"]
    out["solar_azimuth"] = solar["azimuth"].to_numpy()
    out["solar_cos_zenith"] = np.clip(np.cos(np.deg2rad(out["solar_apparent_zenith"])), 0.0, None)
    out["is_daylight"] = (out["solar_cos_zenith"] > 0.0).astype(int)

    # 2. Calcul Physique de l'Irradiance POA (La vraie énergie qui frappe le panneau)
    if "shortwave_radiation" in out.columns and "diffuse_radiation" in out.columns:
        ghi = out["shortwave_radiation"].clip(lower=0.0)
        dhi = out["diffuse_radiation"].clip(lower=0.0)

        # MétéoSuisse ne donne pas le rayonnement direct normal (DNI). On le calcule :
        # GHI = DNI * cos(zenith) + DHI  =>  DNI = (GHI - DHI) / cos(zenith)
        # On ajoute un petit epsilon (1e-6) pour éviter la division par zéro la nuit
        dni = (ghi - dhi) / (out["solar_cos_zenith"] + 1e-6)
        dni = dni.clip(lower=0.0)  # Pas de soleil négatif

        # Le calcul magique de pvlib
        poa_irrad = get_total_irradiance(
            surface_tilt=PANEL_ANGLE,
            surface_azimuth=PANEL_ORIENTATION,
            solar_zenith=out["solar_apparent_zenith"],
            solar_azimuth=out["solar_azimuth"],
            dni=dni,
            ghi=ghi,
            dhi=dhi
        )

        # poa_global est l'énergie totale (directe + diffuse + réfléchie) sur le panneau incliné
        out["poa_global_radiation"] = poa_irrad["poa_global"].fillna(0.0)

        # On garde ton index clear-sky mais basé sur le POA
        clear_sky_ref = 1000.0 * out["solar_cos_zenith"]
        out["clearsky_index_proxy"] = np.where(
            clear_sky_ref > 1e-6,
            out["poa_global_radiation"] / clear_sky_ref,
            0.0,
        )
        out["clearsky_index_proxy"] = out["clearsky_index_proxy"].clip(0.0, 2.0)

        # Force la nuit absolue (Corrige le risque d'interpolation linéaire)
        night_mask = out["is_daylight"] == 0
        out.loc[night_mask, ["poa_global_radiation", "shortwave_radiation", "diffuse_radiation"]] = 0.0

    return out


def add_weather_interactions(df: pd.DataFrame) -> pd.DataFrame:
    """Add lightweight interaction features between weather variables."""
    out = df.copy()

    # Reconstruction d'un "cloudcover" moyen à partir des 3 altitudes
    cloud_cols = ["cloudcover_high", "cloudcover_medium", "cloudcover_low"]
    if set(cloud_cols).issubset(out.columns):
        out["cloudcover_mean"] = out[cloud_cols].mean(axis=1)

    if {"temperature_2m", "cloudcover_mean"}.issubset(out.columns):
        out["temp_x_cloud"] = out["temperature_2m"] * out["cloudcover_mean"]

    # On utilise maintenant le POA_global pour l'interaction nuages (plus précis !)
    if {"poa_global_radiation", "cloudcover_mean"}.issubset(out.columns):
        out["radiation_x_clear_sky"] = out["poa_global_radiation"] * (
                1.0 - out["cloudcover_mean"].clip(0.0, 100.0) / 100.0
        )

    if {"windspeed_10m", "precipitation"}.issubset(out.columns):
        out["wind_x_precip"] = out["windspeed_10m"] * out["precipitation"]

    return out


def build_features(
        df: pd.DataFrame,
        lag_columns: Optional[list[str]] = None,
        lags: Optional[list[int]] = None,
        rolling_columns: Optional[list[str]] = None,
        rolling_windows: Optional[list[int]] = None,
        drop_na: bool = False,
) -> pd.DataFrame:
    _validate_datetime_index(df)

    out = df.copy()
    out = add_time_features(out)
    out = add_solar_features(out)
    out = add_weather_interactions(out)

    if lag_columns is None:
        # On privilégie notre nouvelle super feature POA pour les lags !
        default_lag_candidates = [
            "production_kw",
            "consumption_kw",
            "poa_global_radiation",  # <--- Remplacé shortwave par POA
            "temperature_2m",
        ]
        lag_columns = [col for col in default_lag_candidates if col in out.columns]

    if lags is None:
        lags = [1, 4, 96]

    if lag_columns and lags:
        out = add_lag_features(out, lag_columns, lags)

    if rolling_columns is None:
        rolling_columns = lag_columns
    if rolling_windows is None:
        rolling_windows = [4, 96]

    if rolling_columns and rolling_windows:
        out = add_rolling_features(
            out,
            columns=rolling_columns,
            windows=rolling_windows,
            stats=("mean", "std"),
        )

    if drop_na:
        out = out.dropna()

    return out