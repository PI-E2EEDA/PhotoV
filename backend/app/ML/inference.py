"""Inference services for PV production and household consumption forecasting."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

import numpy as np
import pandas as pd

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert
from app.models import Measure, MeasureType, Prediction
from ..schemas.prediction import PredictionPoint, PredictionResponse
from .config import HORIZON, LOCAL_TIMEZONE, MODELS_DIR, INTERNAL_WEATHER_COLUMNS
from .data_pipeline import build_dataset, build_forecast_dataset_from_db, build_realtime_dataset_async
from .feature_engineering import build_features
from .model_training import load_forecaster

LOGGER = logging.getLogger("pv_api")

PREDICTIONS_CACHE: dict[str, Any] = {}
CACHE_LOCK = Lock()

# In-memory model cache — loaded once, reused across requests
_MODEL_CACHE: dict[str, Any] = {}

PRODUCTION_MODEL_PATH = Path(MODELS_DIR) / "production_forecaster.joblib"
CONSUMPTION_MODEL_PATH = Path(MODELS_DIR) / "consumption_forecaster.joblib"


def models_available() -> bool:
	"""Return True when both trained model artifacts are present on disk."""
	return PRODUCTION_MODEL_PATH.exists() and CONSUMPTION_MODEL_PATH.exists()


def _load_forecasters() -> tuple[Any, Any]:
	"""Load forecasters from memory cache, or from disk on first call."""
	if "production" in _MODEL_CACHE and "consumption" in _MODEL_CACHE:
		return _MODEL_CACHE["production"], _MODEL_CACHE["consumption"]

	if not models_available():
		raise RuntimeError(
			"Model files are missing. Expected: "
			f"{PRODUCTION_MODEL_PATH} and {CONSUMPTION_MODEL_PATH}."
		)

	production_forecaster = load_forecaster(str(PRODUCTION_MODEL_PATH))
	consumption_forecaster = load_forecaster(str(CONSUMPTION_MODEL_PATH))

	_MODEL_CACHE["production"] = production_forecaster
	_MODEL_CACHE["consumption"] = consumption_forecaster

	return production_forecaster, consumption_forecaster


def reload_models() -> None:
	"""Force reload models from disk (call after retraining)."""
	_MODEL_CACHE.clear()
	_load_forecasters()


async def _fetch_recent_production_df(
    session: AsyncSession,
    installation_id: int,
    n_rows: int = 200,
) -> pd.DataFrame:
    """Retourne les n_rows dernières mesures power indexées en UTC."""
    import zoneinfo
    result = await session.execute(
        select(Measure)
        .where(Measure.installation_id == installation_id)
        .where(Measure.type == MeasureType.power)
        .order_by(Measure.time.desc())
        .limit(n_rows)
    )
    measures = result.scalars().all()
    if not measures:
        return pd.DataFrame()

    local_tz = zoneinfo.ZoneInfo(LOCAL_TIMEZONE)
    rows = [
        {
            "time": pd.Timestamp(m.time, tz=local_tz).tz_convert("UTC"),
            "production_kw": float(m.solar_production) / 1000.0,
            "consumption_kw": float(m.solar_consumption + m.grid_consumption) / 1000.0,
        }
        for m in reversed(measures)  # oldest first
    ]
    df = pd.DataFrame(rows).set_index("time").sort_index()
    return df[~df.index.duplicated(keep="last")]


def _build_features_for_inference(
    recent_prod_df: pd.DataFrame,
    forecast_df: pd.DataFrame,
) -> pd.DataFrame:
    """Construit les features pour l'inférence en ancrant les lags sur l'historique réel.

    Concatène l'historique récent (avec production_kw/consumption_kw) et les prévisions
    météo futures, applique build_features sur l'ensemble, puis retourne uniquement les
    lignes futures. Les lags de production pour les premiers pas seront ainsi des vraies
    valeurs historiques et non pas des zéros.
    """
    if recent_prod_df.empty:
        return build_features(forecast_df, drop_na=False)

    # Étendre le forecast avec des colonnes production vides (NaN → pas de cible)
    forecast_ext = forecast_df.copy()
    forecast_ext["production_kw"] = np.nan
    forecast_ext["consumption_kw"] = np.nan

    # Étendre l'historique avec des colonnes météo vides
    history_ext = recent_prod_df.copy()
    for col in INTERNAL_WEATHER_COLUMNS:
        if col not in history_ext.columns:
            history_ext[col] = np.nan

    combined = pd.concat([history_ext, forecast_ext]).sort_index()
    combined = combined[~combined.index.duplicated(keep="last")]

    features = build_features(combined, drop_na=False)

    # Retourner uniquement les lignes futures (horizon du forecast)
    future_start = forecast_df.index.min()
    return features[features.index >= future_start]


def _prepare_base_features() -> pd.DataFrame:
    """Fallback synchrone : construit les features depuis MeteoSwiss live (sans lags réels)."""
    dataset = build_dataset(source="realtime")
    if dataset.empty:
        now = pd.Timestamp.now(tz="UTC").floor("15min")
        idx = pd.date_range(start=now, periods=HORIZON, freq="15min", tz="UTC")
        dataset = pd.DataFrame(
            {col: np.zeros(HORIZON, dtype=float) for col in INTERNAL_WEATHER_COLUMNS},
            index=idx,
        )
    return build_features(dataset, drop_na=False)


def _build_exog_for_forecaster(
        features_df: pd.DataFrame,
        forecaster: Any,
        horizon: int,
) -> pd.DataFrame | None:
        """Create future exogenous matrix aligned with expected forecaster columns."""
        last_window_end = forecaster.last_window.index[-1] if hasattr(forecaster, 'last_window') and forecaster.last_window is not None else pd.Timestamp.now(tz="UTC").floor("15min")
        expected_start = last_window_end + pd.Timedelta(minutes=15)

        future_index = pd.date_range(start=expected_start, periods=horizon, freq="15min", tz="UTC")
        candidate = pd.DataFrame(index=future_index)

        # Merge with existing features safely to keep recent known weather
        if not features_df.empty:
            merged = pd.concat([features_df, candidate], axis=0).sort_index()
            merged = merged[~merged.index.duplicated(keep='last')]
            merged = merged.interpolate(method="time", limit_direction="both")
            candidate = merged.reindex(future_index)

        candidate = candidate.ffill().bfill().fillna(0.0)

        expected_cols = list(getattr(forecaster, "exog_names_in_", []) or [])
        if not expected_cols:
                return None

        for col in expected_cols:
                if col not in candidate.columns:
                        candidate[col] = 0.0

        exog = candidate[expected_cols]
        # Keep exact index
        exog.index = future_index
        return exog.astype(float)


def build_prediction_response(
    features_df: pd.DataFrame | None = None,
    last_window_prod: "pd.Series | None" = None,
    last_window_cons: "pd.Series | None" = None,
) -> PredictionResponse:
    """Generate predictions and format API response payload.

    last_window_prod / last_window_cons : dernières valeurs réelles de production/conso
    (pd.Series UTC-indexée). Quand fournie, remplace le last_window figé de l'entraînement
    et donne au modèle les vraies valeurs passées pour ses lags AR internes.
    """
    production_forecaster, consumption_forecaster = _load_forecasters()
    features = features_df if features_df is not None else _prepare_base_features()

    exog_prod = _build_exog_for_forecaster(features, production_forecaster, HORIZON)
    exog_cons = _build_exog_for_forecaster(features, consumption_forecaster, HORIZON)

    pred_prod_raw = production_forecaster.predict(
        steps=HORIZON, exog=exog_prod, last_window=last_window_prod
    )
    pred_cons_raw = consumption_forecaster.predict(
        steps=HORIZON, exog=exog_cons, last_window=last_window_cons
    )

    pred_prod = np.clip(np.asarray(pred_prod_raw, dtype=float), 0.0, None)
    pred_cons = np.clip(np.asarray(pred_cons_raw, dtype=float), 0.0, None)

    if hasattr(pred_prod_raw, "index") and isinstance(pred_prod_raw.index, pd.DatetimeIndex):
        pred_index = pred_prod_raw.index
    else:
        pred_index = pd.date_range(
            start=pd.Timestamp.now(tz="UTC").floor("15min") + pd.Timedelta(minutes=15),
            periods=HORIZON,
            freq="15min",
            tz="UTC",
        )

    points: list[PredictionPoint] = []
    for ts, prod, cons in zip(pred_index, pred_prod, pred_cons):
        points.append(
            PredictionPoint(
                timestamp=ts,
                production_kw=float(prod),
                consumption_kw=float(cons),
                surplus_kw=float(prod - cons),
            )
        )

    response = PredictionResponse(
        generated_at=datetime.now(timezone.utc),
        horizon_steps=HORIZON,
        predictions=points,
    )

    with CACHE_LOCK:
        PREDICTIONS_CACHE["response"] = response.model_dump()

    return response


async def predict_and_store(session: AsyncSession, installation_id: int = 1) -> None:
    """Job de fond : génère les prédictions depuis DB et les stocke dans Prediction."""
    if not models_available():
        LOGGER.warning(
            "Skipping prediction refresh: model files are missing at %s and %s.",
            PRODUCTION_MODEL_PATH,
            CONSUMPTION_MODEL_PATH,
        )
        return

    try:
        LOGGER.info("Refreshing predictions (DB forecast + real production lags).")

        # 1. Prévisions météo depuis WeatherForecast en DB (remplie juste avant par fetch_and_store_weather_forecast)
        forecast_df = await build_forecast_dataset_from_db(session, installation_id)
        if forecast_df.empty:
            LOGGER.warning("WeatherForecast DB vide, fallback MeteoSwiss live.")
            forecast_df = await build_realtime_dataset_async()

        # 2. Historique récent de production (pour alimenter les lags AR et les lags exogènes)
        recent_prod_df = await _fetch_recent_production_df(session, installation_id, n_rows=200)

        # 3. Features avec lags réels
        features_df = _build_features_for_inference(recent_prod_df, forecast_df)

        # 4. last_window pour les lags AR internes du forecaster
        last_window_prod = recent_prod_df["production_kw"] if not recent_prod_df.empty else None
        last_window_cons = recent_prod_df["consumption_kw"] if not recent_prod_df.empty else None

        response = build_prediction_response(features_df, last_window_prod, last_window_cons)

        reference_time = response.generated_at
        records = [
            {
                "target_time": p.timestamp,
                "reference_time": reference_time,
                "installation_id": installation_id,
                "production_kw": p.production_kw,
                "consumption_kw": p.consumption_kw,
                "surplus_kw": p.surplus_kw,
            }
            for p in response.predictions
        ]

        if records:
            stmt = insert(Prediction).values(records)
            stmt = stmt.on_conflict_do_update(
                index_elements=["installation_id", "target_time", "reference_time"],
                set_={
                    "production_kw": stmt.excluded.production_kw,
                    "consumption_kw": stmt.excluded.consumption_kw,
                    "surplus_kw": stmt.excluded.surplus_kw,
                },
            )
            await session.execute(stmt)
            await session.commit()
            LOGGER.info("Saved %d predictions to DB.", len(records))

    except RuntimeError as exc:
        LOGGER.warning("Prediction refresh skipped: %s", exc)
    except Exception:
        LOGGER.exception("Prediction refresh failed.")



def get_health_payload() -> dict[str, Any]:
	"""Health payload with model availability status."""
	models_loaded = models_available()
	return {
		"status": "ok",
		"timestamp": datetime.now(timezone.utc).isoformat(),
		"models_loaded": bool(models_loaded),
	}