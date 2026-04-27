from datetime import datetime
from pydantic import BaseModel


class SchedulerHealth(BaseModel):
    running: bool
    last_run_iso: str | None = None
    next_run_iso: str | None = None


class RemoteIngestionHealth(BaseModel):
    enabled: bool
    last_sync_iso: str | None = None
    last_error: str | None = None


class MLIngestionHealthResponse(BaseModel):
    status: str
    checked_at: datetime
    database: dict
    scheduler: SchedulerHealth
    remote_ingestion: RemoteIngestionHealth

