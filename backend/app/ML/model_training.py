"""Model training pipeline for PV production and household consumption forecasting."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import numpy as np
import optuna
import pandas as pd
from lightgbm import LGBMRegressor
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import TimeSeriesSplit

from .config import MODELS_DIR
# Import de ton moteur de features !
from .feature_engineering import build_features

try:
    from skforecast.ForecasterAutoreg import ForecasterAutoreg
except ImportError:  # pragma: no cover
    from skforecast.recursive import ForecasterRecursive as ForecasterAutoreg

# Sensible defaults — skip Optuna entirely in quick mode
DEFAULT_LGBM_PARAMS: dict[str, Any] = {
    "num_leaves": 63,
    "learning_rate": 0.08,
    "n_estimators": 400,
    "min_child_samples": 20,
    "random_state": 42,
    "n_jobs": -1,
}


def _prepare_training_data(df: pd.DataFrame, target_col: str) -> tuple[pd.Series, pd.DataFrame | None]:
    """Prepare target and exogenous matrices from a numeric feature table."""
    if target_col not in df.columns:
        raise ValueError(f"Target column not found: {target_col}")

    numeric_df = df.select_dtypes(include=[np.number]).copy()
    exog_cols = [col for col in numeric_df.columns if col != target_col]
    cols_to_check = [target_col] + exog_cols
    prepared = numeric_df[cols_to_check].dropna()

    if len(prepared) < 300:
        raise ValueError("Not enough rows after dropping NaNs to train robustly.")

    y = prepared[target_col]
    exog = prepared[exog_cols] if exog_cols else None
    return y, exog


def create_forecasters() -> dict[str, Any]:
    """Create independent autoregressive forecasters for both targets."""
    # Les lags sont réduits ici car on utilise les lags de build_features en exogène
    base_lags = [1, 4]

    forecasters = {
        "production": ForecasterAutoreg(
            regressor=LGBMRegressor(**DEFAULT_LGBM_PARAMS), lags=base_lags,
        ),
        "consumption": ForecasterAutoreg(
            regressor=LGBMRegressor(**DEFAULT_LGBM_PARAMS), lags=base_lags,
        ),
    }
    return forecasters


def optimize_hyperparameters(
    forecaster: Any,
    df: pd.DataFrame,
    target_col: str,
    n_trials: int = 20,
) -> dict[str, Any]:
    """Optimize LGBMRegressor hyperparameters with Optuna and time CV."""
    y, exog = _prepare_training_data(df, target_col)
    splitter = TimeSeriesSplit(n_splits=3)
    forecaster_lags = forecaster.lags

    def objective(trial: optuna.trial.Trial) -> float:
        params = {
            "num_leaves": trial.suggest_int("num_leaves", 31, 127),
            "learning_rate": trial.suggest_float("learning_rate", 0.03, 0.2),
            "n_estimators": trial.suggest_int("n_estimators", 200, 600),
            "min_child_samples": trial.suggest_int("min_child_samples", 10, 50),
            "random_state": 42,
            "n_jobs": -1,
        }

        rmse_values: list[float] = []
        for train_idx, val_idx in splitter.split(y):
            y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]
            exog_train = exog.iloc[train_idx] if exog is not None else None
            exog_val = exog.iloc[val_idx] if exog is not None else None

            fold_forecaster = ForecasterAutoreg(
                regressor=LGBMRegressor(**params),
                lags=forecaster_lags,
            )
            fold_forecaster.fit(y=y_train, exog=exog_train)
            preds = fold_forecaster.predict(steps=len(y_val), exog=exog_val)

            rmse = float(np.sqrt(mean_squared_error(y_val, preds)))
            rmse_values.append(rmse)

        return float(np.mean(rmse_values))

    study = optuna.create_study(direction="minimize")
    study.optimize(objective, n_trials=n_trials)
    return dict(study.best_params)


def train_forecaster(forecaster: Any, df: pd.DataFrame, target_col: str) -> Any:
    """Train a forecaster on the full available dataset."""
    y, exog = _prepare_training_data(df, target_col)
    forecaster.fit(y=y, exog=exog)
    return forecaster


def save_forecaster(forecaster: Any, filepath: str) -> None:
    """Serialize a trained forecaster to disk with joblib."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(forecaster, path)


def load_forecaster(filepath: str) -> Any:
    """Load a serialized forecaster from a joblib file."""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Forecaster file not found: {filepath}")
    return joblib.load(path)


def run_training_pipeline(
    df: pd.DataFrame,
    output_dir: str = MODELS_DIR,
    optimize: bool = True,
) -> dict[str, Any]:
    """Run full training workflow for production and consumption models."""
    # On n'ajoute plus is_holiday ici, on suppose que df est déjà passé par build_features()
    forecasters = create_forecasters()

    target_map = {
        "production": "production_kw",
        "consumption": "consumption_kw",
    }

    best_params: dict[str, dict[str, Any]] = {}
    trained_forecasters: dict[str, Any] = {}

    for model_name, target_col in target_map.items():
        if optimize:
            best = optimize_hyperparameters(
                forecaster=forecasters[model_name],
                df=df,
                target_col=target_col,
                n_trials=20, # 20 est suffisant pour LightGBM
            )
            best_params[model_name] = best
            forecasters[model_name].regressor.set_params(**best)
        else:
            best_params[model_name] = DEFAULT_LGBM_PARAMS

        trained = train_forecaster(
            forecaster=forecasters[model_name],
            df=df,
            target_col=target_col,
        )
        trained_forecasters[model_name] = trained

        model_path = Path(output_dir) / f"{model_name}_forecaster.joblib"
        save_forecaster(trained, str(model_path))

    return {
        "forecasters": trained_forecasters,
        "best_params": best_params,
    }


if __name__ == "__main__":
    print("Génération des données simulées...")
    date_index = pd.date_range(
        start="2025-01-01",
        periods=30 * 24 * 4, # 1 mois
        freq="15min",
        tz="UTC",
    )

    rng = np.random.default_rng(42)
    hour_float = date_index.hour + (date_index.minute / 60.0)

    # Simulation météo de base
    daylight_profile = np.clip(np.sin((hour_float - 6.0) * np.pi / 12.0), 0.0, None)
    shortwave = daylight_profile * 700.0 + rng.normal(0.0, 30.0, len(date_index))
    shortwave = np.clip(shortwave, 0.0, None)
    diffuse = shortwave * 0.3 # Simulation basique du diffus

    temperature = 8.0 + 8.0 * np.sin(2.0 * np.pi * (date_index.dayofyear.values / 365.0))
    temperature += 3.0 * np.sin(2.0 * np.pi * hour_float / 24.0)

    # Simulation prod/conso cible
    production = 0.005 * shortwave + rng.normal(0.0, 0.15, len(date_index))
    production = np.clip(production, 0.0, None)

    evening_peak = np.exp(-0.5 * ((hour_float - 19.0) / 2.8) ** 2)
    morning_peak = np.exp(-0.5 * ((hour_float - 7.5) / 2.2) ** 2)
    consumption = 1.1 + 0.7 * morning_peak + 0.9 * evening_peak
    consumption = np.clip(consumption, 0.1, None)

    # 1. On crée le DataFrame brut avec TOUTES les colonnes attendues par feature_engineering
    demo_df = pd.DataFrame(
        {
            "production_kw": production,
            "consumption_kw": consumption,
            "temperature_2m": temperature,
            "shortwave_radiation": shortwave,
            "diffuse_radiation": diffuse,
            "precipitation": np.zeros(len(date_index)),
            "windspeed_10m": np.full(len(date_index), 5.0),
            "cloudcover_high": np.full(len(date_index), 20.0),
            "cloudcover_medium": np.full(len(date_index), 20.0),
            "cloudcover_low": np.full(len(date_index), 20.0),
        },
        index=date_index,
    )

    # 2. LA MAGIE : On passe nos fausses données dans le vrai pipeline de features !
    print("Application du Feature Engineering (Physique solaire)...")
    engineered_df = build_features(demo_df, drop_na=True)

    # 3. Entraînement sur les features finales (avec poa_global_radiation)
    print("Lancement de l'entraînement LightGBM...")
    result = run_training_pipeline(engineered_df, optimize=True)
    print("\n✅ Entraînement terminé ! Modèles sauvegardés dans :", MODELS_DIR)