# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PhotoV is a solar installation monitoring and optimization app. It ingests solar production/consumption data from SolarEdge, stores 15-minute interval measures, fetches weather data, and uses ML forecasters to predict future production/consumption to optimize household energy usage.

## Monorepo Structure

- `backend/` — FastAPI Python API, managed with [UV](https://docs.astral.sh/uv/)
- `frontend/` — Vue 3 SPA (Vite, Pinia, Vue Router, TailwindCSS v4), managed with pnpm
- `proxy/` — Caddy reverse proxy for HTTPS and subdomain routing
- `infra/` — Docker Compose infrastructure (PostgreSQL, all services)
- `data-acquisition/` — Standalone scripts for reading SmartPlug hardware

## Development Commands

### Backend
```sh
cd infra && docker compose up db -d   # start PostgreSQL on port 5432
cd backend
uv run alembic upgrade head           # apply migrations
export AUTH_SERVER_SECRET=dev-secret
uv run fastapi dev                    # http://localhost:8000, docs at /docs
```

### Frontend
```sh
cd frontend
pnpm install
pnpm dev          # http://localhost:5173
pnpm build        # type-check + build
pnpm test:unit    # Vitest
pnpm lint         # oxlint + eslint (auto-fix)
pnpm format       # prettier
```

### Generate API client from local backend
```sh
cd frontend && pnpm localapigen   # regenerates src/api/Api.ts from localhost:8000
```

### Database migrations
```sh
cd backend
uv run alembic revision --autogenerate -m "Description"
uv run alembic upgrade head
```

## Backend Architecture

**Stack:** FastAPI (async) + SQLModel + SQLAlchemy async + asyncpg + FastAPI Users + Alembic + APScheduler

**Entry point:** `backend/app/main.py` — registers routes, starts/stops the APScheduler on lifespan.

**Database connection:** `backend/app/db.py` — async engine using `asyncpg`. Uses `psycopg` (sync) for Alembic. DB credentials come from env vars (`POSTGRES_PASSWORD`, `POSTGRES_USER`, `POSTGRES_DB`, `DB_HOST`); defaults match the dev Docker setup (`photov`/`photov`).

**Models:** `backend/app/models.py` — all SQLModel table models. Mixed `SQLModel` (for most tables) and `SQLAlchemy declarative_base` (for `User` and `AccessToken`, required by FastAPI Users). Foreign key constraints on `UserInstallationLink` must be set manually in migrations due to a SQLModel limitation.

**Authentication:** FastAPI Users with bearer token + database strategy. Tokens last 3 weeks. New users must be manually verified in the DB (`UPDATE "user" SET is_verified = true WHERE id = ...`). Required env var: `AUTH_SERVER_SECRET`.

**Key domain invariant:** All energy values are stored in **Wh**, all power values in **W**. Unit conversion to kW/kWh happens only at the display layer.

**Smartplug timestamps** are stored as local time (no timezone), matching SolarEdge's convention.

## ML Pipeline (`backend/app/ML/`)

The ML subsystem forecasts solar production and household consumption 3 days ahead (288 × 15-minute steps) using LightGBM via `skforecast`.

| File | Responsibility |
|---|---|
| `config.py` | All ML constants and env var overrides (location, panel specs, MeteoSwiss point, horizon, remote ingestion settings) |
| `data_pipeline.py` | Fetches Open-Meteo weather history and forecast; assembles the realtime dataset |
| `feature_engineering.py` | Temporal and solar-geometry features built on top of the raw dataset |
| `model_training.py` | Creates `ForecasterRecursive` wrappers, Optuna hyperparameter search, saves `.joblib` artifacts |
| `train_from_db.py` | End-to-end CLI trainer: optional backfill → DB load → feature build → reliability report → save models |
| `inference.py` | Loads model artifacts, generates predictions, caches in memory, persists to `Prediction` table |
| `scheduler.py` | APScheduler jobs: hourly (pull remote + forecast + predict), daily 2AM (weather history), weekly Sunday 3AM (retrain) |
| `remote_production_ingestion.py` | Pulls power measures from a remote PhotoV instance into local DB |

**Trained artifacts** are saved to `backend/app/artifacts/` as `production_forecaster.joblib` and `consumption_forecaster.joblib`.

**Training from scratch** (inside API container):
```sh
uv run -m app.ML.train_from_db --installation-id 1 --backfill-rows 1200
# with Optuna hyperparameter search (slower):
uv run -m app.ML.train_from_db --installation-id 1 --backfill-rows 1200 --optimize --optuna-trials 20
```

**ML env vars** (all prefixed `PV_`): `PV_LATITUDE`, `PV_LONGITUDE`, `PV_ALTITUDE_M`, `PV_PANEL_ANGLE`, `PV_PANEL_ORIENTATION`, `PV_PANEL_COUNT`, `PV_METEOSWISS_POINT_ID`, `PV_HORIZON`, `PV_MODELS_DIR`, `PV_REMOTE_ENABLED`, `PV_REMOTE_BASE_URL`, `PV_REMOTE_TOKEN`, etc.

## Frontend Architecture

**Stack:** Vue 3 Composition API + Pinia (with `pinia-plugin-persistedstate`) + Vue Router + Chart.js + TailwindCSS v4

**API client:** `frontend/src/api/Api.ts` is auto-generated from the backend's OpenAPI spec via `swagger-typescript-api`. Do not edit it manually — regenerate with `pnpm localapigen` (local) or `pnpm apigen` (production).

**State:** `frontend/src/stores/api.ts` — Pinia store managing auth token (persisted), installation ID, and API calls.

## Infrastructure

The `infra/docker-compose.yml` defines: `proxy` (Caddy), `frontend`, `api`, `db` (PostgreSQL), `dbdev` (dev-only, profile `dev`), `backups`.

For local dev, use the `dbdev` profile or uncomment ports on the `db` service. The `AUTH_SERVER_SECRET` must be set; it is not in `.env.example` with a default value.

## SolarEdge Data Import

Initial bulk import and cleanup scripts:
```sh
# Configure credentials first
cp infra/creds/pull.config.json.example infra/creds/pull.config.json

docker compose exec api sh
uv run -m app.tasks.pull-history pull --installation-id 1
uv run -m app.tasks.pull-history clean --installation-id 1   # remove zero-value prefix rows
uv run -m app.tasks.pull-history check --installation-id 1   # coherence audit
```
