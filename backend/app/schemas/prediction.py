from datetime import datetime
from pydantic import BaseModel
class PredictionPoint(BaseModel):
    timestamp: datetime
    production_kw: float
    consumption_kw: float
    surplus_kw: float
class PredictionResponse(BaseModel):
    generated_at: datetime
    horizon_steps: int
    predictions: list[PredictionPoint]
class BestSlotResponse(BaseModel):
    best_start: datetime
    best_end: datetime
    avg_surplus_kw: float
    reason: str
