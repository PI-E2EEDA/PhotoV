"""Inference services for PV production and household consumption forecasting."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

import numpy as np
import pandas as pd

from ..schemas.prediction import BestSlotResponse, PredictionPoint, PredictionResponse
from .config import HORIZON, MODELS_DIR, INTERNAL_WEATHER_COLUMNS
from .data_pipeline import build_dataset
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


def _prepare_base_features() -> pd.DataFrame:
	"""Build realtime dataset and transform it into feature space."""
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
	if features_df.empty:
		future_index = pd.date_range(
			start=pd.Timestamp.now(tz="UTC").floor("15min") + pd.Timedelta(minutes=15),
			periods=horizon,
			freq="15min",
			tz="UTC",
		)
		candidate = pd.DataFrame(index=future_index)
	else:
		start_ts = features_df.index.max() + pd.Timedelta(minutes=15)
		future_index = pd.date_range(start=start_ts, periods=horizon, freq="15min", tz="UTC")
		candidate = features_df.reindex(future_index)

	candidate = candidate.copy()
	candidate = candidate.interpolate(method="linear", limit_direction="both")
	candidate = candidate.ffill().bfill().fillna(0.0)

	expected_cols = list(getattr(forecaster, "exog_names_in_", []) or [])
	if not expected_cols:
		return None

	for col in expected_cols:
		if col not in candidate.columns:
			candidate[col] = 0.0

	exog = candidate[expected_cols]
	return exog.astype(float)


def build_prediction_response(features_df: pd.DataFrame | None = None) -> PredictionResponse:
	"""Generate predictions and format API response payload."""
	production_forecaster, consumption_forecaster = _load_forecasters()
	features = features_df if features_df is not None else _prepare_base_features()

	exog_prod = _build_exog_for_forecaster(features, production_forecaster, HORIZON)
	exog_cons = _build_exog_for_forecaster(features, consumption_forecaster, HORIZON)

	pred_prod_raw = production_forecaster.predict(steps=HORIZON, exog=exog_prod)
	pred_cons_raw = consumption_forecaster.predict(steps=HORIZON, exog=exog_cons)

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


def refresh_predictions_task() -> None:
	"""Background job that refreshes cached predictions."""
	if not models_available():
		LOGGER.warning(
			"Skipping prediction refresh: model files are missing at %s and %s.",
			PRODUCTION_MODEL_PATH,
			CONSUMPTION_MODEL_PATH,
		)
		return

	try:
		LOGGER.info("Refreshing prediction cache.")
		dataset = build_dataset(source="realtime")
		features_df = build_features(dataset, drop_na=False)
		build_prediction_response(features_df)
		LOGGER.info("Prediction cache refreshed successfully.")
	except RuntimeError as exc:
		LOGGER.warning("Prediction refresh skipped: %s", exc)
	except Exception:
		LOGGER.exception("Prediction refresh failed.")


def get_best_slot(duration_minutes: int = 60) -> BestSlotResponse:
	"""Return the best time slot with maximum positive average surplus."""
	with CACHE_LOCK:
		cached = PREDICTIONS_CACHE.get("response")

	if cached is None:
		cached = build_prediction_response().model_dump()

	pred_items = cached["predictions"]
	timestamps = pd.to_datetime([item["timestamp"] for item in pred_items], utc=True)
	surplus_values = np.array([float(item["surplus_kw"]) for item in pred_items], dtype=float)

	window_steps = max(1, int(np.ceil(duration_minutes / 15)))
	window_steps = min(window_steps, len(surplus_values))

	best_avg = -np.inf
	best_start_idx = 0

	for i in range(0, len(surplus_values) - window_steps + 1):
		window = surplus_values[i : i + window_steps]
		avg_surplus = float(window.mean())
		if avg_surplus > best_avg:
			best_avg = avg_surplus
			best_start_idx = i

	if best_avg > 0.0:
		start_ts = timestamps[best_start_idx]
		end_ts = timestamps[best_start_idx + window_steps - 1]
		reason = (
			f"Best window over {duration_minutes} minutes based on maximum "
			"average surplus."
		)
		avg_value = best_avg
	else:
		start_ts = timestamps[0]
		end_ts = timestamps[min(window_steps - 1, len(timestamps) - 1)]
		reason = "No positive average surplus found; returning the earliest available window."
		avg_value = 0.0

	return BestSlotResponse(
		best_start=start_ts,
		best_end=end_ts,
		avg_surplus_kw=float(avg_value),
		reason=reason,
	)


def get_health_payload() -> dict[str, Any]:
	"""Health payload with model availability status."""
	models_loaded = models_available()
	return {
		"status": "ok",
		"timestamp": datetime.now(timezone.utc).isoformat(),
		"models_loaded": bool(models_loaded),
	}