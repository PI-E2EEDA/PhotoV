"""Train ML forecasters from local PostgreSQL data.

Step-by-step helper:
1) Optional remote backfill (power measures)
2) Build aligned 15-minute training frame from Measure + WeatherHistory
3) Run feature engineering + training
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session_maker
from app.models import Installation, Measure, MeasureType, WeatherHistory

from .config import (
    INTERNAL_WEATHER_COLUMNS,
    LOCAL_TIMEZONE,
    METEOSWISS_POINT_ID,
)
from .feature_engineering import build_features
from .model_training import (
    create_forecasters,
    optimize_hyperparameters,
    run_training_pipeline,
    train_forecaster,
)
from .remote_production_ingestion import backfill_remote_production_into_db


@dataclass
class TrainingBuildResult:
    raw_rows: int
    feature_rows: int
    features_df: pd.DataFrame


def _compute_metrics(y_true: pd.Series, y_pred: np.ndarray) -> dict[str, float]:
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    mae = float(mean_absolute_error(y_true, y_pred))
    denom = float(max(1e-9, y_true.max() - y_true.min()))
    nrmse_pct = float((rmse / denom) * 100.0)
    return {
        "rmse": rmse,
        "mae": mae,
        "nrmse_pct": nrmse_pct,
    }


def _evaluate_reliability(
    features_df: pd.DataFrame,
    optimize: bool,
    optuna_trials: int,
) -> dict[str, dict[str, float]]:
    split_idx = int(len(features_df) * 0.8)
    split_idx = max(300, split_idx)
    split_idx = min(split_idx, len(features_df) - 50)
    train_df = features_df.iloc[:split_idx].copy()
    val_df = features_df.iloc[split_idx:].copy()

    if len(val_df) < 30:
        raise ValueError("Validation set trop petit pour evaluer la fiabilite")

    target_map = {
        "production": "production_kw",
        "consumption": "consumption_kw",
    }
    forecasters = create_forecasters()
    report: dict[str, dict[str, float]] = {}

    for model_name, target_col in target_map.items():
        exog_cols = [
            col
            for col in features_df.select_dtypes(include=[np.number]).columns
            if col != target_col
        ]
        y_train = train_df[target_col]
        y_val = val_df[target_col]
        exog_train = train_df[exog_cols] if exog_cols else None
        exog_val = val_df[exog_cols] if exog_cols else None

        if optimize:
            best = optimize_hyperparameters(
                forecaster=forecasters[model_name],
                df=train_df,
                target_col=target_col,
                n_trials=optuna_trials,
            )
            forecasters[model_name].regressor.set_params(**best)

        trained = train_forecaster(forecasters[model_name], train_df, target_col)
        y_pred = np.asarray(trained.predict(steps=len(y_val), exog=exog_val), dtype=float)

        baseline = features_df[target_col].shift(1).loc[val_df.index].bfill()
        baseline_pred = np.asarray(baseline, dtype=float)

        model_metrics = _compute_metrics(y_val, y_pred)
        baseline_metrics = _compute_metrics(y_val, baseline_pred)
        gain_rmse_pct = 100.0 * (baseline_metrics["rmse"] - model_metrics["rmse"]) / max(
            1e-9,
            baseline_metrics["rmse"],
        )

        report[model_name] = {
            "val_rows": float(len(y_val)),
            "rmse_kw": model_metrics["rmse"],
            "mae_kw": model_metrics["mae"],
            "nrmse_pct": model_metrics["nrmse_pct"],
            "baseline_rmse_kw": baseline_metrics["rmse"],
            "baseline_mae_kw": baseline_metrics["mae"],
            "rmse_gain_vs_persistence_pct": float(gain_rmse_pct),
        }

    return report


async def _load_installation(session: AsyncSession, installation_id: int) -> Installation:
    res = await session.execute(
        select(Installation).where(Installation.id == installation_id)
    )
    inst = res.scalars().first()
    if inst is None:
        raise ValueError(f"Installation {installation_id} introuvable en base")
    return inst


async def _build_training_dataframe(
    session: AsyncSession,
    installation_id: int,
) -> pd.DataFrame:
    measure_result = await session.execute(
        select(Measure)
        .where(Measure.installation_id == installation_id)
        .where(Measure.type == MeasureType.power)
        .order_by(Measure.time.asc())
    )
    measures = measure_result.scalars().all()
    if not measures:
        raise ValueError("Aucune mesure de puissance disponible pour l'installation")

    m_df = pd.DataFrame(
        {
            "time": [m.time for m in measures],
            "production_kw": [float(m.solar_production) / 1000.0 for m in measures],
            "consumption_kw": [float(m.solar_consumption + m.grid_consumption) / 1000.0 for m in measures],
        }
    )
    # Measure.time is naive local time (SolarEdge convention). Localize to the
    # installation timezone then convert to UTC to align with WeatherHistory.
    m_df["time"] = pd.to_datetime(m_df["time"])
    if m_df["time"].dt.tz is None:
        m_df["time"] = m_df["time"].dt.tz_localize(
            LOCAL_TIMEZONE, ambiguous="infer", nonexistent="shift_forward"
        )
    m_df["time"] = m_df["time"].dt.tz_convert("UTC")
    m_df = m_df.drop_duplicates(subset=["time"]).set_index("time").sort_index()

    w_result = await session.execute(
        select(WeatherHistory)
        .where(WeatherHistory.point_id == METEOSWISS_POINT_ID)
        .where(WeatherHistory.time >= m_df.index.min().to_pydatetime())
        .where(WeatherHistory.time <= m_df.index.max().to_pydatetime())
        .order_by(WeatherHistory.time.asc())
    )
    weather = w_result.scalars().all()

    if weather:
        w_df = pd.DataFrame(
            {
                "time": [w.time for w in weather],
                "temperature_2m": [float(w.temperature_2m) for w in weather],
                "shortwave_radiation": [float(w.shortwave_radiation) for w in weather],
                "diffuse_radiation": [float(w.diffuse_radiation) for w in weather],
                "precipitation": [float(w.precipitation) for w in weather],
                "windspeed_10m": [float(w.windspeed_10m) for w in weather],
                "cloudcover_high": [float(w.cloudcover_high) for w in weather],
                "cloudcover_medium": [float(w.cloudcover_medium) for w in weather],
                "cloudcover_low": [float(w.cloudcover_low) for w in weather],
            }
        )
        w_df["time"] = pd.to_datetime(w_df["time"], utc=True)
        w_df = w_df.drop_duplicates(subset=["time"]).set_index("time").sort_index()

        # == ALIGNEMENT MANUEL (SUPERPOSITION & TIMEZONE) ==
        # On garantit que les deux index sont bien dans le même référentiel UTC
        if m_df.index.tz is None:
            m_df.index = m_df.index.tz_localize("UTC")
        else:
            m_df.index = m_df.index.tz_convert("UTC")

        if w_df.index.tz is None:
            w_df.index = w_df.index.tz_localize("UTC")
        else:
            w_df.index = w_df.index.tz_convert("UTC")

        # On force une intersection temporelle stricte pour éviter l'extrapolation (les NaNs / 0 artificiels)
        common_start = max(m_df.index.min(), w_df.index.min())
        common_end = min(m_df.index.max(), w_df.index.max())

        m_df = m_df.loc[common_start:common_end]

        if m_df.empty:
            raise ValueError("L'intersection temporelle entre les Mesures et la Météo est vide. Impossible de s'entraîner.")

        weather_15 = w_df.reindex(m_df.index)
        weather_15 = weather_15.interpolate(method="time").ffill().bfill()
        print(f"Meteo historique utilisee: {len(w_df)} lignes. Alignée de {common_start} à {common_end}.")
    else:
        # First run fallback: allow training with autoregressive + temporal features only.
        weather_15 = pd.DataFrame(index=m_df.index)
        for col in INTERNAL_WEATHER_COLUMNS:
            weather_15[col] = 0.0
        print("Attention: aucune meteo historique sur cette periode, fallback meteo=0 active")

    dataset = m_df.join(weather_15, how="left")
    dataset = dataset.sort_index()
    # Resample to strict 15-min frequency: skforecast requires a regular DatetimeIndex.
    # Gaps <= 1h (4 steps) are interpolated; longer gaps are dropped.
    dataset = dataset.resample("15min").asfreq()
    dataset = dataset.interpolate(method="time", limit=4).ffill().bfill().dropna()
    return dataset


async def run_training_from_db(
    installation_id: int,
    backfill_rows: int,
    optimize: bool,
    optuna_trials: int,
) -> TrainingBuildResult:
    async with async_session_maker() as session:
        inst = await _load_installation(session, installation_id)

        if backfill_rows > 0:
            inserted = await backfill_remote_production_into_db(
                session,
                total_rows=backfill_rows,
                page_size=200,
            )
            print(f"Backfill mesures distantes: {inserted} lignes upsert")

        raw_df = await _build_training_dataframe(session, installation_id=installation_id)
        print(
            "Dataset brut: "
            f"{len(raw_df)} lignes, de {raw_df.index.min()} a {raw_df.index.max()}"
        )
        print(
            "Installation utilisee: "
            f"id={inst.id}, lat={inst.latitude}, lon={inst.longitude}, "
            f"tilt={inst.panel_angle}, azimut={inst.panel_orientation}, model={inst.model}"
        )

    features_df = build_features(raw_df, drop_na=True)
    print(f"Dataset features: {len(features_df)} lignes")

    if len(features_df) < 300:
        raise ValueError(
            "Pas assez de lignes pour un entrainement robuste (min 300 apres features). "
            "Augmente --backfill-rows ou attends plus de donnees."
        )

    reliability = _evaluate_reliability(
        features_df=features_df,
        optimize=optimize,
        optuna_trials=optuna_trials,
    )
    print("\n=== Rapport fiabilite (holdout temporel 20%) ===")
    for name, metrics in reliability.items():
        print(
            f"{name}: RMSE={metrics['rmse_kw']:.3f} kW, "
            f"MAE={metrics['mae_kw']:.3f} kW, "
            f"nRMSE={metrics['nrmse_pct']:.2f}%, "
            f"baseline_RMSE={metrics['baseline_rmse_kw']:.3f} kW, "
            f"gain={metrics['rmse_gain_vs_persistence_pct']:.2f}%"
        )

    run_training_pipeline(features_df, optimize=optimize, optuna_trials=optuna_trials)
    return TrainingBuildResult(
        raw_rows=len(raw_df),
        feature_rows=len(features_df),
        features_df=features_df,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train forecasters from DB")
    parser.add_argument("--installation-id", type=int, default=1)
    parser.add_argument(
        "--backfill-rows",
        type=int,
        default=1200,
        help="Nombre de lignes power a backfiller depuis l'API distante avant training",
    )
    parser.add_argument(
        "--optimize",
        action="store_true",
        help="Active Optuna (plus long)",
    )
    parser.add_argument(
        "--optuna-trials",
        type=int,
        default=20,
        help="Nombre d'essais Optuna par modele (utilise seulement avec --optimize)",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    result = asyncio.run(
        run_training_from_db(
            installation_id=args.installation_id,
            backfill_rows=args.backfill_rows,
            optimize=args.optimize,
            optuna_trials=args.optuna_trials,
        )
    )
    print(
        "Entrainement termine: "
        f"raw_rows={result.raw_rows}, feature_rows={result.feature_rows}"
    )


if __name__ == "__main__":
    main()

