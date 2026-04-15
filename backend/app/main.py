from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes_predict import router
from .ml.inference import models_available, refresh_predictions_task
from .ml.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
	"""Startup: scheduler + warmup. Shutdown: clean stop."""
	start_scheduler()
	if models_available():
		refresh_predictions_task()
	yield
	stop_scheduler()
	


app = FastAPI(lifespan=lifespan)

app.add_middleware(
	CORSMiddleware,
	allow_origins=[
		"http://localhost:5173",
		"http://localhost:3000",
	],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
async def root():
	return {"message": "Hello World"}
