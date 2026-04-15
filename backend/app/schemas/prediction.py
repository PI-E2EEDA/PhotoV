"""Pydantic schemas for forecasting API responses."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PredictionPoint(BaseModel):
	"""Single prediction point at a specific timestamp."""

	timestamp: datetime
	production_kw: float
	consumption_kw: float
	surplus_kw: float


class PredictionResponse(BaseModel):
	"""Prediction payload for a fixed forecast horizon."""

	generated_at: datetime
	horizon_steps: int = Field(ge=1)
	predictions: list[PredictionPoint]


class BestSlotResponse(BaseModel):
	"""Optimal slot recommendation payload."""

	best_start: datetime
	best_end: datetime
	avg_surplus_kw: float
	reason: str

