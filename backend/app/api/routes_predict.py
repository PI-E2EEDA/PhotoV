"""Prediction API routes for PV production and household consumption."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from ..ml.inference import (
	build_prediction_response,
	get_best_slot,
	get_health_payload,
	models_available,
	refresh_predictions_task,
)
from ..schemas.prediction import BestSlotResponse, PredictionResponse

router = APIRouter(tags=["forecast"])
_executor = ThreadPoolExecutor(max_workers=2)


@router.get("/predict", response_model=PredictionResponse)
async def predict() -> PredictionResponse:
	"""Generate 3-day forecasts off the event loop."""
	try:
		loop = asyncio.get_running_loop()
		return await loop.run_in_executor(_executor, build_prediction_response, None)
	except RuntimeError as exc:
		raise HTTPException(status_code=503, detail=str(exc)) from exc
	except FileNotFoundError as exc:
		raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/best-slot", response_model=BestSlotResponse)
async def best_slot(duration_minutes: int = Query(default=60, ge=15)) -> BestSlotResponse:
	"""Return the best slot based on average surplus."""
	try:
		loop = asyncio.get_running_loop()
		return await loop.run_in_executor(_executor, get_best_slot, duration_minutes)
	except RuntimeError as exc:
		raise HTTPException(status_code=503, detail=str(exc)) from exc
	except FileNotFoundError as exc:
		raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/health")
def health() -> dict[str, Any]:
	"""Health endpoint with model availability status."""
	return get_health_payload()


@router.post("/refresh")
def refresh(background_tasks: BackgroundTasks) -> dict[str, str]:
	"""Trigger prediction refresh asynchronously."""
	background_tasks.add_task(refresh_predictions_task)
	return {"status": "refresh started"}

